from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.engine import Engine

from app.core.market import MARKET_CONTEXTS, MarketCode
from app.db.init_db import init_database
from app.db.repositories.factor_value_repository import FactorValueRepository
from app.db.repositories.financial_repository import FinancialRepository
from app.db.repositories.latest_quote_repository import LatestQuoteRepository
from app.db.repositories.market_bar_repository import MarketBarRepository
from app.db.repositories.signal_repository import SignalRepository
from app.db.repositories.stock_repository import StockRepository
from app.db.repositories.strategy_repository import StrategyRepository
from app.db.repositories.valuation_snapshot_repository import ValuationSnapshotRepository
from app.db.session import create_session_factory, get_engine
from app.models.factor_value import FactorValue
from app.models.financial import Financial
from app.models.latest_quote import LatestQuote
from app.models.market_bar import MarketBar
from app.models.signal import Signal
from app.models.stock import Stock
from app.models.strategy import Strategy
from app.models.valuation_snapshot import ValuationSnapshot
from app.providers.mock_market_fixtures import STOCK_RESEARCH_FIXTURES
from app.quant.pipeline import QuantPipelineInput, run_quant_pipeline
from app.schemas.ai_research import AIResearchRequest
from app.services.ai_research_write_service import create_ai_research_task_record
from app.services.mock_portfolio_service import get_mock_portfolio_summary
from app.services.mock_backtest_service import get_mock_backtest_result
from app.services.mock_strategy_service import get_mock_strategy_lab
from app.services.backtest_write_service import save_backtest_result
from app.services.portfolio_write_service import save_portfolio_summary


def seed_development_data(engine: Engine | None = None, *, timestamp: datetime | None = None) -> dict[str, int]:
    """写入开发用股票、行情、量化结果、策略和模拟组合数据。"""

    resolved_engine = engine or get_engine()
    init_database(resolved_engine)
    session_factory = create_session_factory(resolved_engine)
    seeded_at = timestamp or datetime.now(timezone.utc).replace(tzinfo=None)
    stock_count = 0
    quote_count = 0
    bar_count = 0
    financial_count = 0
    valuation_count = 0
    factor_count = 0
    signal_count = 0
    strategy_count = 0
    portfolio_count = 0
    backtest_count = 0
    agent_task_count = 0

    with session_factory() as session:
        factor_repository = FactorValueRepository(session)
        stock_repository = StockRepository(session)
        quote_repository = LatestQuoteRepository(session)
        bar_repository = MarketBarRepository(session)
        financial_repository = FinancialRepository(session)
        signal_repository = SignalRepository(session)
        strategy_repository = StrategyRepository(session)
        valuation_repository = ValuationSnapshotRepository(session)

        for market, fixtures in STOCK_RESEARCH_FIXTURES.items():
            context = MARKET_CONTEXTS[market]
            for symbol, fixture in fixtures.items():
                stock = stock_repository.get_by_market_symbol(market.value, symbol)
                if stock is None:
                    stock = stock_repository.add(
                        Stock(
                            market=market.value,
                            symbol=symbol,
                            name=fixture["name"],
                            exchange=fixture["exchange"],
                            currency=context.currency,
                            timezone=context.timezone,
                            sector=fixture["sector"],
                            industry=fixture["industry"],
                        )
                    )
                    session.flush()

                price, change, change_percent, volume, turnover = fixture["quote"]
                quote_repository.save_latest(
                    LatestQuote(
                        stock_id=stock.id,
                        market=market.value,
                        symbol=symbol,
                        price=Decimal(str(price)),
                        change_amount=Decimal(str(change)),
                        change_percent=Decimal(str(change_percent)),
                        volume=volume,
                        turnover=Decimal(str(turnover)),
                        data_status=fixture_data_status(market.value),
                        source="mock_seed",
                        quote_timestamp=seeded_at,
                    )
                )
                stock_count += 1
                quote_count += 1
                bar_count += _seed_market_bars(
                    bar_repository=bar_repository,
                    stock=stock,
                    market=market,
                    symbol=symbol,
                    seeded_at=seeded_at,
                )
                financial_repository.save_period(
                    _build_financial(
                        stock=stock,
                        market=market,
                        symbol=symbol,
                        seeded_at=seeded_at,
                    )
                )
                valuation_repository.save_snapshot(
                    _build_valuation_snapshot(
                        stock=stock,
                        market=market,
                        symbol=symbol,
                        seeded_at=seeded_at,
                    )
                )
                factor_count += len(
                    factor_repository.save_values(
                        _build_factor_values(
                            stock=stock,
                            market=market,
                            symbol=symbol,
                            seeded_at=seeded_at,
                        )
                    )
                )
                signal_count += len(
                    signal_repository.save_signals(
                        _build_signals(
                            stock=stock,
                            market=market,
                            symbol=symbol,
                            seeded_at=seeded_at,
                        )
                    )
                )
                financial_count += 1
                valuation_count += 1

        for market in STOCK_RESEARCH_FIXTURES:
            for strategy in _build_strategies(market=market, seeded_at=seeded_at):
                strategy_repository.save_strategy(strategy)
                strategy_count += 1

        session.commit()

        for market in STOCK_RESEARCH_FIXTURES:
            create_ai_research_task_record(session, _build_ai_research_request(market), route_prefix="/research")
            agent_task_count += 1
            save_portfolio_summary(session, get_mock_portfolio_summary(market))
            portfolio_count += 1
            save_backtest_result(session, get_mock_backtest_result(market))
            backtest_count += 1

    return {
        "stocks": stock_count,
        "latest_quotes": quote_count,
        "market_bars": bar_count,
        "financials": financial_count,
        "valuation_snapshots": valuation_count,
        "factor_values": factor_count,
        "signals": signal_count,
        "strategies": strategy_count,
        "portfolios": portfolio_count,
        "backtests": backtest_count,
        "agent_tasks": agent_task_count,
    }


def fixture_data_status(market: str) -> str:
    """根据市场返回当前 Mock Seed 的数据状态。"""

    return "realtime" if market == "US" else "delayed"


def _seed_market_bars(
    *,
    bar_repository: MarketBarRepository,
    stock: Stock,
    market: MarketCode,
    symbol: str,
    seeded_at: datetime,
) -> int:
    """为单只股票写入最近 30 根日线 K 线；已存在时跳过。"""

    existing_bars = bar_repository.list_latest(market.value, symbol, "1d", limit=1)
    if existing_bars:
        return 0

    fixture = STOCK_RESEARCH_FIXTURES[market][symbol]
    base_price, daily_step = fixture["kline_seed"]
    base_price_decimal = Decimal(str(base_price))
    daily_step_decimal = Decimal(str(daily_step))
    latest_volume = fixture["quote"][3]
    bars: list[MarketBar] = []

    for index in range(30):
        open_price, high_price, low_price, close_price = _build_seed_ohlc(
            index=index,
            base_price=base_price_decimal,
            daily_step=daily_step_decimal,
        )

        bars.append(
            MarketBar(
                stock_id=stock.id,
                market=market.value,
                symbol=symbol,
                interval_code="1d",
                bar_timestamp=seeded_at.replace(hour=0, minute=0, second=0, microsecond=0)
                - timedelta(days=29 - index),
                open_price=open_price.quantize(Decimal("0.000001")),
                high_price=high_price.quantize(Decimal("0.000001")),
                low_price=max(low_price, Decimal("0.01")).quantize(Decimal("0.000001")),
                close_price=close_price.quantize(Decimal("0.000001")),
                volume=max(int(latest_volume * (0.72 + index / 90)), 0),
                source="mock_seed",
                data_status=fixture_data_status(market.value),
            )
        )

    bar_repository.add_many(bars)
    return len(bars)


def _build_financial(*, stock: Stock, market: MarketCode, symbol: str, seeded_at: datetime) -> Financial:
    """把 Mock fixture 中的盈利能力和现金流指标写成 TTM 基本面记录。"""

    fixture = STOCK_RESEARCH_FIXTURES[market][symbol]
    gross_margin, operating_margin = fixture["profitability"][2], fixture["profitability"][3]
    roe, roic = fixture["profitability"][0], fixture["profitability"][1]
    fcf, operating_cash_flow, capex = fixture["cash_flow"]

    return Financial(
        stock_id=stock.id,
        market=market.value,
        symbol=symbol,
        fiscal_period="TTM",
        period_end_date=seeded_at.date(),
        revenue=None,
        net_income=None,
        gross_margin=Decimal(str(gross_margin)),
        operating_margin=Decimal(str(operating_margin)),
        roe=Decimal(str(roe)),
        roic=Decimal(str(roic)),
        operating_cash_flow=Decimal(str(operating_cash_flow)),
        capex=Decimal(str(capex)),
        fcf=Decimal(str(fcf)),
        source="mock_seed",
    )


def _build_valuation_snapshot(*, stock: Stock, market: MarketCode, symbol: str, seeded_at: datetime) -> ValuationSnapshot:
    """把 Mock fixture 中的估值指标写成某一时点的估值快照。"""

    pe_ttm, pb, ps_ttm, pfcf_ttm = STOCK_RESEARCH_FIXTURES[market][symbol]["valuation"]

    return ValuationSnapshot(
        stock_id=stock.id,
        market=market.value,
        symbol=symbol,
        pe_ttm=Decimal(str(pe_ttm)),
        pb=Decimal(str(pb)),
        ps_ttm=Decimal(str(ps_ttm)),
        pfcf_ttm=Decimal(str(pfcf_ttm)),
        snapshot_timestamp=seeded_at,
        source="mock_seed",
    )


def _build_factor_values(*, stock: Stock, market: MarketCode, symbol: str, seeded_at: datetime) -> list[FactorValue]:
    """运行 Quant Pipeline 并把因子快照写成可落库的因子值。"""

    factors = _run_seed_quant_pipeline(market=market, symbol=symbol).factors
    factor_map = {
        "momentum_20d": factors.momentum_20d,
        "trend_strength": factors.trend_strength,
        "volatility_20d": factors.volatility_20d,
        "quality_score": factors.quality_score,
        "composite_score": factors.composite_score,
    }

    return [
        FactorValue(
            stock_id=stock.id,
            market=market.value,
            symbol=symbol,
            factor_name=factor_name,
            factor_value=None if factor_value is None else Decimal(str(round(factor_value, 8))),
            as_of_date=seeded_at.date(),
            data_status=fixture_data_status(market.value),
            source="mock_seed",
        )
        for factor_name, factor_value in factor_map.items()
    ]


def _build_signals(*, stock: Stock, market: MarketCode, symbol: str, seeded_at: datetime) -> list[Signal]:
    """运行 Quant Pipeline 并把信号输出写成可落库的结构化提示。"""

    return [
        Signal(
            stock_id=stock.id,
            market=market.value,
            symbol=symbol,
            signal_type=signal.code,
            direction=signal.direction.value,
            severity=signal.severity.value,
            score=signal.score,
            evidence=signal.evidence,
            triggered_at=seeded_at,
            source="mock_seed",
        )
        for signal in _run_seed_quant_pipeline(market=market, symbol=symbol).signals
    ]


def _run_seed_quant_pipeline(*, market: MarketCode, symbol: str):
    """用开发 fixture 运行确定性 Quant Pipeline，供因子和信号 seed 复用。"""

    fixture = STOCK_RESEARCH_FIXTURES[market][symbol]
    base_price, daily_step = fixture["kline_seed"]
    closes = [
        float(
            _build_seed_ohlc(
                index=index,
                base_price=Decimal(str(base_price)),
                daily_step=Decimal(str(daily_step)),
            )[3]
        )
        for index in range(40)
    ]
    roe, roic, gross_margin = fixture["profitability"][0], fixture["profitability"][1], fixture["profitability"][2]
    return run_quant_pipeline(
        QuantPipelineInput(
            symbol=symbol,
            closes=closes,
            roe=roe,
            roic=roic,
            gross_margin=gross_margin,
        )
    )


def _build_ai_research_request(market: MarketCode) -> AIResearchRequest:
    """构造开发 Seed 的 AI Research 任务请求，用于本地读取路径演示。"""

    default_symbol = next(iter(STOCK_RESEARCH_FIXTURES[market]))
    query_map = {
        MarketCode.US: "分析 NVDA 今天异动原因",
        MarketCode.HK: "分析港股科技股是否走强",
        MarketCode.CN: "分析 A 股新能源链是否出现机会",
    }
    return AIResearchRequest(
        market=market,
        query=query_map[market],
        symbols=[default_symbol],
        include_strategy_idea=True,
    )


def _build_seed_ohlc(
    *,
    index: int,
    base_price: Decimal,
    daily_step: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """生成可重复但有波动的开发 K 线 OHLC，和 Mock Provider 的演示形态保持一致。"""

    trend_price = base_price + Decimal(index) * daily_step
    step_size = max(abs(daily_step), base_price * Decimal("0.006"))
    cycle_wave = Decimal((index % 7) - 3) * step_size * Decimal("0.42")
    pulse_direction = 1 if index % 11 in {3, 4} else -1 if index % 11 in {8, 9} else 0
    pulse_wave = Decimal(pulse_direction) * step_size * Decimal("1.15")
    open_price = trend_price + cycle_wave * Decimal("0.72") - pulse_wave * Decimal("0.18")
    close_price = trend_price + daily_step * Decimal("0.35") + pulse_wave + cycle_wave * Decimal("0.32")
    wick_size = step_size * (Decimal("0.85") + Decimal(index % 4) * Decimal("0.18"))
    high_price = max(open_price, close_price) + wick_size
    low_price = min(open_price, close_price) - wick_size * Decimal("0.78")

    return open_price, high_price, low_price, close_price


def _build_strategies(*, market: MarketCode, seeded_at: datetime) -> list[Strategy]:
    """把 Strategy Lab Mock 草案转换成可落库的策略主表记录。"""

    lab_snapshot = get_mock_strategy_lab(market)
    strategies: list[Strategy] = []
    for draft in lab_snapshot.drafts:
        strategies.append(
            Strategy(
                strategy_id=draft.strategy_id,
                market=market.value,
                name=draft.name,
                description=draft.description,
                status=draft.status.value,
                created_by=draft.created_by.value,
                current_version=draft.version,
                universe=draft.universe.model_dump(mode="json"),
                entry_conditions=[condition.model_dump(mode="json") for condition in draft.entry_conditions],
                exit_conditions=[condition.model_dump(mode="json") for condition in draft.exit_conditions],
                position_rule=draft.position_rule.model_dump(mode="json"),
                rebalance_frequency=draft.rebalance_frequency.value,
                risk_constraints=[constraint.model_dump(mode="json") for constraint in draft.risk_constraints],
                parameters=draft.parameters,
                created_at=seeded_at,
                updated_at=seeded_at,
            )
        )
    return strategies


if __name__ == "__main__":
    result = seed_development_data()
    print("Seeded development data:")
    for table_name, row_count in result.items():
        print(f"- {table_name}: {row_count}")

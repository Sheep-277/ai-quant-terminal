from datetime import datetime, timedelta, timezone

from app.core.config import DataProviderMode, Settings, get_settings
from app.core.market import MarketCode, get_market_context
from app.providers.base import MarketDataProvider
from app.providers.factory import get_market_data_provider
from app.quant.risk import PositionInput, calculate_portfolio_risk
from app.schemas.market import DataStatus
from app.schemas.portfolio import (
    PaperOrder,
    PaperOrderCreateResponse,
    PaperOrderRequest,
    PaperOrderRiskDecision,
    PaperOrderSide,
    PaperOrderStatus,
    PortfolioAccount,
    PortfolioDataMode,
    PortfolioPosition,
    PortfolioResponse,
    PortfolioRiskSummary,
)
from app.schemas.risk import PreTradeRiskCheckRequest, RiskCheckDecision, RiskPositionInput
from app.services.risk_service import pre_trade_check


PORTFOLIO_FIXTURES = {
    MarketCode.US: {
        "account_id": "paper-us-001",
        "initial_capital": 100_000.0,
        "cash": 18_420.0,
        "daily_pnl": 860.0,
        "positions": [
            ("NVDA", "NVIDIA Corporation", 180, 142.3, 181.42),
            ("MSFT", "Microsoft Corporation", 80, 468.2, 517.66),
            ("AMD", "Advanced Micro Devices", 120, 151.4, 174.02),
        ],
        "risk_flags": ["半导体持仓集中度较高", "当前组合仅为模拟交易账户"],
    },
    MarketCode.HK: {
        "account_id": "paper-hk-001",
        "initial_capital": 100_000.0,
        "cash": 21_300.0,
        "daily_pnl": 420.0,
        "positions": [
            ("00700.HK", "Tencent Holdings", 200, 378.4, 421.6),
            ("09988.HK", "Alibaba Group", 300, 88.1, 96.35),
            ("00005.HK", "HSBC Holdings", 160, 84.7, 92.1),
        ],
        "risk_flags": ["港股小盘股基本面数据可能延迟", "当前组合仅为模拟交易账户"],
    },
    MarketCode.CN: {
        "account_id": "paper-cn-001",
        "initial_capital": 100_000.0,
        "cash": 16_800.0,
        "daily_pnl": -260.0,
        "positions": [
            ("600519.SH", "贵州茅台", 30, 1288.0, 1412.0),
            ("300750.SZ", "宁德时代", 180, 196.5, 214.88),
            ("000001.SZ", "平安银行", 1200, 10.8, 11.42),
        ],
        "risk_flags": ["A 股涨跌停规则可能影响模拟成交", "当前组合仅为模拟交易账户"],
    },
}


def get_portfolio_summary(
    market: MarketCode,
    *,
    settings: Settings | None = None,
    provider: MarketDataProvider | None = None,
) -> PortfolioResponse:
    """生成模拟组合摘要；真实 Provider 可用时用行情快照重估持仓。"""

    resolved_settings = settings or get_settings()
    if resolved_settings.data_provider != DataProviderMode.REAL:
        return get_mock_portfolio_summary(market)

    try:
        return _get_provider_priced_portfolio_summary(
            market=market,
            settings=resolved_settings,
            provider=provider,
        )
    except Exception as error:
        fallback_response = get_mock_portfolio_summary(market)
        return fallback_response.model_copy(
            update={
                "risk": fallback_response.risk.model_copy(
                    update={
                        "risk_flags": [
                            *fallback_response.risk.risk_flags,
                            (
                                "真实持仓行情读取失败，当前页面已回退到 Mock 组合估值；"
                                f"{_format_provider_fallback_reason(error)}"
                            ),
                        ],
                    }
                )
            }
        )


def get_mock_portfolio_summary(market: MarketCode) -> PortfolioResponse:
    """生成模拟组合摘要，当前不读取数据库、不连接真实券商。"""

    context = get_market_context(market)
    fixture = PORTFOLIO_FIXTURES[market]
    timestamp = datetime.now(timezone.utc)
    market_value = _calculate_market_value(fixture["positions"])
    nav = round(fixture["cash"] + market_value, 2)
    total_pnl = round(nav - fixture["initial_capital"], 2)
    positions = _build_positions(
        market=market,
        rows=fixture["positions"],
        nav=nav,
    )
    risk = calculate_portfolio_risk(
        positions=[
            PositionInput(symbol=position.symbol, market_value=position.market_value)
            for position in positions
        ],
        nav=nav,
        cash=fixture["cash"],
    )

    return PortfolioResponse(
        market=market,
        timestamp=timestamp,
        timezone=context.timezone,
        currency=context.currency,
        data_mode=PortfolioDataMode.MOCK,
        account=PortfolioAccount(
            account_id=fixture["account_id"],
            market=market,
            currency=context.currency,
            nav=nav,
            cash=fixture["cash"],
            market_value=market_value,
            daily_pnl=fixture["daily_pnl"],
            total_pnl=total_pnl,
            total_return=total_pnl / fixture["initial_capital"],
            updated_at=timestamp,
        ),
        positions=positions,
        orders=_build_orders(timestamp=timestamp, market=market, positions=positions),
        risk=PortfolioRiskSummary(
            gross_exposure=round(risk.gross_exposure, 4),
            net_exposure=round(risk.net_exposure, 4),
            largest_position_weight=round(risk.largest_position_weight, 4),
            cash_weight=round(risk.cash_weight, 4),
            risk_flags=_build_risk_flags(risk.risk_flags, fixture["risk_flags"]),
        ),
    )


def _get_provider_priced_portfolio_summary(
    *,
    market: MarketCode,
    settings: Settings,
    provider: MarketDataProvider | None,
) -> PortfolioResponse:
    """用真实 Provider quote 更新模拟持仓价格，并重新计算账户和风险摘要。"""

    context = get_market_context(market)
    fixture = PORTFOLIO_FIXTURES[market]
    resolved_provider = provider or get_market_data_provider(settings)
    provider_status = resolved_provider.get_provider_status()
    timestamp = datetime.now(timezone.utc)
    priced_rows: list[tuple[str, str, int, float, float]] = []
    daily_pnl = 0.0

    for symbol, name, quantity, average_cost, _fallback_price in fixture["positions"]:
        quote = resolved_provider.get_quote(market, symbol)
        if quote["data_status"] == DataStatus.UNAVAILABLE:
            source = quote.get("source") or provider_status.get("active_source") or provider_status.get("provider_name") or "unknown"
            raise ValueError(
                f"provider quote unavailable; market={market.value}; symbol={symbol}; "
                f"status={quote['data_status']}; source={source}"
            )
        priced_rows.append((symbol, name, quantity, average_cost, quote["price"]))
        daily_pnl += quote["change"] * quantity

    market_value = _calculate_market_value(priced_rows)
    nav = round(fixture["cash"] + market_value, 2)
    total_pnl = round(nav - fixture["initial_capital"], 2)
    positions = _build_positions(market=market, rows=priced_rows, nav=nav)
    risk = calculate_portfolio_risk(
        positions=[
            PositionInput(symbol=position.symbol, market_value=position.market_value)
            for position in positions
        ],
        nav=nav,
        cash=fixture["cash"],
    )
    source_name = (
        provider_status.get("active_source")
        or provider_status.get("provider_name")
        or settings.real_provider_name
    )

    return PortfolioResponse(
        market=market,
        timestamp=timestamp,
        timezone=context.timezone,
        currency=context.currency,
        data_mode=PortfolioDataMode.PAPER,
        account=PortfolioAccount(
            account_id=fixture["account_id"],
            market=market,
            currency=context.currency,
            nav=nav,
            cash=fixture["cash"],
            market_value=market_value,
            daily_pnl=round(daily_pnl, 2),
            total_pnl=total_pnl,
            total_return=total_pnl / fixture["initial_capital"],
            updated_at=timestamp,
        ),
        positions=positions,
        orders=_build_orders(timestamp=timestamp, market=market, positions=positions),
        risk=PortfolioRiskSummary(
            gross_exposure=round(risk.gross_exposure, 4),
            net_exposure=round(risk.net_exposure, 4),
            largest_position_weight=round(risk.largest_position_weight, 4),
            cash_weight=round(risk.cash_weight, 4),
            risk_flags=_build_risk_flags(
                risk.risk_flags,
                [
                    f"持仓最新价使用 Provider 行情重估，来源={source_name}",
                    "当前组合仍为模拟账户，不连接真实券商账户",
                ],
            ),
        ),
    )


def create_mock_paper_order(request: PaperOrderRequest) -> PaperOrderCreateResponse:
    """创建模拟订单回执，提交前先经过确定性 Risk service。"""

    context = get_market_context(request.market)
    timestamp = datetime.now(timezone.utc)
    risk_check = pre_trade_check(_build_pre_trade_risk_check_request(request=request))

    return PaperOrderCreateResponse(
        order_id=_build_mock_order_id(market=request.market, account_id=request.account_id, symbol=request.symbol),
        account_id=request.account_id,
        market=request.market,
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        limit_price=request.limit_price,
        status=PaperOrderStatus.REJECTED if risk_check.decision == RiskCheckDecision.REJECTED else PaperOrderStatus.SUBMITTED,
        submitted_at=timestamp,
        currency=context.currency,
        risk_checked=risk_check.risk_checked,
        risk_decision=PaperOrderRiskDecision(risk_check.decision.value),
        risk_reason_codes=[reason.code for reason in risk_check.reasons],
        risk_reasons=[reason.message for reason in risk_check.reasons],
    )


def _build_positions(
    market: MarketCode,
    rows: list[tuple[str, str, int, float, float]],
    nav: float,
) -> list[PortfolioPosition]:
    """把紧凑 fixture 转成正式持仓对象，并计算市值、权重和浮动盈亏。"""

    positions: list[PortfolioPosition] = []
    for symbol, name, quantity, average_cost, last_price in rows:
        market_value = round(quantity * last_price, 2)
        unrealized_pnl = round((last_price - average_cost) * quantity, 2)
        positions.append(
            PortfolioPosition(
                market=market,
                symbol=symbol,
                name=name,
                quantity=quantity,
                average_cost=average_cost,
                last_price=last_price,
                market_value=market_value,
                weight=round(market_value / nav, 4),
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_percent=round((last_price - average_cost) / average_cost, 4),
            )
        )

    return positions


def _calculate_market_value(rows: list[tuple[str, str, int, float, float]]) -> float:
    """根据持仓数量和最新价计算组合持仓总市值。"""

    return round(sum(quantity * last_price for _, _, quantity, _, last_price in rows), 2)


def _build_orders(
    timestamp: datetime,
    market: MarketCode,
    positions: list[PortfolioPosition],
) -> list[PaperOrder]:
    """基于当前持仓构造少量模拟订单，强调不会发送到真实券商。"""

    orders: list[PaperOrder] = []
    for index, position in enumerate(positions[:2]):
        submitted_at = timestamp - timedelta(days=index + 1)
        orders.append(
            PaperOrder(
                order_id=f"paper-{market.value.lower()}-{index + 1:03d}",
                market=market,
                symbol=position.symbol,
                side=PaperOrderSide.BUY,
                quantity=max(1, position.quantity // 3),
                limit_price=position.last_price,
                status=PaperOrderStatus.FILLED,
                submitted_at=submitted_at,
                filled_at=submitted_at + timedelta(minutes=3),
            )
        )

    return orders


def _build_risk_flags(
    engine_flags: list[str],
    fixture_flags: list[str],
) -> list[str]:
    """把 Risk Engine 风险码转换成中文提示，并保留市场特有 Mock 提示。"""

    flag_messages = {
        "largest_position_weight_exceeded": "单一持仓权重超过 30% 风险约束",
        "low_cash_weight": "现金权重低于 5%，组合接近满仓",
        "gross_exposure_above_nav": "总敞口超过组合净值，需检查杠杆或空头口径",
    }

    translated_flags = [
        flag_messages[flag]
        for flag in engine_flags
        if flag in flag_messages
    ]
    return translated_flags + fixture_flags


def _format_provider_fallback_reason(error: Exception) -> str:
    """把 Provider 异常转换成页面可读的回退原因，避免只暴露模糊错误类型。"""

    message = str(error).strip()
    if message:
        return f"错误类型={type(error).__name__}；原因={message}。"
    return f"错误类型={type(error).__name__}；原因=Provider 未返回详细错误。"


def _build_pre_trade_risk_check_request(request: PaperOrderRequest) -> PreTradeRiskCheckRequest:
    """基于 Mock 账户快照构造下单前风险检查请求。"""

    fixture = PORTFOLIO_FIXTURES[request.market]
    market_value = _calculate_market_value(fixture["positions"])
    nav = round(fixture["cash"] + market_value, 2)
    positions = _build_positions(market=request.market, rows=fixture["positions"], nav=nav)

    return PreTradeRiskCheckRequest(
        account_id=request.account_id,
        market=request.market,
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        limit_price=request.limit_price,
        nav=nav,
        cash=fixture["cash"],
        current_positions=[
            RiskPositionInput(
                market=position.market,
                symbol=position.symbol,
                market_value=position.market_value,
            )
            for position in positions
        ],
        paper_trading=request.paper_trading,
    )


def _build_mock_order_id(*, market: MarketCode, account_id: str, symbol: str) -> str:
    """根据市场、账户和标的生成稳定 Mock 订单 ID，便于前端调试。"""

    normalized_account = account_id.strip().lower().replace("_", "-").replace(".", "-")
    normalized_symbol = symbol.strip().lower().replace(".", "-")
    return f"paper-{market.value.lower()}-{normalized_account}-{normalized_symbol}-submitted"

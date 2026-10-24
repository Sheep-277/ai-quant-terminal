from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.core.config import DataProviderMode, Settings, get_settings
from app.core.market import MarketCode, get_market_context
from app.providers.base import MarketDataProvider, ProviderBar
from app.providers.factory import get_market_data_provider
from app.quant.backtest import PriceBar, SimulatedTrade, run_buy_and_hold_backtest
from app.schemas.backtest import (
    BacktestDataMode,
    BacktestPerformance,
    BacktestRequest,
    BacktestResponse,
    BacktestStatus,
    BacktestTaskCreateResponse,
    BacktestTrade,
    EquityCurvePoint,
)
from app.schemas.market import DataStatus


BACKTEST_FIXTURES = {
    MarketCode.US: {
        "backtest_id": "mock-us-backtest-001",
        "strategy_id": "mock-us-momentum-quality-v1",
        "start_date": date(2025, 1, 1),
        "end_date": date(2025, 12, 31),
        "initial_capital": 100_000.0,
        "benchmark_return": 0.184,
        "symbol": "NVDA",
        "prices": [100, 104, 108, 106, 112, 118, 116, 121, 126, 124, 129, 132],
    },
    MarketCode.HK: {
        "backtest_id": "mock-hk-backtest-001",
        "strategy_id": "mock-hk-cashflow-value-v1",
        "start_date": date(2025, 1, 1),
        "end_date": date(2025, 12, 31),
        "initial_capital": 100_000.0,
        "benchmark_return": 0.096,
        "symbol": "00700.HK",
        "prices": [100, 102, 101, 104, 107, 106, 109, 111, 110, 113, 115, 116],
    },
    MarketCode.CN: {
        "backtest_id": "mock-cn-backtest-001",
        "strategy_id": "mock-cn-quality-trend-v1",
        "start_date": date(2025, 1, 1),
        "end_date": date(2025, 12, 31),
        "initial_capital": 100_000.0,
        "benchmark_return": 0.121,
        "symbol": "600519.SH",
        "prices": [100, 103, 105, 104, 108, 111, 109, 113, 116, 115, 119, 121],
    },
}


def get_backtest_result(
    market: MarketCode,
    *,
    settings: Settings | None = None,
    provider: MarketDataProvider | None = None,
) -> BacktestResponse:
    """生成回测中心结果；真实 Provider 可用时优先使用历史 K 线，失败时回退 Mock。"""

    resolved_settings = settings or get_settings()
    if resolved_settings.data_provider != DataProviderMode.REAL:
        return get_mock_backtest_result(market)

    try:
        return _get_provider_backtest_result(
            market=market,
            settings=resolved_settings,
            provider=provider,
        )
    except Exception as error:
        fallback_response = get_mock_backtest_result(market)
        return fallback_response.model_copy(
            update={
                "assumptions": [
                    *fallback_response.assumptions,
                    (
                        "真实历史行情读取失败，当前页面已回退到 Mock 回测结果；"
                        f"错误类型={type(error).__name__}。"
                    ),
                ],
            }
        )


def get_mock_backtest_result(market: MarketCode) -> BacktestResponse:
    """使用 Mock 行情运行确定性回测，生成回测中心响应。"""

    context = get_market_context(market)
    fixture = BACKTEST_FIXTURES[market]
    timestamp = datetime.now(timezone.utc)
    backtest = run_buy_and_hold_backtest(
        symbol=fixture["symbol"],
        bars=_build_price_bars(
            start_date=fixture["start_date"],
            prices=fixture["prices"],
        ),
        initial_capital=fixture["initial_capital"],
    )
    performance = backtest.performance
    if performance is None:
        raise ValueError("backtest performance must not be None")

    return BacktestResponse(
        backtest_id=fixture["backtest_id"],
        strategy_id=fixture["strategy_id"],
        market=market,
        status=BacktestStatus.COMPLETED,
        data_mode=BacktestDataMode.MOCK,
        timestamp=timestamp,
        timezone=context.timezone,
        currency=context.currency,
        benchmark=context.benchmark,
        start_date=fixture["start_date"],
        end_date=fixture["end_date"],
        performance=BacktestPerformance(
            initial_capital=performance.initial_capital,
            final_value=performance.final_value,
            total_return=performance.total_return,
            annualized_return=performance.annualized_return or 0,
            benchmark_return=fixture["benchmark_return"],
            maximum_drawdown=performance.maximum_drawdown or 0,
            sharpe_ratio=performance.sharpe_ratio,
            win_rate=performance.win_rate or 0,
            trade_count=performance.trade_count,
        ),
        equity_curve=_build_mock_equity_curve(
            end_timestamp=timestamp,
            equity_curve=backtest.equity_curve,
            benchmark_return=fixture["benchmark_return"],
        ),
        trades=_build_mock_trades(
            market=market,
            trades=backtest.trades,
        ),
        assumptions=[
            f"回测结果为 {context.currency} 计价的 Mock 数据。",
            "交易费用和滑点已在模拟成交记录中显式展示。",
            "当前结果不使用未来数据，也不代表真实可交易收益。",
        ],
    )


def _get_provider_backtest_result(
    *,
    market: MarketCode,
    settings: Settings,
    provider: MarketDataProvider | None,
) -> BacktestResponse:
    """把 Provider 历史 K 线转换为回测输入，并生成可被前端展示的结果。"""

    context = get_market_context(market)
    fixture = BACKTEST_FIXTURES[market]
    resolved_provider = provider or get_market_data_provider(settings)
    provider_status = resolved_provider.get_provider_status()
    provider_bars = resolved_provider.get_bars(
        market,
        fixture["symbol"],
        interval="1d",
        count=120,
        start=fixture["start_date"],
        end=fixture["end_date"],
    )
    if _provider_bars_use_mock_fallback(provider_bars):
        raise ValueError("provider bars came from mock fallback")

    price_bars = _build_price_bars_from_provider(provider_bars)
    backtest = run_buy_and_hold_backtest(
        symbol=fixture["symbol"],
        bars=price_bars,
        initial_capital=fixture["initial_capital"],
    )
    performance = backtest.performance
    if performance is None:
        raise ValueError("backtest performance must not be None")

    timestamp = datetime.now(timezone.utc)
    benchmark_return = fixture["benchmark_return"]
    source_name = provider_status.get("active_source") or provider_status.get("provider_name") or settings.real_provider_name

    return BacktestResponse(
        backtest_id=fixture["backtest_id"].replace("mock", "historical", 1),
        strategy_id=fixture["strategy_id"],
        market=market,
        status=BacktestStatus.COMPLETED,
        data_mode=BacktestDataMode.HISTORICAL,
        timestamp=timestamp,
        timezone=context.timezone,
        currency=context.currency,
        benchmark=context.benchmark,
        start_date=price_bars[0].timestamp,
        end_date=price_bars[-1].timestamp,
        performance=BacktestPerformance(
            initial_capital=performance.initial_capital,
            final_value=performance.final_value,
            total_return=performance.total_return,
            annualized_return=performance.annualized_return or 0,
            benchmark_return=benchmark_return,
            maximum_drawdown=performance.maximum_drawdown or 0,
            sharpe_ratio=performance.sharpe_ratio,
            win_rate=performance.win_rate or 0,
            trade_count=performance.trade_count,
        ),
        equity_curve=_build_equity_curve_from_price_bars(
            price_bars=price_bars,
            equity_curve=backtest.equity_curve,
            benchmark_return=benchmark_return,
        ),
        trades=_build_mock_trades(
            market=market,
            trades=backtest.trades,
        ),
        assumptions=[
            f"回测结果使用 {fixture['symbol']} 的 Provider 历史 K 线，来源={source_name}。",
            "策略逻辑仍为最小买入并持有回测，用于验证真实行情接入链路。",
            "基准收益率当前沿用原型基准参数，后续可接入真实指数历史序列。",
            "交易费用和滑点已在模拟成交记录中显式展示，结果不代表真实可交易收益。",
        ],
    )


def create_backtest_task_receipt(request: BacktestRequest) -> BacktestTaskCreateResponse:
    """创建回测任务接收回执；当前只返回接收状态，不启动异步队列。"""

    context = get_market_context(request.market)
    settings = get_settings()
    backtest_id = _build_backtest_id(market=request.market, strategy_id=request.strategy_id)

    return BacktestTaskCreateResponse(
        backtest_id=backtest_id,
        strategy_id=request.strategy_id,
        market=request.market,
        status=BacktestStatus.PENDING,
        accepted_at=datetime.now(timezone.utc),
        data_mode=request.data_mode,
        timezone=context.timezone,
        currency=context.currency,
        poll_url=f"{settings.api_prefix}/backtests/{backtest_id}",
    )


def _build_mock_equity_curve(
    end_timestamp: datetime,
    equity_curve: list[float],
    benchmark_return: float,
) -> list[EquityCurvePoint]:
    """把 Quant Backtest 生成的权益曲线转换为 API schema。"""

    initial_capital = equity_curve[0]
    points: list[EquityCurvePoint] = []
    peak = initial_capital
    for index, equity in enumerate(equity_curve):
        progress = index / (len(equity_curve) - 1)
        peak = max(peak, equity)
        benchmark_equity = initial_capital * (1 + benchmark_return * progress)
        drawdown = 0 if peak == 0 else (peak - equity) / peak

        points.append(
            EquityCurvePoint(
                timestamp=end_timestamp - timedelta(days=(len(equity_curve) - 1 - index) * 30),
                equity=round(equity, 2),
                benchmark_equity=round(benchmark_equity, 2),
                drawdown=round(drawdown, 4),
            )
        )

    return points


def _build_equity_curve_from_price_bars(
    *,
    price_bars: list[PriceBar],
    equity_curve: list[float],
    benchmark_return: float,
) -> list[EquityCurvePoint]:
    """按真实 K 线日期生成权益曲线点，保留与前端图表一致的时间轴。"""

    initial_capital = equity_curve[0]
    points: list[EquityCurvePoint] = []
    peak = initial_capital
    for index, equity in enumerate(equity_curve):
        progress = index / (len(equity_curve) - 1)
        peak = max(peak, equity)
        benchmark_equity = initial_capital * (1 + benchmark_return * progress)
        drawdown = 0 if peak == 0 else (peak - equity) / peak

        points.append(
            EquityCurvePoint(
                timestamp=datetime.combine(price_bars[index].timestamp, datetime.min.time(), tzinfo=timezone.utc),
                equity=round(equity, 2),
                benchmark_equity=round(benchmark_equity, 2),
                drawdown=round(drawdown, 4),
            )
        )

    return points


def _build_mock_trades(
    market: MarketCode,
    trades: list[SimulatedTrade],
) -> list[BacktestTrade]:
    """把 Quant Backtest 生成的模拟成交转换为 API schema。"""

    return [
        BacktestTrade(
            timestamp=datetime.combine(trade.timestamp, datetime.min.time(), tzinfo=timezone.utc),
            market=market,
            symbol=trade.symbol,
            side=trade.side,
            quantity=trade.quantity,
            price=round(trade.price, 2),
            fee=round(trade.fee, 2),
            slippage=round(trade.slippage, 2),
        )
        for trade in trades
    ]


def _build_backtest_id(*, market: MarketCode, strategy_id: str) -> str:
    """根据市场和策略 ID 生成稳定回测任务 ID，便于前端轮询调试。"""

    normalized_strategy_id = strategy_id.strip().lower().replace("_", "-").replace(".", "-")
    return f"backtest-{market.value.lower()}-{normalized_strategy_id}"


def _build_price_bars(start_date: date, prices: list[float]) -> list[PriceBar]:
    """把 Mock 收盘价转换为最小回测价格数据。"""

    return [
        PriceBar(timestamp=start_date + timedelta(days=index * 30), close=price)
        for index, price in enumerate(prices)
    ]


def _build_price_bars_from_provider(provider_bars: list[ProviderBar]) -> list[PriceBar]:
    """把 Provider K 线转换为回测引擎只需要的日期和收盘价。"""

    price_bars = [
        PriceBar(
            timestamp=_read_provider_bar_date(provider_bar, index),
            close=float(provider_bar["close"]),
        )
        for index, provider_bar in enumerate(provider_bars)
        if float(provider_bar["close"]) > 0
    ]
    price_bars.sort(key=lambda bar: bar.timestamp)

    if len(price_bars) < 2:
        raise ValueError("provider bars must contain at least two valid close prices")

    return price_bars


def _provider_bars_use_mock_fallback(provider_bars: list[ProviderBar]) -> bool:
    """识别真实 Provider 内部回退的 Mock K 线，避免页面误标为历史真实数据。"""

    return any(
        provider_bar.get("source") == "mock_fallback"
        or provider_bar.get("data_status") == DataStatus.UNAVAILABLE
        for provider_bar in provider_bars
    )


def _read_provider_bar_date(provider_bar: ProviderBar, index: int) -> date:
    """读取 Provider K 线日期；缺失时间戳时使用 offset 构造稳定日期。"""

    timestamp: Any = provider_bar.get("timestamp")
    if isinstance(timestamp, datetime):
        return timestamp.date()
    if isinstance(timestamp, str) and timestamp.strip():
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()

    offset = int(provider_bar.get("offset", index))
    return date.today() - timedelta(days=offset)

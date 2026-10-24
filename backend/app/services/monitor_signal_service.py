from dataclasses import dataclass
from datetime import datetime

from app.core.market import MarketCode, get_market_context
from app.providers.base import MarketDataProvider, ProviderBar
from app.quant.pipeline import QuantPipelineInput, QuantPipelineResult, run_quant_pipeline
from app.schemas.market import DataStatus
from app.schemas.stock import KLineBar, KLineInterval, KLineSeries, StockResearchQuery


@dataclass(frozen=True)
class MonitorSignalCalculation:
    """单标的价格信号计算结果；时间取自输入行情，不代表实时推送。"""

    market: MarketCode
    symbol: str
    timezone: str
    currency: str
    source: str
    data_status: DataStatus
    timestamp: datetime
    bar_count: int
    result: QuantPipelineResult


def calculate_monitor_signals(
    market: MarketCode,
    symbol: str,
    *,
    provider: MarketDataProvider,
    observed_at: datetime,
) -> MonitorSignalCalculation:
    """读取公开日 K 线并计算价格信号，不取样例基本面、不回退、不落库。

    observed_at 是调用方本次观察时间，只作未来时间检查，不是历史回放时点。
    当前仅放行项目已接入的 YahooFinance；新增来源须先验证其真实输入合同。
    """

    query = StockResearchQuery(market=market, symbol=symbol)
    if query.symbol is None:
        raise ValueError("monitor calculation requires an explicit symbol")
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must include timezone")

    status = provider.get_provider_status()
    if (
        status["mode"] != "real"
        or not status["ready"]
        or status["fallback_active"]
        or status.get("active_source") != "yahoo_finance"
    ):
        raise ValueError("monitor calculation requires a verified public market provider")

    bars = provider.get_bars(query.market, query.symbol, interval="1d", count=40)
    kline = _validate_public_bars(bars, observed_at=observed_at)
    result = run_quant_pipeline(QuantPipelineInput(
        symbol=query.symbol,
        closes=[bar.close for bar in kline.bars],
    ))
    context = get_market_context(query.market)
    return MonitorSignalCalculation(
        market=query.market,
        symbol=query.symbol,
        timezone=context.timezone,
        currency=context.currency,
        source="yahoo_finance",
        data_status=kline.data_status,
        timestamp=kline.bars[-1].timestamp,
        bar_count=len(kline.bars),
        result=result,
    )


def _validate_public_bars(bars: list[ProviderBar], *, observed_at: datetime) -> KLineSeries:
    """整段校验来源、状态和 OHLCV，不排序、补日期、删坏行或换成 Mock。"""

    if len(bars) < 21:
        raise ValueError("monitor calculation requires at least 21 daily bars")
    if any(bar.get("source") != "yahoo_finance" for bar in bars):
        raise ValueError("monitor bars contain unverified or fallback sources")
    statuses = [DataStatus(bar.get("data_status")) for bar in bars]
    if DataStatus.UNAVAILABLE in statuses:
        raise ValueError("monitor bars are unavailable")
    kline = KLineSeries(
        interval=KLineInterval.ONE_DAY,
        data_status=DataStatus.DELAYED if DataStatus.DELAYED in statuses else DataStatus.REALTIME,
        bars=[KLineBar.model_validate({
            key: bar.get(key) for key in ("timestamp", "open", "high", "low", "close", "volume")
        }) for bar in bars],
    )
    for bar in kline.bars:
        if bar.timestamp.tzinfo is None or bar.timestamp.utcoffset() is None:
            raise ValueError("monitor bar timestamp must include timezone")
        if bar.timestamp > observed_at:
            raise ValueError("monitor bars contain future timestamps")
    return kline

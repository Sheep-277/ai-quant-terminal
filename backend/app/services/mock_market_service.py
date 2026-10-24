from datetime import datetime, timedelta, timezone

from app.core.market import MarketCode, get_market_context
from app.providers.base import ProviderBar, ProviderMarketBreadth, ProviderMarketEvent, ProviderStatus
from app.providers.factory import get_market_data_provider
from app.schemas.market import (
    DataStatus,
    Direction,
    MarketBreadth,
    MarketChartBar,
    MarketEvent,
    MarketEventOrigin,
    MarketIndex,
    MarketOverviewResponse,
    SectorPerformance,
)


MARKET_OVERVIEW_CHART_SYMBOLS: dict[MarketCode, str] = {
    MarketCode.US: "^GSPC",
    MarketCode.HK: "^HSI",
    MarketCode.CN: "000300.SS",
}


def get_mock_market_overview(market: MarketCode) -> MarketOverviewResponse:
    """组装当前 Provider 的市场总览，保留每项来源和原始时间。"""

    context = get_market_context(market)
    market_data_provider = get_market_data_provider()
    data_status = market_data_provider.get_market_data_status(market)
    overview_data = market_data_provider.get_market_overview_data(
        market, MARKET_OVERVIEW_CHART_SYMBOLS[market], interval="1d", count=30,
    )
    indices = overview_data["indices"]
    breadth = market_data_provider.get_market_breadth(market)
    sectors = market_data_provider.get_sector_performance(market)
    provider_events = market_data_provider.get_market_events(market)
    provider_status = market_data_provider.get_provider_status()
    timestamp = datetime.now(timezone.utc)
    chart_bars = _build_market_chart_bars(
        market=market,
        bars=overview_data["bars"],
        timestamp=timestamp,
        default_status=data_status,
        provider_status=provider_status,
    )

    # 这里统一组装 Pydantic Schema，确保 Mock 数据也遵守 API 合同。
    return MarketOverviewResponse(
        market=context.market,
        timestamp=timestamp,
        timezone=context.timezone,
        currency=context.currency,
        benchmark=context.benchmark,
        data_status=data_status,
        indices=[
            MarketIndex(
                name=index["name"],
                symbol=index["symbol"],
                value=index["value"],
                change_percent=index["change_percent"],
                status=index.get("data_status", data_status),
                source=index.get("source", "mock_provider"),
                timestamp=index.get("timestamp"),
            )
            for index in indices
        ],
        breadth=MarketBreadth(
            advancers_percent=breadth["advancers_percent"],
            decliners_percent=breadth["decliners_percent"],
            unchanged_percent=breadth["unchanged_percent"],
            new_highs=breadth["new_highs"],
            new_lows=breadth["new_lows"],
            source=breadth["source"],
            status=breadth["data_status"],
            timestamp=breadth.get("timestamp"),
        ),
        chart_bars=chart_bars,
        sectors=[
            SectorPerformance(
                name=sector["name"],
                change_percent=sector["change_percent"],
                direction=_resolve_direction(sector["change_percent"]),
                source=sector["source"],
                status=sector["data_status"],
                timestamp=sector.get("timestamp"),
            )
            for sector in sectors
        ],
        events=_build_market_events(
            timestamp=timestamp,
            data_status=data_status,
            breadth=breadth,
            provider_events=provider_events,
        ) + [
            MarketEvent(
                timestamp=timestamp,
                source="PROVIDER",
                origin=MarketEventOrigin.SYSTEM,
                title=f"指数 {index['symbol']} 公开报价不可用或尚未覆盖，暂无行情数据。",
                impact="数据状态提示",
                confidence=1.0,
            )
            for index in indices
            if index.get("data_status") == DataStatus.UNAVAILABLE
        ],
    )


def _resolve_direction(change_percent: float) -> Direction:
    """根据涨跌幅统一推导方向，避免 fixture 手工维护方向。"""

    if change_percent > 0:
        return Direction.POSITIVE
    if change_percent < 0:
        return Direction.NEGATIVE
    return Direction.NEUTRAL


def _build_market_chart_bars(
    *,
    market: MarketCode,
    bars: list[ProviderBar],
    timestamp: datetime,
    default_status: DataStatus,
    provider_status: ProviderStatus,
) -> list[MarketChartBar]:
    """把 Provider K 线转换成市场总览图表合同。"""

    source = provider_status.get("active_source") or provider_status.get("source_type") or provider_status["provider_name"]

    return [
        MarketChartBar(
            timestamp=_resolve_bar_timestamp(bar=bar, timestamp=timestamp),
            open=bar["open"],
            high=bar["high"],
            low=bar["low"],
            close=bar["close"],
            volume=bar["volume"],
            data_status=bar.get("data_status", default_status),
            source=bar.get("source", source),
        )
        for bar in bars
    ]


def _resolve_bar_timestamp(*, bar: ProviderBar, timestamp: datetime) -> datetime:
    """真实行情优先使用供应商时间；Mock 无时间时按 offset 生成稳定日期。"""

    raw_timestamp = bar.get("timestamp")
    if isinstance(raw_timestamp, datetime):
        return raw_timestamp
    if isinstance(raw_timestamp, str):
        normalized_value = raw_timestamp.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized_value)

    return timestamp - timedelta(days=bar["offset"])


def _build_market_events(
    timestamp: datetime,
    data_status: DataStatus,
    breadth: ProviderMarketBreadth,
    provider_events: list[ProviderMarketEvent],
) -> list[MarketEvent]:
    """构造市场事件流，统一加入数据状态和市场宽度提示。"""

    events = [
        MarketEvent(
            timestamp=timestamp,
            source=event["source"],
            origin=event["origin"],
            title=event["title"],
            impact=event["impact"],
            confidence=event["confidence"],
        )
        for event in provider_events
    ]
    events.append(_build_breadth_event(timestamp=timestamp, breadth=breadth))

    if data_status == DataStatus.DELAYED:
        events.append(
            MarketEvent(
                timestamp=timestamp,
                source="PROVIDER",
                origin=MarketEventOrigin.SYSTEM,
                title="当前市场行情为延迟数据",
                impact="数据状态提示",
                confidence=1.0,
            )
        )

    return events


def _build_breadth_event(
    timestamp: datetime,
    breadth: ProviderMarketBreadth,
) -> MarketEvent:
    """根据上涨/下跌家数占比生成市场宽度事件。"""

    advancers_percent = breadth["advancers_percent"]
    decliners_percent = breadth["decliners_percent"]
    new_highs = breadth["new_highs"]
    new_lows = breadth["new_lows"]
    if advancers_percent > decliners_percent:
        title = f"上涨家数占比 {advancers_percent:.0%}，市场宽度偏强"
        impact = "广度偏强"
    elif advancers_percent < decliners_percent:
        title = f"下跌家数占比 {decliners_percent:.0%}，市场宽度偏弱"
        impact = "广度偏弱"
    else:
        title = "上涨和下跌家数接近，市场宽度中性"
        impact = "广度中性"

    return MarketEvent(
        timestamp=timestamp,
        source="FAST_PATH",
        origin=MarketEventOrigin.MOCK_SAMPLE,
        title=f"{title}；新高 {new_highs}，新低 {new_lows}",
        impact=impact,
        confidence=0.9,
    )

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.market import MarketCode
from app.db.repositories.latest_quote_repository import LatestQuoteRepository
from app.models.latest_quote import LatestQuote
from app.schemas.market import DataStatus, MarketBreadth, MarketEvent, MarketEventOrigin, MarketIndex, MarketOverviewResponse


def get_market_overview_read_snapshot(
    session: Session,
    market: MarketCode,
    fallback: MarketOverviewResponse,
) -> MarketOverviewResponse | None:
    """分别读取指数和个股快照，防止个股价格被当作指数点位。"""

    quotes = LatestQuoteRepository(session).list_by_market(market.value)
    if not quotes:
        return None

    timestamp = max(quote.quote_timestamp for quote in quotes).replace(tzinfo=timezone.utc)
    data_status = _resolve_data_status(quotes)
    index_symbols = {index.symbol for index in fallback.indices}
    index_quotes = {quote.symbol: quote for quote in quotes if quote.symbol in index_symbols}
    stock_quotes = [quote for quote in quotes if quote.symbol not in index_symbols]
    # 指数名称和顺序由 Provider 定义，本地数据只能覆盖同代码指数。
    indices = [
        _quote_to_index(index_quotes[index.symbol], index)
        if index.symbol in index_quotes
        else index
        for index in fallback.indices
    ]
    retained_index_count = len(fallback.indices) - len(index_quotes)
    index_note = (
        f"；{retained_index_count} 条指数沿用 Provider 列表，来源与时间见各指数标注"
        if retained_index_count
        else ""
    )
    return fallback.model_copy(
        update={
            "timestamp": timestamp,
            "data_status": data_status,
            "indices": indices,
            "breadth": _build_breadth(stock_quotes, timestamp=timestamp, data_status=data_status)
            if stock_quotes
            else fallback.breadth,
            "events": [
                MarketEvent(
                    timestamp=timestamp,
                    source="DATABASE",
                    origin=MarketEventOrigin.SYSTEM,
                    title=(
                        f"市场总览已读取 {len(quotes)} 条本地最新行情；"
                        f"同代码指数 {len(index_quotes)} 条，个股 {len(stock_quotes)} 条参与股票池宽度统计"
                        f"{index_note}；个股价格不作为指数点位"
                    ),
                    impact="数据库行情",
                    confidence=1.0,
                ),
                *fallback.events,
            ],
        }
    )


def _quote_to_index(quote: LatestQuote, index: MarketIndex) -> MarketIndex:
    """用同代码行情更新已有指数，保留指数名称及其自身数据状态。"""

    return MarketIndex(
        name=index.name,
        symbol=index.symbol,
        value=float(quote.price),
        change_percent=float(quote.change_percent),
        status=DataStatus(quote.data_status),
        source=quote.source,
        timestamp=quote.quote_timestamp.replace(tzinfo=timezone.utc),
    )


def _build_breadth(
    quotes: list[LatestQuote],
    *,
    timestamp: datetime,
    data_status: DataStatus,
) -> MarketBreadth:
    """根据本地行情涨跌数量计算市场宽度。"""

    total = len(quotes)
    advancers = sum(1 for quote in quotes if quote.change_percent > 0)
    decliners = sum(1 for quote in quotes if quote.change_percent < 0)
    unchanged = total - advancers - decliners
    return MarketBreadth(
        advancers_percent=advancers / total,
        decliners_percent=decliners / total,
        unchanged_percent=unchanged / total,
        new_highs=sum(1 for quote in quotes if quote.change_percent >= Decimal("0.015")),
        new_lows=sum(1 for quote in quotes if quote.change_percent <= Decimal("-0.015")),
        source="database",
        status=data_status,
        timestamp=timestamp,
    )


def _resolve_data_status(quotes: list[LatestQuote]) -> DataStatus:
    """汇总当前市场本地行情的数据状态。"""

    statuses = {quote.data_status for quote in quotes}
    if DataStatus.REALTIME.value in statuses:
        return DataStatus.REALTIME
    if DataStatus.DELAYED.value in statuses:
        return DataStatus.DELAYED
    return DataStatus.UNAVAILABLE

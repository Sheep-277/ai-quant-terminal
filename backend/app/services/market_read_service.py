from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.market import MarketCode, get_market_context
from app.db.repositories.latest_quote_repository import LatestQuoteRepository
from app.db.repositories.stock_repository import StockRepository
from app.models.latest_quote import LatestQuote
from app.models.stock import Stock
from app.schemas.market import DataStatus, MarketBreadth, MarketEvent, MarketEventOrigin, MarketIndex, MarketOverviewResponse
from app.schemas.market import MarketWatchlistQuote


def get_market_overview_read_snapshot(
    session: Session,
    market: MarketCode,
    fallback: MarketOverviewResponse,
) -> MarketOverviewResponse | None:
    """分别读取指数和个股快照，防止个股价格被当作指数点位。"""

    quotes = LatestQuoteRepository(session).list_by_market(market.value)
    index_symbols = {index.symbol for index in fallback.indices}
    stocks = [stock for stock in StockRepository(session).list_by_market(market.value)
              if stock.asset_type == "common_stock" and stock.symbol not in index_symbols]
    watchlist = _build_watchlist(stocks, quotes, market)
    if not quotes:
        # 数据库已读取但报价为空，不能让前端把它误认为未接入并回填样例。
        return fallback.model_copy(update={"watchlist": watchlist, "breadth": _build_breadth([], market)})

    timestamp = max(quote.quote_timestamp for quote in quotes).replace(tzinfo=timezone.utc)
    data_status = _resolve_data_status(quotes)
    index_quotes = {quote.symbol: quote for quote in quotes if quote.symbol in index_symbols}
    stock_quotes = [quote for quote in quotes if quote.symbol not in index_symbols]
    stock_ids = {stock.symbol: stock.id for stock in stocks}
    pool_quotes = [quote for quote in stock_quotes if stock_ids.get(quote.symbol) == quote.stock_id]
    breadth = _build_breadth(pool_quotes, market)
    breadth = breadth.model_copy(update={
        "excluded_sample_size": breadth.excluded_sample_size + len(stock_quotes) - len(pool_quotes),
    })
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
            "breadth": breadth,
            "watchlist": watchlist,
            "events": [
                MarketEvent(
                    timestamp=timestamp,
                    source="DATABASE",
                    origin=MarketEventOrigin.SYSTEM,
                    title=(
                        f"市场总览已读取 {len(quotes)} 条本地最新行情；"
                        f"同代码指数 {len(index_quotes)} 条，个股 {breadth.sample_size} 条参与股票池宽度统计"
                        f"，排除 {breadth.excluded_sample_size} 条样例、无效或其他交易日记录"
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
    market: MarketCode,
) -> MarketBreadth:
    """只统计同一市场最新可用交易日的非样例个股，不推断全市场宽度。"""

    now = datetime.now(timezone.utc)
    eligible = [quote for quote in quotes if _is_usable_real_quote(quote, now)]
    local_zone = ZoneInfo(get_market_context(market).timezone)
    latest_day = max((_quote_time(quote).astimezone(local_zone).date() for quote in eligible), default=None)
    selected = [quote for quote in eligible if _quote_time(quote).astimezone(local_zone).date() == latest_day]
    total = len(selected)
    sample_timestamp = max((_quote_time(quote) for quote in selected), default=None)
    advancers = sum(1 for quote in selected if quote.change_percent > 0)
    decliners = sum(1 for quote in selected if quote.change_percent < 0)
    unchanged = total - advancers - decliners
    # 最差状态决定整组状态，历史快照不因原始标记为 realtime 而冒充当前实时。
    today = now.astimezone(local_zone).date()
    status = DataStatus.UNAVAILABLE if not total else (
        DataStatus.REALTIME if latest_day == today and all(quote.data_status == "realtime" for quote in selected)
        else DataStatus.DELAYED
    )
    return MarketBreadth(
        advancers_percent=advancers / total if total else None,
        decliners_percent=decliners / total if total else None,
        unchanged_percent=unchanged / total if total else None,
        # latest_quotes 没有比较窗口或历史高低价，不能用当日涨跌幅替代新高/新低。
        new_highs=None,
        new_lows=None,
        source="database",
        status=status,
        timestamp=sample_timestamp,
        sample_size=total,
        sample_sources=sorted({quote.source for quote in selected}),
        excluded_sample_size=len(quotes) - total,
    )


def _quote_time(quote: LatestQuote) -> datetime:
    """数据库无时区时间按既有 UTC 存储约定解释，已有时区则转换而非覆盖。"""
    instant = quote.quote_timestamp
    return instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant.astimezone(timezone.utc)


def _is_usable_real_quote(quote: LatestQuote, now: datetime) -> bool:
    """报价列表和宽度共用来源、价格、状态和非未来时间判定。"""
    return bool(
        quote.source.strip() and not quote.source.strip().lower().startswith(("mock", "demo", "seed"))
        and quote.data_status in (DataStatus.REALTIME.value, DataStatus.DELAYED.value)
        and quote.price.is_finite() and quote.price > 0 and quote.change_percent.is_finite()
        and _quote_time(quote) <= now
    )


def _build_watchlist(stocks: list[Stock], quotes: list[LatestQuote], market: MarketCode) -> list[MarketWatchlistQuote]:
    """按主数据补齐股票身份，一次查询的报价按代码匹配，避免逐行查询或读取其他市场。"""
    now = datetime.now(timezone.utc)
    local_zone = ZoneInfo(get_market_context(market).timezone)
    by_symbol = {quote.symbol: quote for quote in quotes if quote.market == market.value}
    rows: list[MarketWatchlistQuote] = []
    for stock in stocks:
        quote = by_symbol.get(stock.symbol)
        if quote is not None and quote.stock_id != stock.id:
            quote = None
        usable = quote is not None and _is_usable_real_quote(quote, now)
        timestamp = _quote_time(quote) if usable else None
        status = DataStatus.UNAVAILABLE
        if usable:
            status = DataStatus.DELAYED if timestamp.astimezone(local_zone).date() < now.astimezone(local_zone).date() else DataStatus(quote.data_status)
        rows.append(MarketWatchlistQuote(
            market=market, symbol=stock.symbol, name=stock.name, currency=stock.currency, timezone=stock.timezone,
            price=float(quote.price) if usable else None,
            change_amount=float(quote.change_amount) if usable and quote.change_amount.is_finite() else None,
            change_percent=float(quote.change_percent) if usable else None,
            volume=quote.volume if usable and quote.volume >= 0 else None,
            turnover=float(quote.turnover) if usable and quote.turnover.is_finite() and quote.turnover >= 0 else None,
            source=quote.source if quote is not None else "database", status=status, timestamp=timestamp,
        ))
    return rows


def _resolve_data_status(quotes: list[LatestQuote]) -> DataStatus:
    """汇总当前市场本地行情的数据状态。"""

    statuses = {quote.data_status for quote in quotes}
    if DataStatus.REALTIME.value in statuses:
        return DataStatus.REALTIME
    if DataStatus.DELAYED.value in statuses:
        return DataStatus.DELAYED
    return DataStatus.UNAVAILABLE

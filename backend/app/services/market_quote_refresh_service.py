from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal, TypedDict

from sqlalchemy.orm import Session

from app.core.exceptions import ProviderError, ProviderUnavailableError
from app.core.market import MarketCode
from app.db.repositories.latest_quote_repository import LatestQuoteRepository
from app.db.repositories.stock_repository import StockRepository
from app.models.latest_quote import LatestQuote
from app.models.stock import Stock
from app.providers.base import MarketDataProvider, ProviderQuote
from app.schemas.market import DataStatus


class QuoteRefreshItem(TypedDict):
    """单只股票刷新结果，不包含密钥、连接字符串或原始供应商异常。"""

    symbol: str
    status: Literal["updated", "would_update", "skipped", "failed"]
    reason: str | None


class MarketQuoteRefreshReport(TypedDict):
    """本次明确市场的股票池刷新报告，预览不等同于已提交。"""

    market: str
    dry_run: bool
    items: list[QuoteRefreshItem]


def refresh_market_quotes(
    session: Session,
    market: MarketCode,
    provider: MarketDataProvider,
    *,
    dry_run: bool = True,
    now: datetime | None = None,
) -> MarketQuoteRefreshReport:
    """顺序刷新启用的普通股；事务提交由调用方负责，不新增股票或重试。"""
    _real_source(provider)
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.utcoffset() is None:
        raise ValueError("Refresh clock must include timezone.")
    repository = LatestQuoteRepository(session)
    stocks = StockRepository(session).list_by_market(market.value)
    items: list[QuoteRefreshItem] = []
    for stock in stocks:
        if stock.asset_type != "common_stock":
            continue
        try:
            quote = provider.get_quote(market, stock.symbol)
            source = _real_source(provider)
        except (ProviderError, OSError, ValueError):
            items.append({"symbol": stock.symbol, "status": "failed", "reason": "provider_read_failed"})
            continue
        try:
            record = _quote_record(stock, quote, source=source, now=checked_at)
        except (ValueError, InvalidOperation, OverflowError, TypeError, KeyError):
            items.append({"symbol": stock.symbol, "status": "skipped", "reason": "invalid_or_unavailable_quote"})
            continue
        existing = repository.get_by_market_symbol(market.value, stock.symbol)
        # seed 的创建时间不是行情时间；可被真实旧收盘替换。真实记录则禁止时间倒退。
        if existing is not None and not existing.source.lower().startswith(("mock", "demo", "seed")):
            previous_time = existing.quote_timestamp
            if previous_time.utcoffset() is not None:
                previous_time = previous_time.astimezone(timezone.utc).replace(tzinfo=None)
            if record.quote_timestamp < previous_time:
                items.append({"symbol": stock.symbol, "status": "skipped", "reason": "older_than_saved_quote"})
                continue
        if not dry_run:
            repository.save_latest(record)
        items.append({"symbol": stock.symbol, "status": "would_update" if dry_run else "updated", "reason": None})
    return {"market": market.value, "dry_run": dry_run, "items": items}


def _real_source(provider: MarketDataProvider) -> str:
    """来源从已就绪的真实 Provider 获取，不把 Demo 或 Mock 以真实来源入库。"""
    status = provider.get_provider_status()
    source = (status.get("active_source") or "").strip()
    if (status["mode"] != "real" or not status["ready"] or status["fallback_active"]
            or not source or len(source) > 64 or source.lower().startswith(("mock", "demo", "seed", "real_placeholder"))):
        raise ProviderUnavailableError("A ready real provider is required.")
    return source


def _decimal_field(value: object, *, scale: int, bound: int) -> Decimal:
    """校验有限十进制值和数据库精度，禁止 NaN、布尔值及溢出写入。"""
    if isinstance(value, bool):
        raise ValueError("Boolean quote value.")
    number = Decimal(str(value))
    if not number.is_finite() or abs(number) >= Decimal(10) ** bound:
        raise ValueError("Invalid quote numeric range.")
    rounded = number.quantize(Decimal(1).scaleb(-scale))
    if abs(rounded) >= Decimal(10) ** bound:
        raise ValueError("Rounded quote exceeds column precision.")
    return rounded


def _quote_record(stock: Stock, quote: ProviderQuote, *, source: str, now: datetime) -> LatestQuote:
    """保留供应商时间，按既有约定以无时区 UTC 写入 MySQL DateTime。"""
    timestamp = quote.get("timestamp")
    if (quote["data_status"] not in (DataStatus.REALTIME, DataStatus.DELAYED)
            or not isinstance(timestamp, datetime) or timestamp.utcoffset() is None or timestamp > now):
        raise ValueError("Unavailable quote or invalid provider time.")
    price = _decimal_field(quote["price"], scale=6, bound=14)
    change = _decimal_field(quote["change"], scale=6, bound=14)
    percent = _decimal_field(quote["change_percent"], scale=8, bound=4)
    turnover = _decimal_field(quote["turnover"], scale=4, bound=20)
    volume = quote["volume"]
    if price <= 0 or turnover < 0 or isinstance(volume, bool) or not isinstance(volume, int) or not 0 <= volume < 2**63:
        raise ValueError("Invalid price, turnover or volume.")
    return LatestQuote(
        stock_id=stock.id, market=stock.market, symbol=stock.symbol,
        price=price, change_amount=change, change_percent=percent, volume=volume, turnover=turnover,
        source=source, data_status=quote["data_status"],
        quote_timestamp=timestamp.astimezone(timezone.utc).replace(tzinfo=None),
    )

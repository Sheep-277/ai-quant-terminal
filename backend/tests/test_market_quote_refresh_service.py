from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import ProviderUnavailableError
from app.core.market import MarketCode, get_market_context
from app.db.repositories.latest_quote_repository import LatestQuoteRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.latest_quote import LatestQuote
from app.models.stock import Stock
from app.providers.base import MarketDataProvider
from app.services.market_quote_refresh_service import refresh_market_quotes
from app.services.market_read_service import _build_breadth


NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
QUOTE_TIME = datetime(2026, 10, 26, 7, tzinfo=timezone.utc)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Stock.__table__, LatestQuote.__table__])
    with create_session_factory(engine)() as session:
        yield session
    engine.dispose()


def add_stock(session: Session, market: MarketCode = MarketCode.CN, symbol: str = "600519.SH", **fields: object) -> Stock:
    context = get_market_context(market)
    stock = Stock(market=market.value, symbol=symbol, name=symbol, exchange="TEST",
                  currency=context.currency, timezone=context.timezone, **fields)
    session.add(stock)
    session.flush()
    return stock


@pytest.fixture
def provider() -> Mock:
    fake = Mock(spec=MarketDataProvider)
    fake.get_provider_status.return_value = {
        "provider_name": "YahooFinance", "mode": "real", "ready": True,
        "data_status": "delayed", "fallback_active": False, "fallback_reason": None,
        "active_source": "yahoo_finance",
    }
    fake.get_quote.side_effect = lambda *_args: {
        "price": 100.25, "change": 1.25, "change_percent": 0.01262626,
        "volume": 1000, "turnover": 100250.0, "data_status": "delayed", "timestamp": QUOTE_TIME,
    }
    return fake


def save_quote(session: Session, stock: Stock, *, when: datetime, source: str) -> None:
    LatestQuoteRepository(session).save_latest(LatestQuote(
        stock_id=stock.id, market=stock.market, symbol=stock.symbol, price=Decimal("88"),
        change_amount=Decimal("0"), change_percent=Decimal("0"), volume=1, turnover=Decimal("88"),
        source=source, data_status="delayed", quote_timestamp=when,
    ))
    session.commit()


def test_preview_never_writes_and_market_is_explicit(session: Session, provider: Mock) -> None:
    add_stock(session)
    add_stock(session, MarketCode.US, "NVDA")
    report = refresh_market_quotes(session, MarketCode.CN, provider, now=NOW)
    assert report["dry_run"] is True
    assert report["items"] == [{"symbol": "600519.SH", "status": "would_update", "reason": None}]
    assert LatestQuoteRepository(session).list_by_market("CN") == []
    provider.get_quote.assert_called_once_with(MarketCode.CN, "600519.SH")


def test_apply_replaces_seed_with_provider_time_and_feeds_real_breadth(session: Session, provider: Mock) -> None:
    stock = add_stock(session)
    # seed 的较新创建时间不能阻止较旧但真实的收盘报价进入本地股票池。
    save_quote(session, stock, when=NOW.replace(tzinfo=None), source="mock_seed")
    report = refresh_market_quotes(session, MarketCode.CN, provider, dry_run=False, now=NOW)
    session.commit()
    quote = LatestQuoteRepository(session).get_by_market_symbol("CN", stock.symbol)
    assert report["items"][0]["status"] == "updated"
    assert quote is not None
    assert quote.source == "yahoo_finance"
    assert quote.quote_timestamp == QUOTE_TIME.replace(tzinfo=None)
    assert quote.price == Decimal("100.250000")
    breadth = _build_breadth([quote], MarketCode.CN)
    assert breadth.sample_size == 1
    assert breadth.advancers_percent == 1
    assert breadth.sample_sources == ["yahoo_finance"]
    assert breadth.new_highs is None
    refresh_market_quotes(session, MarketCode.CN, provider, dry_run=False, now=NOW)
    session.commit()
    assert len(LatestQuoteRepository(session).list_by_market("CN")) == 1


def test_older_public_quote_does_not_overwrite_newer_saved_quote(session: Session, provider: Mock) -> None:
    stock = add_stock(session)
    save_quote(session, stock, when=NOW.replace(tzinfo=None), source="yahoo_finance")
    report = refresh_market_quotes(session, MarketCode.CN, provider, dry_run=False, now=NOW)
    assert report["items"][0]["reason"] == "older_than_saved_quote"
    assert LatestQuoteRepository(session).get_by_market_symbol("CN", stock.symbol).price == Decimal("88")


@pytest.mark.parametrize("field,value", [
    ("data_status", "unavailable"), ("timestamp", None),
    ("timestamp", datetime(2026, 10, 26, 7)),
    ("timestamp", datetime(2999, 1, 1, tzinfo=timezone.utc)),
    ("price", float("nan")), ("price", float("inf")), ("price", 0), ("price", True),
    ("price", 1e14), ("price", 0.0000001), ("change", float("inf")),
    ("change_percent", float("nan")), ("volume", -1), ("volume", True),
    ("volume", 1.2), ("volume", 2**63), ("turnover", -1), ("turnover", 1e20),
])
def test_bad_quotes_leave_seed_untouched(session: Session, provider: Mock, field: str, value: object) -> None:
    stock = add_stock(session)
    save_quote(session, stock, when=NOW.replace(tzinfo=None), source="mock_seed")
    quote = provider.get_quote(MarketCode.CN, stock.symbol)
    quote[field] = value
    provider.get_quote.side_effect = lambda *_args: quote
    report = refresh_market_quotes(session, MarketCode.CN, provider, dry_run=False, now=NOW)
    assert report["items"][0]["status"] == "skipped"
    assert LatestQuoteRepository(session).get_by_market_symbol("CN", stock.symbol).source == "mock_seed"


@pytest.mark.parametrize("source,mode,ready,fallback", [
    ("mock_provider", "mock", True, False), ("demo_provider", "real", True, False),
    ("yahoo_finance", "real", False, False), ("yahoo_finance", "real", True, True),
    ("", "real", True, False),
])
def test_non_real_or_unready_provider_is_rejected_before_fetch(
    session: Session, provider: Mock, source: str, mode: str, ready: bool, fallback: bool,
) -> None:
    provider.get_provider_status.return_value.update(active_source=source, mode=mode, ready=ready, fallback_active=fallback)
    with pytest.raises(ProviderUnavailableError):
        refresh_market_quotes(session, MarketCode.CN, provider, now=NOW)
    provider.get_quote.assert_not_called()


def test_one_failed_symbol_does_not_stop_other_stocks_or_expose_error(session: Session, provider: Mock) -> None:
    add_stock(session, symbol="300750.SZ")
    add_stock(session, symbol="600519.SH")
    good = provider.get_quote(MarketCode.CN, "600519.SH")
    provider.get_quote.side_effect = [TimeoutError("private-secret"), good]
    report = refresh_market_quotes(session, MarketCode.CN, provider, dry_run=False, now=NOW)
    session.commit()
    assert [item["status"] for item in report["items"]] == ["failed", "updated"]
    assert "private-secret" not in str(report)
    assert len(LatestQuoteRepository(session).list_by_market("CN")) == 1


def test_inactive_stocks_and_non_stock_assets_are_not_fetched(session: Session, provider: Mock) -> None:
    add_stock(session, symbol="600519.SH", is_active=False)
    add_stock(session, symbol="000300.SH", asset_type="index")
    report = refresh_market_quotes(session, MarketCode.CN, provider, now=NOW)
    assert report["items"] == []
    provider.get_quote.assert_not_called()


def test_caller_can_rollback_entire_refresh(session: Session, provider: Mock) -> None:
    stock = add_stock(session)
    save_quote(session, stock, when=NOW.replace(tzinfo=None), source="mock_seed")
    refresh_market_quotes(session, MarketCode.CN, provider, dry_run=False, now=NOW)
    session.rollback()
    assert LatestQuoteRepository(session).get_by_market_symbol("CN", stock.symbol).source == "mock_seed"

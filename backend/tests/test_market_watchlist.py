from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.market import MarketCode, get_market_context
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.latest_quote import LatestQuote
from app.models.stock import Stock
from app.providers.market_data import MockMarketDataProvider
from app.schemas.market import MarketWatchlistQuote
from app.services.market_read_service import get_market_overview_read_snapshot
from app.services.mock_market_service import get_mock_market_overview


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    monkeypatch.setattr("app.services.mock_market_service.get_market_data_provider", lambda: MockMarketDataProvider())
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Stock.__table__, LatestQuote.__table__])
    with create_session_factory(engine)() as session:
        yield session
    engine.dispose()


def add_stock(session: Session, market: MarketCode, symbol: str, **fields: object) -> Stock:
    context = get_market_context(market)
    stock = Stock(market=market.value, symbol=symbol, name=f"{symbol} Company", exchange="TEST",
                  currency=context.currency, timezone=context.timezone, **fields)
    session.add(stock)
    session.flush()
    return stock


def add_quote(session: Session, stock: Stock, *, source: str = "yahoo_finance", status: str = "delayed") -> LatestQuote:
    quote = LatestQuote(stock_id=stock.id, market=stock.market, symbol=stock.symbol,
                        price=Decimal("100.25"), change_amount=Decimal("0"), change_percent=Decimal("0"),
                        volume=0, turnover=Decimal("0"), source=source, data_status=status,
                        quote_timestamp=datetime(2026, 10, 20, 7))
    session.add(quote)
    session.flush()
    return quote


@pytest.mark.parametrize("market,symbol", [(MarketCode.US, "NVDA"), (MarketCode.HK, "00700.HK"), (MarketCode.CN, "600519.SH")])
def test_watchlist_preserves_market_identity_real_quote_and_genuine_zeros(session: Session, market: MarketCode, symbol: str) -> None:
    stock = add_stock(session, market, symbol)
    add_quote(session, stock)
    other_market = MarketCode.US if market != MarketCode.US else MarketCode.HK
    add_quote(session, add_stock(session, other_market, "OTHER"))
    snapshot = get_market_overview_read_snapshot(session, market, get_mock_market_overview(market))
    assert snapshot is not None and snapshot.watchlist is not None
    assert len(snapshot.watchlist) == 1
    row = snapshot.watchlist[0]
    assert row.market == market and row.symbol == symbol
    assert row.name == stock.name and row.currency == stock.currency and row.timezone == stock.timezone
    assert row.price == 100.25 and row.change_percent == 0
    assert row.volume == row.turnover == row.change_amount == 0
    assert row.source == "yahoo_finance" and row.status == "delayed"
    assert row.timestamp.isoformat() == "2026-10-20T07:00:00+00:00"
    assert "signal" not in row.model_dump() and "risk" not in row.model_dump()


@pytest.mark.parametrize("source,status", [("mock_seed", "delayed"), ("mock_fallback", "unavailable"),
    ("demo_provider", "realtime"), ("yahoo_finance", "unavailable")])
def test_unusable_quotes_keep_identity_but_not_sample_prices(session: Session, source: str, status: str) -> None:
    add_quote(session, add_stock(session, MarketCode.US, "NVDA"), source=source, status=status)
    snapshot = get_market_overview_read_snapshot(session, MarketCode.US, get_mock_market_overview(MarketCode.US))
    row = snapshot.watchlist[0]
    assert row.symbol == "NVDA" and row.source == source
    assert row.status == "unavailable" and row.timestamp is None
    assert all(getattr(row, field) is None for field in ("price", "change_amount", "change_percent", "volume", "turnover"))


def test_stock_without_quote_has_explicit_missing_values(session: Session) -> None:
    add_stock(session, MarketCode.US, "NVDA")
    snapshot = get_market_overview_read_snapshot(session, MarketCode.US, get_mock_market_overview(MarketCode.US))
    assert len(snapshot.watchlist) == 1
    assert snapshot.watchlist[0].status == "unavailable"
    assert snapshot.watchlist[0].price is None
    assert snapshot.watchlist[0].source == "database"


def test_inactive_and_non_stock_assets_are_excluded_and_pool_is_sorted(session: Session) -> None:
    for symbol, fields in [("NVDA", {}), ("AAPL", {}), ("SPX", {}),
                           ("DISABLED", {"is_active": False}), ("ETF", {"asset_type": "etf"})]:
        add_quote(session, add_stock(session, MarketCode.US, symbol, **fields))
    snapshot = get_market_overview_read_snapshot(session, MarketCode.US, get_mock_market_overview(MarketCode.US))
    assert [row.symbol for row in snapshot.watchlist] == ["AAPL", "NVDA"]
    assert snapshot.breadth.sample_size == 2
    assert snapshot.breadth.excluded_sample_size == 2


def test_old_realtime_mark_is_downgraded_and_future_quote_is_missing(session: Session) -> None:
    add_quote(session, add_stock(session, MarketCode.US, "OLD"), status="realtime")
    future = add_quote(session, add_stock(session, MarketCode.US, "FUTURE"))
    future.quote_timestamp = datetime(2999, 1, 1)
    session.flush()
    snapshot = get_market_overview_read_snapshot(session, MarketCode.US, get_mock_market_overview(MarketCode.US))
    rows = {row.symbol: row for row in snapshot.watchlist}
    assert rows["OLD"].status == "delayed" and rows["OLD"].price == 100.25
    assert rows["FUTURE"].status == "unavailable" and rows["FUTURE"].price is None


def test_quote_with_wrong_stock_id_is_not_attached_to_same_symbol(session: Session) -> None:
    stock = add_stock(session, MarketCode.US, "NVDA")
    other = add_stock(session, MarketCode.US, "AAPL")
    quote = add_quote(session, stock)
    quote.stock_id = other.id
    session.flush()
    snapshot = get_market_overview_read_snapshot(session, MarketCode.US, get_mock_market_overview(MarketCode.US))
    assert all(row.price is None for row in snapshot.watchlist)
    assert snapshot.breadth.sample_size == 0


def test_watchlist_uses_two_bulk_reads_without_per_stock_queries(session: Session) -> None:
    for symbol in ("AAPL", "NVDA", "MSFT"):
        add_quote(session, add_stock(session, MarketCode.US, symbol))
    session.commit()
    session.expire_all()
    selects: list[str] = []

    def capture(_connection: object, _cursor: object, statement: str, _parameters: object, _context: object, _many: bool) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    event.listen(session.bind, "before_cursor_execute", capture)
    try:
        snapshot = get_market_overview_read_snapshot(session, MarketCode.US, get_mock_market_overview(MarketCode.US))
    finally:
        event.remove(session.bind, "before_cursor_execute", capture)
    assert len(snapshot.watchlist) == 3
    assert len(selects) == 2


def test_default_contract_distinguishes_disconnected_and_empty_local_pool(session: Session) -> None:
    fallback = get_mock_market_overview(MarketCode.US)
    assert fallback.watchlist is None
    snapshot = get_market_overview_read_snapshot(session, MarketCode.US, fallback)
    assert snapshot.watchlist == []
    assert snapshot.chart_bars == fallback.chart_bars
    assert snapshot.indices == fallback.indices


def test_watchlist_schema_rejects_non_finite_numbers() -> None:
    with pytest.raises(ValidationError):
        MarketWatchlistQuote(market="US", symbol="NVDA", name="NVIDIA", currency="USD", timezone="America/New_York",
                            price=float("nan"), change_amount=0, change_percent=0, volume=0, turnover=0,
                            source="yahoo_finance", status="delayed", timestamp=None)

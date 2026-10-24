from datetime import datetime
from decimal import Decimal

from app.core.market import MarketCode
from app.db.repositories.latest_quote_repository import LatestQuoteRepository
from app.db.seed import seed_development_data
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.latest_quote import LatestQuote
from app.models.stock import Stock
from app.services.stock_read_service import get_stock_read_snapshot


def _create_test_session():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return engine, create_session_factory(engine)()


def test_stock_read_service_prefers_database_snapshot() -> None:
    engine, session = _create_test_session()
    seed_development_data(engine, timestamp=datetime(2026, 9, 28, 10, 30, 0))

    snapshot = get_stock_read_snapshot(session, MarketCode.US, " nvda ")

    assert snapshot.source == "database"
    assert snapshot.profile.symbol == "NVDA"
    assert snapshot.profile.name == "NVIDIA Corporation"
    assert snapshot.quote.price == 181.42
    assert snapshot.quote.timestamp == datetime(2026, 9, 28, 10, 30, 0)

    session.close()


def test_stock_read_service_falls_back_when_database_is_empty() -> None:
    _, session = _create_test_session()

    snapshot = get_stock_read_snapshot(session, MarketCode.US, "AAPL")

    assert snapshot.source == "mock_provider"
    assert snapshot.profile.symbol == "AAPL"
    assert snapshot.profile.name == "Apple Inc."
    assert snapshot.quote.price == 232.18

    session.close()


def test_stock_read_service_falls_back_when_quote_is_missing() -> None:
    _, session = _create_test_session()
    session.add(
        Stock(
            market="US",
            symbol="NVDA",
            name="NVIDIA Corporation",
            exchange="NASDAQ",
            currency="USD",
            timezone="America/New_York",
        )
    )
    session.commit()

    snapshot = get_stock_read_snapshot(session, MarketCode.US, "NVDA")

    assert snapshot.source == "mock_provider"
    assert snapshot.profile.symbol == "NVDA"
    assert snapshot.quote.price == 181.42

    session.close()


def test_stock_read_service_keeps_same_symbol_separated_by_market() -> None:
    _, session = _create_test_session()
    us_stock = _add_stock(
        session,
        market="US",
        symbol="ABC",
        name="ABC US",
        exchange="NASDAQ",
        currency="USD",
        timezone="America/New_York",
    )
    hk_stock = _add_stock(
        session,
        market="HK",
        symbol="ABC",
        name="ABC HK",
        exchange="HKEX",
        currency="HKD",
        timezone="Asia/Hong_Kong",
    )
    quote_repository = LatestQuoteRepository(session)
    quote_repository.save_latest(_build_quote(us_stock, price=Decimal("10.00"), data_status="realtime"))
    quote_repository.save_latest(_build_quote(hk_stock, price=Decimal("20.00"), data_status="delayed"))
    session.commit()

    us_snapshot = get_stock_read_snapshot(session, MarketCode.US, " abc ")
    hk_snapshot = get_stock_read_snapshot(session, MarketCode.HK, " abc ")

    assert us_snapshot.source == "database"
    assert hk_snapshot.source == "database"
    assert us_snapshot.profile.name == "ABC US"
    assert hk_snapshot.profile.name == "ABC HK"
    assert us_snapshot.profile.currency == "USD"
    assert hk_snapshot.profile.currency == "HKD"
    assert us_snapshot.quote.price == 10.0
    assert hk_snapshot.quote.price == 20.0
    assert us_snapshot.quote.data_status == "realtime"
    assert hk_snapshot.quote.data_status == "delayed"

    session.close()


def _add_stock(
    session,
    *,
    market: str,
    symbol: str,
    name: str,
    exchange: str,
    currency: str,
    timezone: str,
) -> Stock:
    """构造个股读取测试所需的股票基础资料。"""

    stock = Stock(
        market=market,
        symbol=symbol,
        name=name,
        exchange=exchange,
        currency=currency,
        timezone=timezone,
    )
    session.add(stock)
    session.flush()
    return stock


def _build_quote(stock: Stock, *, price: Decimal, data_status: str) -> LatestQuote:
    """构造个股读取测试所需的最新行情。"""

    return LatestQuote(
        stock_id=stock.id,
        market=stock.market,
        symbol=stock.symbol,
        price=price,
        change_amount=Decimal("0.50"),
        change_percent=Decimal("0.05000000"),
        volume=1_000_000,
        turnover=price * Decimal("1000000"),
        data_status=data_status,
        source="test",
        quote_timestamp=datetime(2026, 9, 28, 10, 30, 0),
    )

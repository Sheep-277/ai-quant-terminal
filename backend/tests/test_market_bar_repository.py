from datetime import datetime, timedelta
from decimal import Decimal

from app.db.repositories.market_bar_repository import MarketBarRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.market_bar import MarketBar
from app.models.stock import Stock


def _create_test_session():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return create_session_factory(engine)()


def _add_stock(session, *, market: str = "US", symbol: str = "NVDA") -> Stock:
    stock = Stock(
        market=market,
        symbol=symbol,
        name=f"{symbol} Example",
        exchange="NASDAQ" if market == "US" else "HKEX",
        currency="USD" if market == "US" else "HKD",
        timezone="America/New_York" if market == "US" else "Asia/Hong_Kong",
    )
    session.add(stock)
    session.flush()
    return stock


def _build_bar(stock: Stock, offset: int, close_price: str) -> MarketBar:
    timestamp = datetime(2026, 9, 20, 0, 0, 0) + timedelta(days=offset)
    return MarketBar(
        stock_id=stock.id,
        market=stock.market,
        symbol=stock.symbol,
        interval_code="1d",
        bar_timestamp=timestamp,
        open_price=Decimal("180.000000"),
        high_price=Decimal("183.000000"),
        low_price=Decimal("179.500000"),
        close_price=Decimal(close_price),
        volume=1000 + offset,
        source="mock",
        data_status="delayed",
    )


def test_market_bar_repository_adds_and_lists_bars_by_symbol() -> None:
    session = _create_test_session()
    repository = MarketBarRepository(session)
    stock = _add_stock(session)

    repository.add_many(
        [
            _build_bar(stock, 1, "181.000000"),
            _build_bar(stock, 0, "180.000000"),
            _build_bar(stock, 2, "182.000000"),
        ]
    )
    session.commit()

    bars = repository.list_by_symbol("us", " nvda ", "1d")

    assert [bar.close_price for bar in bars] == [
        Decimal("180.000000"),
        Decimal("181.000000"),
        Decimal("182.000000"),
    ]

    session.close()


def test_market_bar_repository_filters_by_time_range() -> None:
    session = _create_test_session()
    repository = MarketBarRepository(session)
    stock = _add_stock(session)
    repository.add_many([_build_bar(stock, offset, f"18{offset}.000000") for offset in range(5)])
    session.commit()

    bars = repository.list_by_symbol(
        "US",
        "NVDA",
        "1d",
        start_at=datetime(2026, 9, 21, 0, 0, 0),
        end_at=datetime(2026, 9, 23, 0, 0, 0),
    )

    assert [bar.bar_timestamp.day for bar in bars] == [21, 22, 23]

    session.close()


def test_market_bar_repository_lists_latest_bars_in_ascending_order() -> None:
    session = _create_test_session()
    repository = MarketBarRepository(session)
    stock = _add_stock(session)
    repository.add_many([_build_bar(stock, offset, f"18{offset}.000000") for offset in range(5)])
    session.commit()

    bars = repository.list_latest("US", "NVDA", "1d", limit=3)

    assert [bar.bar_timestamp.day for bar in bars] == [22, 23, 24]
    assert [bar.close_price for bar in bars] == [
        Decimal("182.000000"),
        Decimal("183.000000"),
        Decimal("184.000000"),
    ]

    session.close()


def test_market_bar_repository_keeps_same_symbol_separated_by_market() -> None:
    session = _create_test_session()
    repository = MarketBarRepository(session)
    us_stock = _add_stock(session, market="US", symbol="ABC")
    hk_stock = _add_stock(session, market="HK", symbol="ABC")
    repository.add_many(
        [
            _build_bar(us_stock, 0, "180.000000"),
            _build_bar(hk_stock, 0, "280.000000"),
        ]
    )
    session.commit()

    us_bars = repository.list_latest("us", " abc ", "1d", limit=10)
    hk_bars = repository.list_latest("hk", " abc ", "1d", limit=10)

    assert [bar.close_price for bar in us_bars] == [Decimal("180.000000")]
    assert [bar.close_price for bar in hk_bars] == [Decimal("280.000000")]

    session.close()

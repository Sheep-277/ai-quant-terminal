from datetime import datetime
from decimal import Decimal

from app.db.repositories.valuation_snapshot_repository import ValuationSnapshotRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.stock import Stock
from app.models.valuation_snapshot import ValuationSnapshot


def _create_stock(session, *, market: str = "US", symbol: str = "NVDA") -> Stock:
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


def _snapshot(stock: Stock, snapshot_timestamp: datetime, pe_ttm: str) -> ValuationSnapshot:
    return ValuationSnapshot(
        stock_id=stock.id,
        market=stock.market,
        symbol=stock.symbol,
        pe_ttm=Decimal(pe_ttm),
        pb=Decimal("41.200000"),
        ps_ttm=Decimal("25.400000"),
        pfcf_ttm=Decimal("65.800000"),
        snapshot_timestamp=snapshot_timestamp,
        source="test",
    )


def test_valuation_snapshot_repository_returns_latest_snapshot() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        stock = _create_stock(session)
        repository = ValuationSnapshotRepository(session)

        repository.save_snapshot(_snapshot(stock, datetime(2026, 9, 28, 10, 30, 0), "48.600000"))
        repository.save_snapshot(_snapshot(stock, datetime(2026, 9, 29, 10, 30, 0), "47.900000"))
        session.commit()

        latest = repository.get_latest_by_market_symbol("us", " nvda ")
        history = repository.list_by_market_symbol("US", "NVDA")

        assert latest is not None
        assert latest.snapshot_timestamp == datetime(2026, 9, 29, 10, 30, 0)
        assert latest.pe_ttm == Decimal("47.900000")
        assert [item.pe_ttm for item in history] == [Decimal("47.900000"), Decimal("48.600000")]


def test_valuation_snapshot_repository_updates_existing_snapshot() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        stock = _create_stock(session)
        repository = ValuationSnapshotRepository(session)

        timestamp = datetime(2026, 9, 28, 10, 30, 0)
        first = repository.save_snapshot(_snapshot(stock, timestamp, "48.600000"))
        session.commit()

        updated = repository.save_snapshot(_snapshot(stock, timestamp, "49.100000"))
        session.commit()

        history = repository.list_by_market_symbol("US", "NVDA")

        assert updated.id == first.id
        assert len(history) == 1
        assert history[0].pe_ttm == Decimal("49.100000")


def test_valuation_snapshot_repository_keeps_same_symbol_separated_by_market() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        us_stock = _create_stock(session, market="US", symbol="ABC")
        hk_stock = _create_stock(session, market="HK", symbol="ABC")
        repository = ValuationSnapshotRepository(session)

        repository.save_snapshot(_snapshot(us_stock, datetime(2026, 9, 28, 10, 30, 0), "30.100000"))
        repository.save_snapshot(_snapshot(hk_stock, datetime(2026, 9, 28, 10, 30, 0), "20.200000"))
        session.commit()

        us_latest = repository.get_latest_by_market_symbol("us", " abc ")
        hk_latest = repository.get_latest_by_market_symbol("hk", " abc ")

        assert us_latest is not None
        assert hk_latest is not None
        assert us_latest.pe_ttm == Decimal("30.100000")
        assert hk_latest.pe_ttm == Decimal("20.200000")

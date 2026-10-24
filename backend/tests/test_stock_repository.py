from app.db.repositories.stock_repository import StockRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.stock import Stock


def _create_test_session():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return create_session_factory(engine)()


def test_stock_repository_adds_and_gets_stock_by_market_symbol() -> None:
    session = _create_test_session()
    repository = StockRepository(session)

    stock = repository.add(
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

    found = repository.get_by_market_symbol("us", " nvda ")

    assert found == stock
    assert found is not None
    assert found.symbol == "NVDA"

    session.close()


def test_stock_repository_lists_active_stocks_by_market() -> None:
    session = _create_test_session()
    repository = StockRepository(session)

    repository.add(
        Stock(
            market="US",
            symbol="NVDA",
            name="NVIDIA Corporation",
            exchange="NASDAQ",
            currency="USD",
            timezone="America/New_York",
        )
    )
    repository.add(
        Stock(
            market="US",
            symbol="OLD",
            name="Inactive Example",
            exchange="NASDAQ",
            currency="USD",
            timezone="America/New_York",
            is_active=False,
        )
    )
    repository.add(
        Stock(
            market="HK",
            symbol="00700.HK",
            name="Tencent Holdings",
            exchange="HKEX",
            currency="HKD",
            timezone="Asia/Hong_Kong",
        )
    )
    session.commit()

    active_us_stocks = repository.list_by_market("us")
    all_us_stocks = repository.list_by_market("US", active_only=False)

    assert [stock.symbol for stock in active_us_stocks] == ["NVDA"]
    assert [stock.symbol for stock in all_us_stocks] == ["NVDA", "OLD"]

    session.close()


def test_stock_repository_returns_none_when_stock_is_missing() -> None:
    session = _create_test_session()
    repository = StockRepository(session)

    assert repository.get_by_market_symbol("CN", "600000") is None

    session.close()


def test_stock_repository_keeps_same_symbol_separated_by_market() -> None:
    session = _create_test_session()
    repository = StockRepository(session)

    us_stock = repository.add(
        Stock(
            market="US",
            symbol="ABC",
            name="ABC US",
            exchange="NASDAQ",
            currency="USD",
            timezone="America/New_York",
        )
    )
    hk_stock = repository.add(
        Stock(
            market="HK",
            symbol="ABC",
            name="ABC HK",
            exchange="HKEX",
            currency="HKD",
            timezone="Asia/Hong_Kong",
        )
    )
    session.commit()

    found_us = repository.get_by_market_symbol("us", " abc ")
    found_hk = repository.get_by_market_symbol("hk", " abc ")

    assert found_us == us_stock
    assert found_hk == hk_stock
    assert found_us is not None
    assert found_hk is not None
    assert found_us.currency == "USD"
    assert found_hk.currency == "HKD"

    session.close()

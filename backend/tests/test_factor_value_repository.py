from datetime import date
from decimal import Decimal

from app.db.repositories.factor_value_repository import FactorValueRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.factor_value import FactorValue
from app.models.stock import Stock


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


def _factor(stock: Stock, factor_name: str, as_of_date: date, factor_value: str) -> FactorValue:
    return FactorValue(
        stock_id=stock.id,
        market=stock.market,
        symbol=stock.symbol,
        factor_name=factor_name,
        factor_value=Decimal(factor_value),
        as_of_date=as_of_date,
        data_status="realtime",
        source="test",
    )


def test_factor_value_repository_returns_latest_factor_set() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        stock = _create_stock(session)
        repository = FactorValueRepository(session)

        repository.save_values([
            _factor(stock, "momentum_20d", date(2026, 9, 27), "0.12000000"),
            _factor(stock, "momentum_20d", date(2026, 9, 28), "0.17000000"),
            _factor(stock, "quality_score", date(2026, 9, 28), "0.91000000"),
        ])
        session.commit()

        latest_values = repository.list_latest_by_market_symbol("us", " nvda ")

        assert [item.factor_name for item in latest_values] == ["momentum_20d", "quality_score"]
        assert [item.factor_value for item in latest_values] == [Decimal("0.17000000"), Decimal("0.91000000")]


def test_factor_value_repository_lists_history_and_updates_existing_value() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        stock = _create_stock(session)
        repository = FactorValueRepository(session)

        first = repository.save_values([
            _factor(stock, "momentum_20d", date(2026, 9, 27), "0.12000000"),
            _factor(stock, "momentum_20d", date(2026, 9, 28), "0.17000000"),
        ])[1]
        session.commit()

        updated = repository.save_values([
            _factor(stock, "momentum_20d", date(2026, 9, 28), "0.18000000"),
        ])[0]
        session.commit()

        history = repository.list_history("US", "NVDA", "momentum_20d")

        assert updated.id == first.id
        assert [item.factor_value for item in history] == [Decimal("0.18000000"), Decimal("0.12000000")]


def test_factor_value_repository_keeps_same_symbol_separated_by_market() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        us_stock = _create_stock(session, market="US", symbol="ABC")
        hk_stock = _create_stock(session, market="HK", symbol="ABC")
        repository = FactorValueRepository(session)

        repository.save_values([
            _factor(us_stock, "composite_score", date(2026, 9, 28), "0.81000000"),
            _factor(hk_stock, "composite_score", date(2026, 9, 28), "0.62000000"),
        ])
        session.commit()

        us_values = repository.list_latest_by_market_symbol("us", " abc ")
        hk_values = repository.list_latest_by_market_symbol("hk", " abc ")

        assert [item.factor_value for item in us_values] == [Decimal("0.81000000")]
        assert [item.factor_value for item in hk_values] == [Decimal("0.62000000")]

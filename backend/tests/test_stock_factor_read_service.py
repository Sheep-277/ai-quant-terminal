from datetime import date
from decimal import Decimal

from app.core.market import MarketCode
from app.db.repositories.factor_value_repository import FactorValueRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.factor_value import FactorValue
from app.models.stock import Stock
from app.services.stock_factor_read_service import get_stock_factor_read_snapshot


def _create_session():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return create_session_factory(engine)()


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


def _factor(stock: Stock, factor_name: str, factor_value: str) -> FactorValue:
    return FactorValue(
        stock_id=stock.id,
        market=stock.market,
        symbol=stock.symbol,
        factor_name=factor_name,
        factor_value=Decimal(factor_value),
        as_of_date=date(2026, 9, 28),
        data_status="realtime",
        source="test",
    )


def test_stock_factor_read_service_returns_database_factor_snapshot() -> None:
    session = _create_session()
    stock = _create_stock(session)
    FactorValueRepository(session).save_values([
        _factor(stock, "momentum_20d", "0.17000000"),
        _factor(stock, "trend_strength", "0.07000000"),
        _factor(stock, "volatility_20d", "0.01500000"),
        _factor(stock, "quality_score", "0.91000000"),
        _factor(stock, "composite_score", "0.93000000"),
    ])
    session.commit()

    snapshot = get_stock_factor_read_snapshot(session, MarketCode.US, " nvda ")

    assert snapshot is not None
    assert snapshot.source == "database"
    assert snapshot.available_factors == (
        "momentum_20d",
        "trend_strength",
        "volatility_20d",
        "quality_score",
        "composite_score",
    )
    assert snapshot.missing_factors == ()
    assert snapshot.factor_snapshot.momentum_20d == 0.17
    assert snapshot.factor_snapshot.composite_score == 0.93

    session.close()


def test_stock_factor_read_service_allows_partial_factor_snapshot() -> None:
    session = _create_session()
    stock = _create_stock(session)
    FactorValueRepository(session).save_values([
        _factor(stock, "momentum_20d", "0.17000000"),
        _factor(stock, "quality_score", "0.91000000"),
    ])
    session.commit()

    snapshot = get_stock_factor_read_snapshot(session, MarketCode.US, "NVDA")

    assert snapshot is not None
    assert snapshot.available_factors == ("momentum_20d", "quality_score")
    assert snapshot.missing_factors == ("trend_strength", "volatility_20d", "composite_score")
    assert snapshot.factor_snapshot.momentum_20d == 0.17
    assert snapshot.factor_snapshot.trend_strength is None

    session.close()


def test_stock_factor_read_service_returns_none_when_database_is_empty() -> None:
    session = _create_session()

    snapshot = get_stock_factor_read_snapshot(session, MarketCode.US, "NVDA")

    assert snapshot is None

    session.close()


def test_stock_factor_read_service_keeps_same_symbol_separated_by_market() -> None:
    session = _create_session()
    us_stock = _create_stock(session, market="US", symbol="ABC")
    hk_stock = _create_stock(session, market="HK", symbol="ABC")
    repository = FactorValueRepository(session)
    repository.save_values([
        _factor(us_stock, "momentum_20d", "0.11000000"),
        _factor(us_stock, "composite_score", "0.81000000"),
        _factor(hk_stock, "momentum_20d", "0.05000000"),
        _factor(hk_stock, "composite_score", "0.62000000"),
    ])
    session.commit()

    us_snapshot = get_stock_factor_read_snapshot(session, MarketCode.US, " abc ")
    hk_snapshot = get_stock_factor_read_snapshot(session, MarketCode.HK, " abc ")

    assert us_snapshot is not None
    assert hk_snapshot is not None
    assert us_snapshot.factor_snapshot.momentum_20d == 0.11
    assert hk_snapshot.factor_snapshot.momentum_20d == 0.05
    assert us_snapshot.factor_snapshot.composite_score == 0.81
    assert hk_snapshot.factor_snapshot.composite_score == 0.62
    assert us_snapshot.available_factors == ("momentum_20d", "composite_score")
    assert hk_snapshot.available_factors == ("momentum_20d", "composite_score")

    session.close()

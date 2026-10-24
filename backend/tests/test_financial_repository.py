from datetime import date
from decimal import Decimal

from app.db.repositories.financial_repository import FinancialRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.financial import Financial
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


def _financial(stock: Stock, fiscal_period: str, period_end_date: date, revenue: str) -> Financial:
    return Financial(
        stock_id=stock.id,
        market=stock.market,
        symbol=stock.symbol,
        fiscal_period=fiscal_period,
        period_end_date=period_end_date,
        revenue=Decimal(revenue),
        net_income=Decimal("72880000000.0000"),
        gross_margin=Decimal("0.75400000"),
        operating_margin=Decimal("0.62600000"),
        roe=Decimal("0.91000000"),
        roic=Decimal("0.57000000"),
        operating_cash_flow=Decimal("69300000000.0000"),
        capex=Decimal("7200000000.0000"),
        fcf=Decimal("62100000000.0000"),
        source="test",
    )


def test_financial_repository_returns_latest_period() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        stock = _create_stock(session)
        repository = FinancialRepository(session)

        repository.save_period(_financial(stock, "2026Q2", date(2026, 6, 30), "115000000000.0000"))
        repository.save_period(_financial(stock, "2026Q3", date(2026, 9, 30), "130500000000.0000"))
        session.commit()

        latest = repository.get_latest_by_market_symbol("us", " nvda ")
        history = repository.list_by_market_symbol("US", "NVDA")

        assert latest is not None
        assert latest.fiscal_period == "2026Q3"
        assert latest.revenue == Decimal("130500000000.0000")
        assert [item.fiscal_period for item in history] == ["2026Q3", "2026Q2"]


def test_financial_repository_updates_existing_period() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        stock = _create_stock(session)
        repository = FinancialRepository(session)

        first = repository.save_period(_financial(stock, "2026Q3", date(2026, 9, 30), "130500000000.0000"))
        session.commit()

        updated = repository.save_period(_financial(stock, "2026Q3", date(2026, 9, 30), "131000000000.0000"))
        session.commit()

        history = repository.list_by_market_symbol("US", "NVDA")

        assert updated.id == first.id
        assert len(history) == 1
        assert history[0].revenue == Decimal("131000000000.0000")


def test_financial_repository_keeps_same_symbol_separated_by_market() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        us_stock = _create_stock(session, market="US", symbol="ABC")
        hk_stock = _create_stock(session, market="HK", symbol="ABC")
        repository = FinancialRepository(session)

        repository.save_period(_financial(us_stock, "2026Q3", date(2026, 9, 30), "100000000.0000"))
        repository.save_period(_financial(hk_stock, "2026Q3", date(2026, 9, 30), "200000000.0000"))
        session.commit()

        us_latest = repository.get_latest_by_market_symbol("us", " abc ")
        hk_latest = repository.get_latest_by_market_symbol("hk", " abc ")

        assert us_latest is not None
        assert hk_latest is not None
        assert us_latest.revenue == Decimal("100000000.0000")
        assert hk_latest.revenue == Decimal("200000000.0000")

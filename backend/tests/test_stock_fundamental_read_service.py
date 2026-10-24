from datetime import date, datetime
from decimal import Decimal

from app.core.market import MarketCode
from app.db.repositories.financial_repository import FinancialRepository
from app.db.repositories.valuation_snapshot_repository import ValuationSnapshotRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.financial import Financial
from app.models.stock import Stock
from app.models.valuation_snapshot import ValuationSnapshot
from app.services.stock_fundamental_read_service import get_stock_fundamental_read_snapshot


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


def test_stock_fundamental_read_service_returns_database_snapshot() -> None:
    session = _create_session()
    stock = _create_stock(session)

    FinancialRepository(session).save_period(
        Financial(
            stock_id=stock.id,
            market="US",
            symbol="NVDA",
            fiscal_period="TTM",
            period_end_date=date(2026, 9, 30),
            revenue=Decimal("130500000000.0000"),
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
    )
    ValuationSnapshotRepository(session).save_snapshot(
        ValuationSnapshot(
            stock_id=stock.id,
            market="US",
            symbol="NVDA",
            pe_ttm=Decimal("48.600000"),
            pb=Decimal("41.200000"),
            ps_ttm=Decimal("25.400000"),
            pfcf_ttm=Decimal("65.800000"),
            snapshot_timestamp=datetime(2026, 9, 28, 10, 30, 0),
            source="test",
        )
    )
    session.commit()

    snapshot = get_stock_fundamental_read_snapshot(session, MarketCode.US, " nvda ")

    assert snapshot is not None
    assert snapshot.source == "database"
    assert snapshot.completeness == "complete"
    assert snapshot.available_sections == ("valuation", "profitability", "cash_flow")
    assert snapshot.missing_sections == ()
    assert snapshot.valuation.pe_ttm == 48.6
    assert snapshot.valuation.pb == 41.2
    assert snapshot.profitability.roe_ttm == 0.91
    assert snapshot.profitability.roic_ttm == 0.57
    assert snapshot.cash_flow.fcf_ttm == 62100000000.0
    assert snapshot.cash_flow.capex_ttm == 7200000000.0

    session.close()


def test_stock_fundamental_read_service_returns_none_when_database_is_empty() -> None:
    session = _create_session()

    snapshot = get_stock_fundamental_read_snapshot(session, MarketCode.US, "NVDA")

    assert snapshot is None

    session.close()


def test_stock_fundamental_read_service_allows_partial_database_snapshot() -> None:
    session = _create_session()
    stock = _create_stock(session)

    ValuationSnapshotRepository(session).save_snapshot(
        ValuationSnapshot(
            stock_id=stock.id,
            market="US",
            symbol="NVDA",
            pe_ttm=Decimal("48.600000"),
            pb=Decimal("41.200000"),
            ps_ttm=Decimal("25.400000"),
            pfcf_ttm=Decimal("65.800000"),
            snapshot_timestamp=datetime(2026, 9, 28, 10, 30, 0),
            source="test",
        )
    )
    session.commit()

    snapshot = get_stock_fundamental_read_snapshot(session, MarketCode.US, "NVDA")

    assert snapshot is not None
    assert snapshot.completeness == "partial"
    assert snapshot.available_sections == ("valuation",)
    assert snapshot.missing_sections == ("profitability", "cash_flow")
    assert snapshot.valuation.pe_ttm == 48.6
    assert snapshot.profitability.roe_ttm is None
    assert snapshot.cash_flow.fcf_ttm is None

    session.close()


def test_stock_fundamental_read_service_keeps_same_symbol_separated_by_market() -> None:
    session = _create_session()
    us_stock = _create_stock(session, market="US", symbol="ABC")
    hk_stock = _create_stock(session, market="HK", symbol="ABC")
    financial_repository = FinancialRepository(session)
    valuation_repository = ValuationSnapshotRepository(session)

    financial_repository.save_period(
        Financial(
            stock_id=us_stock.id,
            market="US",
            symbol="ABC",
            fiscal_period="TTM",
            period_end_date=date(2026, 9, 30),
            revenue=Decimal("100000000.0000"),
            net_income=Decimal("50000000.0000"),
            gross_margin=Decimal("0.60000000"),
            operating_margin=Decimal("0.40000000"),
            roe=Decimal("0.30000000"),
            roic=Decimal("0.20000000"),
            operating_cash_flow=Decimal("30000000.0000"),
            capex=Decimal("5000000.0000"),
            fcf=Decimal("25000000.0000"),
            source="test",
        )
    )
    financial_repository.save_period(
        Financial(
            stock_id=hk_stock.id,
            market="HK",
            symbol="ABC",
            fiscal_period="TTM",
            period_end_date=date(2026, 9, 30),
            revenue=Decimal("200000000.0000"),
            net_income=Decimal("80000000.0000"),
            gross_margin=Decimal("0.50000000"),
            operating_margin=Decimal("0.30000000"),
            roe=Decimal("0.15000000"),
            roic=Decimal("0.10000000"),
            operating_cash_flow=Decimal("40000000.0000"),
            capex=Decimal("8000000.0000"),
            fcf=Decimal("32000000.0000"),
            source="test",
        )
    )
    valuation_repository.save_snapshot(
        ValuationSnapshot(
            stock_id=us_stock.id,
            market="US",
            symbol="ABC",
            pe_ttm=Decimal("30.100000"),
            pb=Decimal("10.200000"),
            ps_ttm=Decimal("8.300000"),
            pfcf_ttm=Decimal("25.400000"),
            snapshot_timestamp=datetime(2026, 9, 28, 10, 30, 0),
            source="test",
        )
    )
    valuation_repository.save_snapshot(
        ValuationSnapshot(
            stock_id=hk_stock.id,
            market="HK",
            symbol="ABC",
            pe_ttm=Decimal("20.100000"),
            pb=Decimal("5.200000"),
            ps_ttm=Decimal("4.300000"),
            pfcf_ttm=Decimal("15.400000"),
            snapshot_timestamp=datetime(2026, 9, 28, 10, 30, 0),
            source="test",
        )
    )
    session.commit()

    us_snapshot = get_stock_fundamental_read_snapshot(session, MarketCode.US, " abc ")
    hk_snapshot = get_stock_fundamental_read_snapshot(session, MarketCode.HK, " abc ")

    assert us_snapshot is not None
    assert hk_snapshot is not None
    assert us_snapshot.valuation.pe_ttm == 30.1
    assert hk_snapshot.valuation.pe_ttm == 20.1
    assert us_snapshot.profitability.roe_ttm == 0.3
    assert hk_snapshot.profitability.roe_ttm == 0.15
    assert us_snapshot.cash_flow.fcf_ttm == 25000000.0
    assert hk_snapshot.cash_flow.fcf_ttm == 32000000.0

    session.close()

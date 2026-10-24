from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import inspect

from app.db.session import Base, create_database_engine, create_session_factory
from app.models.financial import Financial
from app.models.stock import Stock
from app.models.valuation_snapshot import ValuationSnapshot


def test_financial_and_valuation_models_declare_expected_shape() -> None:
    financial_table = Financial.__table__
    valuation_table = ValuationSnapshot.__table__

    assert financial_table.name == "financials"
    assert {constraint.name for constraint in financial_table.constraints} >= {"uq_financials_period"}
    assert "idx_financials_symbol_period" in {index.name for index in financial_table.indexes}
    assert {"stocks.id"} == {
        f"{foreign_key.column.table.name}.{foreign_key.column.name}"
        for foreign_key in financial_table.foreign_keys
    }

    assert valuation_table.name == "valuation_snapshots"
    assert {constraint.name for constraint in valuation_table.constraints} >= {"uq_valuation_snapshot"}
    assert {"stocks.id"} == {
        f"{foreign_key.column.table.name}.{foreign_key.column.name}"
        for foreign_key in valuation_table.foreign_keys
    }


def test_financial_and_valuation_models_can_be_inserted() -> None:
    # 使用 SQLite 内存库验证 ORM 映射，不依赖本机 MySQL 服务。
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        stock = Stock(
            market="US",
            symbol="NVDA",
            name="NVIDIA Corporation",
            exchange="NASDAQ",
            currency="USD",
            timezone="America/New_York",
        )
        session.add(stock)
        session.flush()

        financial = Financial(
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
        valuation = ValuationSnapshot(
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
        session.add_all([financial, valuation])
        session.commit()
        session.refresh(financial)
        session.refresh(valuation)

        assert financial.id is not None
        assert financial.fcf == Decimal("62100000000.0000")
        assert valuation.id is not None
        assert valuation.pe_ttm == Decimal("48.600000")

    inspector = inspect(engine)
    assert {"financials", "valuation_snapshots"} <= set(inspector.get_table_names())

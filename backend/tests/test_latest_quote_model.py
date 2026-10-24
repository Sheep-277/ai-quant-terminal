from datetime import datetime
from decimal import Decimal

from sqlalchemy import inspect

from app.db.session import Base, create_database_engine, create_session_factory
from app.models.latest_quote import LatestQuote
from app.models.stock import Stock


def test_latest_quote_model_declares_expected_table_shape() -> None:
    table = LatestQuote.__table__

    assert table.name == "latest_quotes"
    assert {column.name for column in table.columns} == {
        "id",
        "stock_id",
        "market",
        "symbol",
        "price",
        "change_amount",
        "change_percent",
        "volume",
        "turnover",
        "data_status",
        "source",
        "quote_timestamp",
        "received_at",
    }
    assert {constraint.name for constraint in table.constraints} >= {
        "uq_latest_quotes_market_symbol",
        "ck_latest_quotes_status",
    }
    assert {"stocks.id"} == {
        f"{foreign_key.column.table.name}.{foreign_key.column.name}"
        for foreign_key in table.foreign_keys
    }


def test_latest_quote_model_can_be_created_and_inserted_in_database() -> None:
    # 先插入股票主数据，再插入最新行情，验证外键依赖方向正确。
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

        quote = LatestQuote(
            stock_id=stock.id,
            market="US",
            symbol="NVDA",
            price=Decimal("181.420000"),
            change_amount=Decimal("2.380000"),
            change_percent=Decimal("0.01330000"),
            volume=218430000,
            turnover=Decimal("39612000000.0000"),
            data_status="delayed",
            source="mock",
            quote_timestamp=datetime(2026, 9, 28, 10, 30, 0),
        )
        session.add(quote)
        session.commit()
        session.refresh(quote)

        assert quote.id is not None
        assert quote.stock_id == stock.id
        assert quote.price == Decimal("181.420000")
        assert quote.data_status == "delayed"
        assert quote.received_at is not None

    inspector = inspect(engine)
    assert "latest_quotes" in inspector.get_table_names()

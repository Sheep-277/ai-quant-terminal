from datetime import datetime
from decimal import Decimal

from sqlalchemy import inspect

from app.db.session import Base, create_database_engine, create_session_factory
from app.models.market_bar import MarketBar
from app.models.stock import Stock


def test_market_bar_model_declares_expected_table_shape() -> None:
    table = MarketBar.__table__

    assert table.name == "market_bars"
    assert {column.name for column in table.columns} == {
        "id",
        "stock_id",
        "market",
        "symbol",
        "interval_code",
        "bar_timestamp",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
        "source",
        "data_status",
        "received_at",
    }
    assert {constraint.name for constraint in table.constraints} >= {
        "uq_market_bars",
        "ck_market_bars_status",
    }
    assert {"stocks.id"} == {
        f"{foreign_key.column.table.name}.{foreign_key.column.name}"
        for foreign_key in table.foreign_keys
    }
    assert "idx_market_bars_symbol_time" in {index.name for index in table.indexes}


def test_market_bar_model_can_be_created_and_inserted_in_database() -> None:
    # MarketBar 依赖 Stock，先插入股票主数据，再插入一根日线 K 线。
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

        bar = MarketBar(
            stock_id=stock.id,
            market="US",
            symbol="NVDA",
            interval_code="1d",
            bar_timestamp=datetime(2026, 9, 28, 0, 0, 0),
            open_price=Decimal("180.000000"),
            high_price=Decimal("183.000000"),
            low_price=Decimal("179.500000"),
            close_price=Decimal("181.420000"),
            volume=218430000,
            source="mock",
            data_status="delayed",
        )
        session.add(bar)
        session.commit()
        session.refresh(bar)

        assert bar.id is not None
        assert bar.stock_id == stock.id
        assert bar.close_price == Decimal("181.420000")
        assert bar.interval_code == "1d"
        assert bar.received_at is not None

    inspector = inspect(engine)
    assert "market_bars" in inspector.get_table_names()

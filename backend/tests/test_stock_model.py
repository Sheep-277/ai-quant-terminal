from sqlalchemy import inspect

from app.db.session import Base, create_database_engine, create_session_factory
from app.models.stock import Stock


def test_stock_model_declares_expected_table_shape() -> None:
    table = Stock.__table__

    assert table.name == "stocks"
    assert {column.name for column in table.columns} == {
        "id",
        "market",
        "symbol",
        "name",
        "asset_type",
        "exchange",
        "currency",
        "timezone",
        "sector",
        "industry",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert {constraint.name for constraint in table.constraints} >= {
        "uq_stocks_market_symbol",
        "ck_stocks_market",
    }


def test_stock_model_can_be_created_and_inserted_in_database() -> None:
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
            sector="Technology",
            industry="Semiconductors",
        )
        session.add(stock)
        session.commit()
        session.refresh(stock)

        assert stock.id is not None
        assert stock.asset_type == "common_stock"
        assert stock.is_active is True
        assert stock.created_at is not None
        assert stock.updated_at is not None

    inspector = inspect(engine)
    assert "stocks" in inspector.get_table_names()

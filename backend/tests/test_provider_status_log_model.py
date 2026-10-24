from sqlalchemy import inspect

from app.db.session import Base, create_database_engine, create_session_factory
from app.models.provider_status_log import ProviderStatusLog


def test_provider_status_log_model_declares_expected_table_shape() -> None:
    table = ProviderStatusLog.__table__

    assert table.name == "provider_status_logs"
    assert {column.name for column in table.columns} == {
        "id",
        "provider_name",
        "mode",
        "ready",
        "data_status",
        "fallback_active",
        "fallback_reason",
        "checked_at",
    }
    assert {constraint.name for constraint in table.constraints} >= {
        "ck_provider_status_mode",
        "ck_provider_status_data_status",
    }
    assert "idx_provider_status_checked_at" in {index.name for index in table.indexes}


def test_provider_status_log_model_can_be_created_and_inserted_in_database() -> None:
    # Provider 状态日志不依赖股票表，可独立记录数据源健康检查结果。
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        status_log = ProviderStatusLog(
            provider_name="MockMarketDataProvider",
            mode="mock",
            ready=True,
            data_status="delayed",
            fallback_active=False,
            fallback_reason=None,
        )
        session.add(status_log)
        session.commit()
        session.refresh(status_log)

        assert status_log.id is not None
        assert status_log.provider_name == "MockMarketDataProvider"
        assert status_log.ready is True
        assert status_log.fallback_active is False
        assert status_log.checked_at is not None

    inspector = inspect(engine)
    assert "provider_status_logs" in inspector.get_table_names()

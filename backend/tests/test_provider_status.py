from fastapi.testclient import TestClient

from app.api.v1.provider import build_provider_status_log_list_response, build_provider_status_response
from app.core.config import Settings
from app.db.repositories.provider_status_log_repository import ProviderStatusLogRepository
from app.db.session import Base, create_database_engine, create_session_factory, get_engine, get_session_factory
from app.main import app
from app.models.provider_status_log import ProviderStatusLog


client = TestClient(app)


def test_provider_status_defaults_to_mock_ready() -> None:
    # 默认配置下，Provider 状态接口应显示本地 Mock 数据源可用。
    response = client.get("/api/v1/provider/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "provider_name": "MockMarketDataProvider",
        "mode": "mock",
        "ready": True,
        "data_status": "realtime",
        "fallback_active": False,
        "fallback_reason": None,
        "source_type": "mock",
        "active_source": "provider",
        "missing_configuration": [],
        "next_action": None,
        "last_logged_at": None,
        "recent_log_count": 0,
    }


def test_provider_status_can_log_to_database_when_enabled(monkeypatch) -> None:
    # 测试使用 SQLite 临时库，不要求本地 MySQL 已经启动。
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)

    settings = Settings(
        DATABASE_URL=database_url,
        ENABLE_PROVIDER_STATUS_LOGGING=True,
        _env_file=None,
    )

    response = build_provider_status_response(settings)

    with session_factory() as session:
        repository = ProviderStatusLogRepository(session)
        latest_log = repository.get_latest("MockMarketDataProvider")

    assert response.provider_name == "MockMarketDataProvider"
    assert response.last_logged_at is not None
    assert response.recent_log_count == 1
    assert latest_log is not None
    assert latest_log.provider_name == "MockMarketDataProvider"
    assert latest_log.mode == "mock"


def test_provider_status_logs_can_be_listed(monkeypatch) -> None:
    # 最近日志列表用于本地验收数据源状态，不要求真实外部 Provider。
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)

    with session_factory() as session:
        repository = ProviderStatusLogRepository(session)
        repository.add(
            ProviderStatusLog(
                provider_name="MockMarketDataProvider",
                mode="mock",
                ready=True,
                data_status="realtime",
                fallback_active=False,
                fallback_reason=None,
            )
        )
        session.commit()

    response = build_provider_status_log_list_response(
        Settings(DATABASE_URL=database_url, _env_file=None),
        limit=20,
        provider_name="MockMarketDataProvider",
    )

    assert response.database_available is True
    assert response.total == 1
    assert response.items[0].provider_name == "MockMarketDataProvider"
    assert response.items[0].data_status == "realtime"


def test_provider_status_logs_return_empty_when_database_is_unavailable(monkeypatch) -> None:
    def raise_database_error(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("app.api.v1.provider.get_db_session", raise_database_error)

    response = build_provider_status_log_list_response(Settings(_env_file=None))

    assert response.database_available is False
    assert response.items == []
    assert response.total == 0
    assert "RuntimeError" in response.fallback_reason

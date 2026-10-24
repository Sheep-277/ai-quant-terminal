from app.db.repositories.provider_status_log_repository import ProviderStatusLogRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.core.config import Settings
from app.providers.market_data import MockMarketDataProvider
from app.providers.real_market_data import RealMarketDataProvider
from app.schemas.provider import ProviderStatusResponse
from app.services.provider_status_service import get_provider_status


def _create_test_session():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return create_session_factory(engine)()


def test_provider_status_service_returns_current_provider_status() -> None:
    status = get_provider_status(provider=MockMarketDataProvider())

    assert status == {
        "provider_name": "MockMarketDataProvider",
        "mode": "mock",
        "ready": True,
        "data_status": "realtime",
        "fallback_active": False,
        "fallback_reason": None,
    }


def test_provider_status_response_exposes_real_provider_fallback_fields() -> None:
    # 前端状态条依赖这些字段区分真实源、Mock 回退和缺失配置。
    settings = Settings(DATA_PROVIDER="real", _env_file=None)
    status = get_provider_status(provider=RealMarketDataProvider(settings=settings))
    response = ProviderStatusResponse(**status)

    assert response.mode == "real"
    assert response.ready is False
    assert response.source_type == "real_placeholder"
    assert response.active_source == "mock_fallback"
    assert response.missing_configuration == ["REAL_PROVIDER_BASE_URL", "REAL_PROVIDER_API_KEY_ENV"]
    assert response.next_action == "补全配置项：REAL_PROVIDER_BASE_URL, REAL_PROVIDER_API_KEY_ENV。"


def test_provider_status_service_can_record_status_log() -> None:
    session = _create_test_session()
    repository = ProviderStatusLogRepository(session)

    status = get_provider_status(
        provider=MockMarketDataProvider(),
        status_log_repository=repository,
    )
    session.commit()

    latest_log = repository.get_latest("MockMarketDataProvider")

    assert latest_log is not None
    assert latest_log.provider_name == status["provider_name"]
    assert latest_log.mode == status["mode"]
    assert latest_log.ready == status["ready"]
    assert latest_log.data_status == status["data_status"]
    assert latest_log.fallback_active == status["fallback_active"]
    assert latest_log.fallback_reason == status["fallback_reason"]

    session.close()

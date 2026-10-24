from datetime import datetime, timedelta

from app.db.repositories.provider_status_log_repository import ProviderStatusLogRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.provider_status_log import ProviderStatusLog


def _create_test_session():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return create_session_factory(engine)()


def _build_status_log(
    provider_name: str,
    offset_minutes: int,
    *,
    ready: bool = True,
    fallback_active: bool = False,
) -> ProviderStatusLog:
    return ProviderStatusLog(
        provider_name=provider_name,
        mode="mock" if provider_name.startswith("Mock") else "real",
        ready=ready,
        data_status="delayed" if ready else "unavailable",
        fallback_active=fallback_active,
        fallback_reason="Adapter 尚未实现" if fallback_active else None,
        checked_at=datetime(2026, 9, 28, 10, 0, 0) + timedelta(minutes=offset_minutes),
    )


def test_provider_status_log_repository_adds_and_gets_latest_status() -> None:
    session = _create_test_session()
    repository = ProviderStatusLogRepository(session)

    repository.add(_build_status_log("MockMarketDataProvider", 0))
    latest = repository.add(_build_status_log("MockMarketDataProvider", 5))
    session.commit()

    found = repository.get_latest("MockMarketDataProvider")

    assert found == latest
    assert found is not None
    assert found.checked_at.minute == 5

    session.close()


def test_provider_status_log_repository_lists_recent_status_logs() -> None:
    session = _create_test_session()
    repository = ProviderStatusLogRepository(session)
    for offset in range(5):
        repository.add(_build_status_log("MockMarketDataProvider", offset))
    session.commit()

    logs = repository.list_recent(limit=3)

    assert [log.checked_at.minute for log in logs] == [4, 3, 2]

    session.close()


def test_provider_status_log_repository_filters_by_provider_name() -> None:
    session = _create_test_session()
    repository = ProviderStatusLogRepository(session)
    repository.add(_build_status_log("MockMarketDataProvider", 0))
    real_log = repository.add(
        _build_status_log("RealMarketDataProvider", 1, ready=False, fallback_active=True)
    )
    session.commit()

    latest_real = repository.get_latest("RealMarketDataProvider")
    mock_logs = repository.list_recent(provider_name="MockMarketDataProvider")

    assert latest_real == real_log
    assert latest_real is not None
    assert latest_real.fallback_active is True
    assert [log.provider_name for log in mock_logs] == ["MockMarketDataProvider"]
    assert repository.get_latest("MissingProvider") is None

    session.close()

from app.api.v1.ai_research import build_ai_research_task_create_response
from app.core.config import Settings, get_settings
from app.core.market import MarketCode
from app.db.repositories.ai_research_repository import AIResearchRepository
from app.db.session import Base, create_database_engine, create_session_factory, get_engine, get_session_factory
from app.schemas.ai_research import AIResearchRequest, ResearchTaskStatus
from app.services.ai_research_write_service import create_ai_research_task_record


def test_ai_research_write_service_saves_task_record() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)
    request = AIResearchRequest(
        market=MarketCode.US,
        query="分析 NVDA 今天异动原因",
        symbols=["NVDA"],
        include_strategy_idea=True,
    )

    with session_factory() as session:
        response = create_ai_research_task_record(session, request, route_prefix="/research")
        saved_task = AIResearchRepository(session).get_task_by_task_id(response.task_id)

        assert response.task_id == "research-us-nvda-queued"
        assert response.status == ResearchTaskStatus.QUEUED
        assert response.poll_url == "/api/v1/research/tasks/research-us-nvda-queued"
        assert saved_task is not None
        assert saved_task.market == "US"
        assert saved_task.query == request.query
        assert saved_task.symbols == ["NVDA"]
        assert saved_task.status == "queued"
        assert saved_task.data_status == "realtime"
        assert saved_task.route_prefix == "/research"
        assert saved_task.include_strategy_idea is True
        assert saved_task.result_snapshot is not None
        assert "NVDA" in saved_task.result_snapshot["headline"]
        assert saved_task.result_snapshot["headline"]
        evidence = AIResearchRepository(session).list_evidence(saved_task.task_id)
        assert evidence
        assert {item.symbol for item in evidence} == {"NVDA"}


def test_ai_research_write_service_uses_request_query_and_symbol_in_snapshot() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)
    request = AIResearchRequest(
        market=MarketCode.HK,
        query="分析 00700.HK 是否受 AI 新闻催化",
        symbols=["00700.HK"],
    )

    with session_factory() as session:
        response = create_ai_research_task_record(session, request, route_prefix="/research")
        saved_task = AIResearchRepository(session).get_task_by_task_id(response.task_id)

        assert saved_task is not None
        assert saved_task.query == request.query
        assert saved_task.result_snapshot is not None
        assert "00700.HK" in saved_task.result_snapshot["headline"]
        evidence = AIResearchRepository(session).list_evidence(saved_task.task_id)
        assert evidence
        assert {item.symbol for item in evidence} == {"00700.HK"}


def test_ai_research_write_service_updates_existing_task_record() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)
    first_request = AIResearchRequest(
        market=MarketCode.HK,
        query="分析港股科技股是否走强",
    )
    second_request = AIResearchRequest(
        market=MarketCode.HK,
        query="重新分析港股科技股是否走强",
    )

    with session_factory() as session:
        first_response = create_ai_research_task_record(session, first_request, route_prefix="/ai-research")
        first_task = AIResearchRepository(session).get_task_by_task_id(first_response.task_id)
        assert first_task is not None

        second_response = create_ai_research_task_record(session, second_request, route_prefix="/ai-research")
        second_task = AIResearchRepository(session).get_task_by_task_id(second_response.task_id)

        assert second_task is not None
        assert second_task.id == first_task.id
        assert second_task.query == second_request.query
        assert second_task.route_prefix == "/ai-research"
        assert AIResearchRepository(session).list_evidence(second_task.task_id)


def test_ai_research_api_builder_can_write_task_record(monkeypatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(bind=engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_settings.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)
    request = AIResearchRequest(
        market=MarketCode.CN,
        query="分析 A 股新能源链是否出现机会",
        symbols=["300750.SZ"],
    )

    response = build_ai_research_task_create_response(
        request,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_AI_RESEARCH_DATABASE_WRITES=True,
            _env_file=None,
        ),
        route_prefix="/research",
    )

    session_factory = create_session_factory(engine)
    with session_factory() as session:
        saved_task = AIResearchRepository(session).get_task_by_task_id(response.task_id)

        assert response.poll_url == "/api/v1/research/tasks/research-cn-300750-sz-queued"
        assert saved_task is not None
        assert saved_task.market == "CN"
        assert saved_task.symbols == ["300750.SZ"]
        assert AIResearchRepository(session).list_evidence(saved_task.task_id)


def test_ai_research_api_builder_marks_fallback_when_database_write_fails(monkeypatch) -> None:
    def raise_database_write_error(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_settings.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)
    monkeypatch.setattr("app.api.v1.ai_research.create_ai_research_task_record", raise_database_write_error)
    request = AIResearchRequest(
        market=MarketCode.US,
        query="分析 NVDA 今天异动原因",
        symbols=["NVDA"],
        include_strategy_idea=True,
    )

    response = build_ai_research_task_create_response(
        request,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_AI_RESEARCH_DATABASE_WRITES=True,
            _env_file=None,
        ),
        route_prefix="/research",
    )

    assert response.task_id == "research-us-nvda-queued"
    assert response.data_status == "unavailable"
    assert response.fallback_active is True
    assert response.storage_source == "mock_fallback"
    assert "RuntimeError" in response.fallback_reason
    assert "未持久化 Mock 研究任务" in response.fallback_reason

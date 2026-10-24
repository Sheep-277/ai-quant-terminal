import pytest
from fastapi import HTTPException

from app.api.v1.ai_research import build_ai_research_task_by_id_response, build_ai_research_task_response
from app.core.config import Settings, get_settings
from app.core.market import MarketCode
from app.db.repositories.ai_research_repository import AIResearchRepository
from app.db.session import Base, create_database_engine, create_session_factory, get_engine, get_session_factory
from app.schemas.ai_research import AIResearchRequest
from app.services.ai_research_read_service import get_ai_research_read_snapshot, get_ai_research_read_snapshot_by_task_id
from app.services.ai_research_write_service import create_ai_research_task_record
from app.services.mock_ai_research_service import get_mock_ai_research


def test_ai_research_read_service_uses_latest_task_metadata(monkeypatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(bind=engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_settings.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        create_ai_research_task_record(
            session,
            AIResearchRequest(
                market=MarketCode.US,
                query="分析 NVDA 最新异动",
                symbols=["NVDA"],
            ),
            route_prefix="/research",
        )
        repository = AIResearchRepository(session)
        task = repository.get_task_by_task_id("research-us-nvda-queued")
        assert task is not None
        evidence = repository.list_evidence(task.task_id)
        assert evidence
        evidence[0].title = "数据库证据标题"
        assert task.result_snapshot is not None
        task.result_snapshot = {
            **task.result_snapshot,
            "headline": "数据库结构化结论",
        }
        session.commit()

    response = build_ai_research_task_response(
        MarketCode.US,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_AI_RESEARCH_DATABASE_READS=True,
            _env_file=None,
        ),
    )

    assert response.task_id == "research-us-nvda-queued"
    assert response.query == "分析 NVDA 最新异动"
    assert response.status == "queued"
    assert response.evidence
    assert response.evidence[0].title == "数据库证据标题"
    assert response.evidence[0].source == "ToolRegistry.run_quant_pipeline.factors"
    assert response.result.headline == "数据库结构化结论"
    assert response.result.evidence_ids


def test_ai_research_task_response_appends_fallback_trace_when_database_read_fails(monkeypatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_settings.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)

    def raise_database_read_error(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("app.api.v1.ai_research.get_ai_research_read_snapshot", raise_database_read_error)

    response = build_ai_research_task_response(
        MarketCode.US,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_AI_RESEARCH_DATABASE_READS=True,
            _env_file=None,
        ),
    )

    assert response.data_status == "unavailable"
    assert response.status == "completed"
    assert response.trace[0].status == "failed"
    assert response.trace[0].agent == "orchestrator"
    assert "RuntimeError" in response.trace[0].summary
    assert response.tool_calls[0].status == "failed"
    assert response.tool_calls[0].tool_name == "AIResearchRepository.read_latest_task"


def test_ai_research_read_service_falls_back_without_database_task() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = AIResearchRepository(session)
        assert repository.list_tasks_by_market("HK") == []

    response = build_ai_research_task_response(
        MarketCode.HK,
        Settings(
            DATABASE_URL="sqlite+pysqlite:///:memory:",
            ENABLE_AI_RESEARCH_DATABASE_READS=False,
            _env_file=None,
        ),
    )

    assert response.market == MarketCode.HK
    assert response.status == "completed"
    assert response.query


def test_ai_research_read_snapshot_overrides_mock_with_database_task() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        create_ai_research_task_record(
            session,
            AIResearchRequest(
                market=MarketCode.CN,
                query="分析宁德时代的趋势和风险",
                symbols=["300750.SZ"],
            ),
            route_prefix="/research",
        )
        repository = AIResearchRepository(session)
        task = repository.get_task_by_task_id("research-cn-300750-sz-queued")
        assert task is not None
        task.result_snapshot = {
            **(task.result_snapshot or {}),
            "headline": "数据库中的 AI 研究结论",
        }
        session.commit()

        fallback = get_mock_ai_research(MarketCode.CN)
        snapshot = get_ai_research_read_snapshot(session, MarketCode.CN, fallback)

    assert snapshot is not None
    assert snapshot.task_id == "research-cn-300750-sz-queued"
    assert snapshot.query == "分析宁德时代的趋势和风险"
    assert snapshot.status == "queued"
    assert snapshot.result.headline == "数据库中的 AI 研究结论"
    assert snapshot.evidence
    assert snapshot.evidence[0].market == MarketCode.CN


def test_ai_research_read_snapshot_by_task_id_returns_database_task() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        create_ai_research_task_record(
            session,
            AIResearchRequest(
                market=MarketCode.HK,
                query="分析腾讯当前量化状态",
                symbols=["00700.HK"],
            ),
            route_prefix="/research",
        )
        snapshot = get_ai_research_read_snapshot_by_task_id(session, "research-hk-00700-hk-queued")

    assert snapshot is not None
    assert snapshot.task_id == "research-hk-00700-hk-queued"
    assert snapshot.market == MarketCode.HK
    assert snapshot.query == "分析腾讯当前量化状态"
    assert snapshot.evidence


def test_ai_research_api_builder_can_read_task_by_id(monkeypatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(bind=engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_settings.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        create_ai_research_task_record(
            session,
            AIResearchRequest(
                market=MarketCode.US,
                query="分析 NVDA 今天异动原因",
                symbols=["NVDA"],
            ),
            route_prefix="/research",
        )

    response = build_ai_research_task_by_id_response(
        "research-us-nvda-queued",
        Settings(
            DATABASE_URL=database_url,
            ENABLE_AI_RESEARCH_DATABASE_READS=True,
            _env_file=None,
        ),
    )

    assert response.task_id == "research-us-nvda-queued"
    assert response.market == MarketCode.US
    assert response.query == "分析 NVDA 今天异动原因"


def test_ai_research_api_builder_returns_404_when_task_missing(monkeypatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    Base.metadata.create_all(bind=engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)

    with pytest.raises(HTTPException) as error:
        build_ai_research_task_by_id_response(
            "missing-task-id",
            Settings(
                DATABASE_URL=database_url,
                ENABLE_AI_RESEARCH_DATABASE_READS=True,
                _env_file=None,
            ),
        )

    assert error.value.status_code == 404
    assert error.value.detail["code"] == "ai_research_task_not_found"
    assert error.value.detail["task_id"] == "missing-task-id"


def test_ai_research_api_builder_returns_404_when_database_reads_disabled() -> None:
    with pytest.raises(HTTPException) as error:
        build_ai_research_task_by_id_response(
            "research-us-nvda-queued",
            Settings(
                ENABLE_AI_RESEARCH_DATABASE_READS=False,
                _env_file=None,
            ),
        )

    assert error.value.status_code == 404
    assert error.value.detail["code"] == "ai_research_database_reads_disabled"
    assert error.value.detail["task_id"] == "research-us-nvda-queued"


def test_ai_research_read_snapshot_returns_none_without_database_task() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        fallback = get_mock_ai_research(MarketCode.US)
        snapshot = get_ai_research_read_snapshot(session, MarketCode.US, fallback)

    assert snapshot is None

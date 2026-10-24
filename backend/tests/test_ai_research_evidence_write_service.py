from app.core.market import MarketCode
from app.db.repositories.ai_research_repository import AIResearchRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.schemas.ai_research import AIResearchRequest
from app.services.ai_research_evidence_write_service import save_ai_research_evidence
from app.services.ai_research_write_service import create_ai_research_task_record
from app.services.mock_ai_research_service import get_mock_ai_research


def test_ai_research_evidence_write_service_saves_response_evidence() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)
    request = AIResearchRequest(
        market=MarketCode.US,
        query="分析 NVDA 今天异动原因",
        symbols=["NVDA"],
    )
    response = get_mock_ai_research(MarketCode.US)

    with session_factory() as session:
        task_response = create_ai_research_task_record(session, request, route_prefix="/research")
        repository = AIResearchRepository(session)
        task = repository.get_task_by_task_id(task_response.task_id)
        assert task is not None

        save_ai_research_evidence(session, task, response)

        saved_evidence = repository.list_evidence(task.task_id)
        assert [item.evidence_id for item in saved_evidence] == [
            item.evidence_id for item in response.evidence
        ]
        assert all(item.task_pk == task.id for item in saved_evidence)
        assert all(item.task_id == task.task_id for item in saved_evidence)
        assert saved_evidence[0].raw_payload is not None
        assert saved_evidence[0].raw_payload["evidence_id"] == response.evidence[0].evidence_id


def test_ai_research_evidence_write_service_replaces_existing_evidence() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)
    request = AIResearchRequest(
        market=MarketCode.HK,
        query="分析港股科技股是否走强",
    )
    first_response = get_mock_ai_research(MarketCode.HK)
    second_response = first_response.model_copy(update={"evidence": first_response.evidence[:1]})

    with session_factory() as session:
        task_response = create_ai_research_task_record(session, request, route_prefix="/research")
        repository = AIResearchRepository(session)
        task = repository.get_task_by_task_id(task_response.task_id)
        assert task is not None

        save_ai_research_evidence(session, task, first_response)
        assert len(repository.list_evidence(task.task_id)) == len(first_response.evidence)

        save_ai_research_evidence(session, task, second_response)
        replaced_evidence = repository.list_evidence(task.task_id)

        assert len(replaced_evidence) == 1
        assert replaced_evidence[0].evidence_id == second_response.evidence[0].evidence_id

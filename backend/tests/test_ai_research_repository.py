from datetime import datetime, timedelta, timezone

from app.db.repositories.ai_research_repository import AIResearchRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models import AgentTask, ResearchEvidence


def _build_task(*, task_id: str = "research-us-nvda-queued", status: str = "queued") -> AgentTask:
    accepted_at = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)
    return AgentTask(
        task_id=task_id,
        market="US",
        query="分析 NVDA 今天异动原因",
        symbols=["NVDA"],
        status=status,
        data_status="realtime",
        timezone="America/New_York",
        route_prefix="/research",
        include_strategy_idea=True,
        result_snapshot=None,
        accepted_at=accepted_at,
        completed_at=None,
    )


def _build_evidence(evidence_id: str, evidence_timestamp: datetime) -> ResearchEvidence:
    return ResearchEvidence(
        task_pk=0,
        task_id="",
        evidence_id=evidence_id,
        evidence_type="tool_output",
        market="US",
        symbol="NVDA",
        title="量化信号 Quant Signals",
        value="signals=2; max_score=0.9000",
        source="ToolRegistry.run_quant_pipeline.signals",
        data_status="realtime",
        evidence_timestamp=evidence_timestamp,
        raw_payload={"score": 0.9},
    )


def test_ai_research_repository_saves_and_updates_task() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = AIResearchRepository(session)
        saved = repository.save_task(_build_task())
        session.commit()
        session.refresh(saved)

        repository.save_task(_build_task(status="completed"))
        session.commit()

        task = repository.get_task_by_task_id("research-us-nvda-queued")
        assert task is not None
        assert task.id == saved.id
        assert task.status == "completed"
        assert task.symbols == ["NVDA"]
        assert repository.list_tasks_by_market("us", status="completed")[0].task_id == task.task_id


def test_ai_research_repository_replaces_and_lists_evidence() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)
    base_time = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)

    with session_factory() as session:
        repository = AIResearchRepository(session)
        task = repository.save_task(_build_task())
        session.commit()
        session.refresh(task)

        repository.replace_evidence(
            task,
            [
                _build_evidence("evidence-late", base_time + timedelta(minutes=2)),
                _build_evidence("evidence-early", base_time),
            ],
        )
        session.commit()

        evidence = repository.list_evidence(task.task_id)
        assert [item.evidence_id for item in evidence] == ["evidence-early", "evidence-late"]
        assert all(item.task_pk == task.id for item in evidence)
        assert all(item.task_id == task.task_id for item in evidence)

        repository.replace_evidence(task, [_build_evidence("evidence-new", base_time + timedelta(minutes=1))])
        session.commit()

        replaced_evidence = repository.list_evidence(task.task_id)
        assert [item.evidence_id for item in replaced_evidence] == ["evidence-new"]

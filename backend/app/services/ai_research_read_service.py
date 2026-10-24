from sqlalchemy.orm import Session

from app.core.market import MarketCode
from app.db.repositories.ai_research_repository import AIResearchRepository
from app.models.ai_research import AgentTask, ResearchEvidence as ResearchEvidenceModel
from app.schemas.ai_research import (
    AIResearchResponse,
    EvidenceType,
    ResearchEvidence,
    ResearchTaskStatus,
    StructuredResearchResult,
)
from app.schemas.market import DataStatus
from app.services.mock_ai_research_service import get_mock_ai_research


def get_ai_research_read_snapshot(
    session: Session,
    market: MarketCode,
    fallback: AIResearchResponse,
) -> AIResearchResponse | None:
    """用 agent_tasks 最近任务覆盖 AI Research 响应元信息；缺少任务时返回 None。"""

    repository = AIResearchRepository(session)
    tasks = repository.list_tasks_by_market(market.value, limit=1)
    if not tasks:
        return None

    task = tasks[0]
    evidence = repository.list_evidence(task.task_id)
    return _task_to_response(task, evidence=evidence, fallback=fallback)


def get_ai_research_read_snapshot_by_task_id(
    session: Session,
    task_id: str,
) -> AIResearchResponse | None:
    """按 task_id 读取 AI Research 任务；缺少任务时返回 None。"""

    repository = AIResearchRepository(session)
    task = repository.get_task_by_task_id(task_id)
    if task is None:
        return None

    fallback = get_mock_ai_research(MarketCode(task.market))
    return _task_to_response(
        task,
        evidence=repository.list_evidence(task.task_id),
        fallback=fallback,
    )


def agent_task_to_debug_payload(task: AgentTask) -> dict[str, object]:
    """把任务转换为测试和调试可读结构，不作为 API 响应直接返回。"""

    return {
        "task_id": task.task_id,
        "market": task.market,
        "query": task.query,
        "status": task.status,
        "symbols": task.symbols,
    }


def _task_to_response(
    task: AgentTask,
    *,
    evidence: list[ResearchEvidenceModel],
    fallback: AIResearchResponse,
) -> AIResearchResponse:
    """把数据库任务和证据合并到 Mock Orchestrator 响应结构中。"""

    return fallback.model_copy(
        update={
            "task_id": task.task_id,
            "query": task.query,
            "status": ResearchTaskStatus(task.status),
            "timestamp": task.completed_at or task.accepted_at,
            "data_status": DataStatus(task.data_status),
            "evidence": [_evidence_to_schema(item) for item in evidence] if evidence else fallback.evidence,
            "result": StructuredResearchResult.model_validate(task.result_snapshot)
            if task.result_snapshot
            else fallback.result,
        }
    )


def _evidence_to_schema(evidence: ResearchEvidenceModel) -> ResearchEvidence:
    """把 research_evidence 表记录转换成 API 证据结构。"""

    return ResearchEvidence(
        evidence_id=evidence.evidence_id,
        evidence_type=EvidenceType(evidence.evidence_type),
        market=MarketCode(evidence.market),
        symbol=evidence.symbol,
        title=evidence.title,
        value=evidence.value,
        source=evidence.source,
        data_status=DataStatus(evidence.data_status),
        timestamp=evidence.evidence_timestamp,
    )

from sqlalchemy.orm import Session

from app.db.repositories.ai_research_repository import AIResearchRepository
from app.models.ai_research import AgentTask, ResearchEvidence
from app.schemas.ai_research import AIResearchResponse


def save_ai_research_evidence(
    session: Session,
    task: AgentTask,
    response: AIResearchResponse,
) -> list[ResearchEvidence]:
    """把 AI Research 响应中的证据替换保存到 research_evidence 表。"""

    repository = AIResearchRepository(session)
    saved_evidence = repository.replace_evidence(
        task,
        [_evidence_to_model(item) for item in response.evidence],
    )
    session.commit()
    return saved_evidence


def _evidence_to_model(evidence) -> ResearchEvidence:
    """把 API 证据结构转换成 research_evidence 表记录。"""

    return ResearchEvidence(
        task_pk=0,
        task_id="",
        evidence_id=evidence.evidence_id,
        evidence_type=evidence.evidence_type.value,
        market=evidence.market.value,
        symbol=evidence.symbol,
        title=evidence.title,
        value=evidence.value,
        source=evidence.source,
        data_status=evidence.data_status.value,
        evidence_timestamp=evidence.timestamp.replace(tzinfo=None),
        raw_payload=evidence.model_dump(mode="json"),
    )

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.repositories.ai_research_repository import AIResearchRepository
from app.models.ai_research import AgentTask
from app.schemas.ai_research import AIResearchRequest, AIResearchTaskCreateResponse
from app.services.ai_research_evidence_write_service import save_ai_research_evidence
from app.services.mock_ai_research_service import create_mock_ai_research_task, get_mock_ai_research


def create_ai_research_task_record(
    session: Session,
    request: AIResearchRequest,
    *,
    route_prefix: str = "/research",
    settings: Settings | None = None,
) -> AIResearchTaskCreateResponse:
    """创建 AI Research 任务回执，并把任务基础信息保存到 agent_tasks 表。"""

    response = create_mock_ai_research_task(request, route_prefix=route_prefix)
    research_response = get_mock_ai_research(
        request.market,
        settings=settings,
        query=request.query,
        symbol=request.symbols[0] if request.symbols else None,
    )
    repository = AIResearchRepository(session)
    saved_task = repository.save_task(
        _response_to_agent_task(
            response,
            request,
            route_prefix=route_prefix,
            result_snapshot=research_response.result.model_dump(mode="json"),
        )
    )
    session.flush()
    session.refresh(saved_task)
    save_ai_research_evidence(session, saved_task, research_response)
    session.refresh(saved_task)
    return response


def _response_to_agent_task(
    response: AIResearchTaskCreateResponse,
    request: AIResearchRequest,
    *,
    route_prefix: str,
    result_snapshot: dict,
) -> AgentTask:
    """把任务创建响应转换成 agent_tasks 表记录。"""

    return AgentTask(
        task_id=response.task_id,
        market=response.market.value,
        query=response.query,
        symbols=request.symbols,
        status=response.status.value,
        data_status=response.data_status.value,
        timezone=response.timezone,
        route_prefix=route_prefix,
        include_strategy_idea=request.include_strategy_idea,
        result_snapshot=result_snapshot,
        accepted_at=response.accepted_at.replace(tzinfo=None),
        completed_at=None,
    )

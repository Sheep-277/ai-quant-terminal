from fastapi import APIRouter, HTTPException, Query, status

from app.agents.llm_client import BailianLLMClient, LLMClientError
from app.core.config import Settings, get_settings
from app.core.market import MarketCode
from app.db.session import get_db_session
from app.schemas.ai_research import (
    AIResearchLLMCheckResponse,
    AIResearchLLMStatusResponse,
    AIResearchRequest,
    AIResearchResponse,
    AIResearchSearchCheckResponse,
    AIResearchSearchStatusResponse,
    AIResearchTaskCreateResponse,
    ResearchAgentType,
    ResearchToolCall,
    ResearchTraceStep,
    ToolCallStatus,
)
from app.schemas.market import DataStatus
from app.providers.search_provider import NewsSearchProvider, SearchProviderError, build_news_search_provider
from app.services.ai_research_read_service import get_ai_research_read_snapshot, get_ai_research_read_snapshot_by_task_id
from app.services.ai_research_write_service import create_ai_research_task_record
from app.services.mock_ai_research_service import create_mock_ai_research_task, get_mock_ai_research


router = APIRouter(prefix="/research", tags=["research"])
legacy_router = APIRouter(prefix="/ai-research", tags=["ai-research"])


@router.post(
    "/tasks",
    response_model=AIResearchTaskCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_research_task(request: AIResearchRequest) -> AIResearchTaskCreateResponse:
    """接收正式 Research 任务；开启数据库写入时保存任务基础信息。"""

    return build_ai_research_task_create_response(request, get_settings(), route_prefix="/research")


def build_ai_research_task_create_response(
    request: AIResearchRequest,
    settings: Settings,
    *,
    route_prefix: str,
) -> AIResearchTaskCreateResponse:
    """根据配置创建 AI Research 任务回执；默认只返回 Mock 回执。"""

    if not settings.enable_ai_research_database_writes:
        return create_mock_ai_research_task(request, route_prefix=route_prefix)

    try:
        session_generator = get_db_session(settings)
        session = next(session_generator)
        try:
            return create_ai_research_task_record(session, request, route_prefix=route_prefix, settings=settings).model_copy(
                update={"storage_source": "database"}
            )
        finally:
            session_generator.close()
    except Exception as exc:
        return create_mock_ai_research_task(request, route_prefix=route_prefix).model_copy(
            update={
                "data_status": DataStatus.UNAVAILABLE,
                "fallback_active": True,
                "fallback_reason": f"数据库 AI Research 任务写入失败，当前仅返回未持久化 Mock 研究任务；错误类型={type(exc).__name__}。",
                "storage_source": "mock_fallback",
            }
        )


@router.get("/task", response_model=AIResearchResponse)
def get_research_task(
    market: MarketCode = Query(default=MarketCode.US, description="当前市场代码：US / HK / CN"),
) -> AIResearchResponse:
    """返回 Research 页面数据；开启数据库读取时优先使用最近任务元信息。"""

    return build_ai_research_task_response(market, get_settings())


@router.get("/llm/status", response_model=AIResearchLLMStatusResponse)
def get_research_llm_status() -> AIResearchLLMStatusResponse:
    """返回 AI Research LLM 配置状态，不发起真实模型调用。"""

    return build_ai_research_llm_status_response(get_settings())


@router.post("/llm/check", response_model=AIResearchLLMCheckResponse)
def check_research_llm_connection() -> AIResearchLLMCheckResponse:
    """显式触发一次百炼 LLM 最小连通性检查。"""

    return build_ai_research_llm_check_response(get_settings())


@router.get("/search/status", response_model=AIResearchSearchStatusResponse)
def get_research_search_status() -> AIResearchSearchStatusResponse:
    """返回 AI Research 公开搜索源配置状态，不发起真实搜索调用。"""

    return build_ai_research_search_status_response(get_settings())


@router.post("/search/check", response_model=AIResearchSearchCheckResponse)
def check_research_search_connection() -> AIResearchSearchCheckResponse:
    """显式触发一次公开搜索源最小连通性检查。"""

    return build_ai_research_search_check_response(get_settings())


def build_ai_research_llm_status_response(settings: Settings) -> AIResearchLLMStatusResponse:
    """构造百炼 LLM 配置诊断结果，供前端和验收时快速排查。"""

    missing_configuration = _get_missing_llm_configuration(settings)
    endpoint = _build_llm_endpoint(settings) if not missing_configuration else None

    if not settings.enable_llm_research:
        next_action = "ENABLE_LLM_RESEARCH=false，AI Research 当前只展示确定性 Quant 结论。"
    elif missing_configuration:
        next_action = f"补全配置：{', '.join(missing_configuration)}。"
    else:
        next_action = "LLM 配置完整；创建 AI Research 任务时会尝试调用百炼摘要。"

    return AIResearchLLMStatusResponse(
        enabled=settings.enable_llm_research,
        configured=settings.enable_llm_research and not missing_configuration,
        model=settings.bailian_model,
        endpoint=endpoint,
        missing_configuration=missing_configuration,
        next_action=next_action,
    )


def build_ai_research_search_status_response(settings: Settings) -> AIResearchSearchStatusResponse:
    """构造公开搜索源配置诊断结果，供前端显示 Tavily/SerpAPI/Mock 状态。"""

    provider_name = settings.search_provider.value
    api_key_configured = bool(settings.search_api_key and settings.search_api_key.strip())
    missing_configuration: list[str] = []
    if provider_name != "mock" and not api_key_configured:
        missing_configuration.append("SEARCH_API_KEY")

    configured = provider_name == "mock" or not missing_configuration
    if provider_name == "mock":
        next_action = "SEARCH_PROVIDER=mock，AI Research 当前只展示本地事件线索。"
    elif missing_configuration:
        next_action = f"补全配置：{', '.join(missing_configuration)}。"
    else:
        next_action = f"公开搜索源 {provider_name} 配置完整；AI Research 会尝试追加公开事件证据。"

    return AIResearchSearchStatusResponse(
        provider_name=provider_name,
        configured=configured,
        api_key_configured=api_key_configured,
        result_limit=settings.search_result_limit,
        timeout_seconds=settings.search_timeout_seconds,
        missing_configuration=missing_configuration,
        next_action=next_action,
    )


def build_ai_research_search_check_response(
    settings: Settings,
    *,
    provider: NewsSearchProvider | None = None,
) -> AIResearchSearchCheckResponse:
    """执行公开搜索源 ping 检查；失败时返回结构化结果而不是 500。"""

    status_response = build_ai_research_search_status_response(settings)
    query = "AI Quant Terminal market news"
    if not status_response.configured:
        return AIResearchSearchCheckResponse(
            ok=False,
            provider_name=status_response.provider_name,
            query=query,
            result_count=0,
            error=status_response.next_action,
            next_action="先补全公开搜索源配置，再执行连通性检查。",
        )

    search_provider = provider or build_news_search_provider(settings)
    try:
        results = search_provider.search(query, limit=1)
    except SearchProviderError as exc:
        return AIResearchSearchCheckResponse(
            ok=False,
            provider_name=status_response.provider_name,
            query=query,
            result_count=0,
            error=str(exc),
            next_action="检查 SEARCH_PROVIDER、SEARCH_API_KEY 和本机网络。",
        )

    preview = results[0]["title"] if results else None
    return AIResearchSearchCheckResponse(
        ok=True,
        provider_name=status_response.provider_name,
        query=query,
        result_count=len(results),
        response_preview=preview,
        next_action="公开搜索源连通性检查通过；AI Research 可尝试追加公开事件证据。",
    )


def build_ai_research_llm_check_response(
    settings: Settings,
    *,
    client: BailianLLMClient | None = None,
) -> AIResearchLLMCheckResponse:
    """执行百炼 LLM ping 检查；失败时返回结构化结果而不是 500。"""

    status_response = build_ai_research_llm_status_response(settings)
    if not status_response.configured:
        return AIResearchLLMCheckResponse(
            ok=False,
            model=settings.bailian_model,
            endpoint=status_response.endpoint,
            error=status_response.next_action,
            next_action="先补全 LLM 配置，再执行连通性检查。",
        )

    llm_client = client or BailianLLMClient(settings, timeout_seconds=8.0)
    try:
        response_preview = llm_client.check_connection()
    except LLMClientError as exc:
        return AIResearchLLMCheckResponse(
            ok=False,
            model=settings.bailian_model,
            endpoint=status_response.endpoint,
            error=str(exc),
            next_action="检查 BAILIAN_API_KEY、BAILIAN_BASE_URL、BAILIAN_MODEL 和本机网络。",
        )

    return AIResearchLLMCheckResponse(
        ok=True,
        model=settings.bailian_model,
        endpoint=status_response.endpoint,
        response_preview=response_preview,
        next_action="百炼 LLM 连通性检查通过；AI Research 可尝试生成 LLM 摘要。",
    )


def build_ai_research_task_response(market: MarketCode, settings: Settings) -> AIResearchResponse:
    """根据配置构造 AI Research 响应；证据和结论当前仍由 Mock Orchestrator 生成。"""

    fallback_response = get_mock_ai_research(market=market, settings=settings)
    if not settings.enable_ai_research_database_reads:
        return fallback_response

    try:
        session_generator = get_db_session(settings)
        session = next(session_generator)
        try:
            snapshot = get_ai_research_read_snapshot(session, market, fallback_response)
            if snapshot is None:
                return fallback_response
            return snapshot
        finally:
            session_generator.close()
    except Exception as error:
        return _append_ai_research_database_fallback_trace(fallback_response, error)


def _append_ai_research_database_fallback_trace(
    fallback_response: AIResearchResponse,
    error: Exception,
) -> AIResearchResponse:
    """数据库读取异常时保留 Mock Research，并在公开轨迹中暴露回退原因。"""

    trace_step = ResearchTraceStep(
        step_id=f"{fallback_response.task_id}-database-read-fallback",
        agent=ResearchAgentType.ORCHESTRATOR,
        status=ToolCallStatus.FAILED,
        title="数据库研究任务读取失败",
        summary=(
            "读取 agent_tasks / research_evidence 失败，"
            f"当前 AI Research 页面已回退到 Mock Orchestrator。错误类型={type(error).__name__}。"
        ),
        started_at=fallback_response.timestamp,
        completed_at=fallback_response.timestamp,
    )
    tool_call = ResearchToolCall(
        tool_call_id=f"{fallback_response.task_id}-database-read",
        agent=ResearchAgentType.ORCHESTRATOR,
        tool_name="AIResearchRepository.read_latest_task",
        status=ToolCallStatus.FAILED,
        started_at=fallback_response.timestamp,
        completed_at=fallback_response.timestamp,
        summary=trace_step.summary,
    )
    return fallback_response.model_copy(
        update={
            "data_status": DataStatus.UNAVAILABLE,
            "trace": [trace_step, *fallback_response.trace],
            "tool_calls": [tool_call, *fallback_response.tool_calls],
        }
    )


@router.get("/tasks/{task_id}", response_model=AIResearchResponse)
def get_research_task_by_id(task_id: str) -> AIResearchResponse:
    """按任务 ID 返回已保存的 AI Research 结果。"""

    return build_ai_research_task_by_id_response(task_id, get_settings())


def build_ai_research_task_by_id_response(task_id: str, settings: Settings) -> AIResearchResponse:
    """查询指定 AI Research 任务；未开启数据库读取或记录不存在时返回 404。"""

    if not settings.enable_ai_research_database_reads:
        raise_ai_research_task_not_found(
            task_id,
            code="ai_research_database_reads_disabled",
            message="AI Research database reads are disabled.",
        )

    session_generator = get_db_session(settings)
    session = next(session_generator)
    try:
        snapshot = get_ai_research_read_snapshot_by_task_id(session, task_id)
        if snapshot is None:
            raise_ai_research_task_not_found(
                task_id,
                code="ai_research_task_not_found",
                message="AI Research task was not found.",
            )
        return snapshot
    finally:
        session_generator.close()


def raise_ai_research_task_not_found(task_id: str, *, code: str, message: str) -> None:
    """返回结构化 404，方便前端区分未开启读取和任务不存在。"""

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": code,
            "message": message,
            "task_id": task_id,
        },
    )


def _get_missing_llm_configuration(settings: Settings) -> list[str]:
    """列出启用百炼 LLM 摘要所需但尚未配置的环境变量。"""

    missing_configuration: list[str] = []
    if not settings.bailian_api_key or not settings.bailian_api_key.strip():
        missing_configuration.append("BAILIAN_API_KEY")
    if not settings.bailian_base_url or not settings.bailian_base_url.strip():
        missing_configuration.append("BAILIAN_BASE_URL")
    return missing_configuration


def _build_llm_endpoint(settings: Settings) -> str | None:
    """复用百炼客户端 URL 规范化规则，生成前端可见的目标 endpoint。"""

    try:
        return BailianLLMClient(settings)._chat_completions_url()
    except LLMClientError:
        return None


@legacy_router.post(
    "/tasks",
    response_model=AIResearchTaskCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_ai_research_task(request: AIResearchRequest) -> AIResearchTaskCreateResponse:
    """兼容旧 AI Research 任务入口，供当前前端继续调用。"""

    return build_ai_research_task_create_response(request, get_settings(), route_prefix="/ai-research")


@legacy_router.get("/task", response_model=AIResearchResponse)
def get_ai_research_task(
    market: MarketCode = Query(default=MarketCode.US, description="当前市场代码：US / HK / CN"),
) -> AIResearchResponse:
    """兼容旧 AI Research 页面查询入口。"""

    return build_ai_research_task_response(market, get_settings())


@legacy_router.get("/llm/status", response_model=AIResearchLLMStatusResponse)
def get_ai_research_llm_status() -> AIResearchLLMStatusResponse:
    """兼容旧 AI Research 路由，返回 LLM 配置状态。"""

    return build_ai_research_llm_status_response(get_settings())


@legacy_router.get("/search/status", response_model=AIResearchSearchStatusResponse)
def get_ai_research_search_status() -> AIResearchSearchStatusResponse:
    """兼容旧 AI Research 路由，返回公开搜索源配置状态。"""

    return build_ai_research_search_status_response(get_settings())


@legacy_router.post("/search/check", response_model=AIResearchSearchCheckResponse)
def check_ai_research_search_connection() -> AIResearchSearchCheckResponse:
    """兼容旧 AI Research 路由，显式检查公开搜索源连通性。"""

    return build_ai_research_search_check_response(get_settings())


@legacy_router.post("/llm/check", response_model=AIResearchLLMCheckResponse)
def check_ai_research_llm_connection() -> AIResearchLLMCheckResponse:
    """兼容旧 AI Research 路由，显式检查 LLM 连通性。"""

    return build_ai_research_llm_check_response(get_settings())


@legacy_router.get("/tasks/{task_id}", response_model=AIResearchResponse)
def get_ai_research_task_by_id(task_id: str) -> AIResearchResponse:
    """兼容旧 AI Research 任务 ID 查询入口。"""

    return build_ai_research_task_by_id_response(task_id, get_settings())

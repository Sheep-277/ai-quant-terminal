from datetime import datetime, timezone
from typing import Any, TypedDict

from app.agents.llm_client import BailianLLMClient, LLMClientError, LLMResearchClient
from app.agents.research_orchestrator import run_research_orchestrator
from app.core.config import SearchProviderMode, Settings
from app.core.config import get_settings
from app.core.market import MarketCode, get_market_context
from app.providers.search_provider import NewsSearchProvider, SearchProviderError, SearchResult, build_news_search_provider
from app.schemas.ai_research import (
    AIResearchRequest,
    AIResearchResponse,
    AIResearchTaskCreateResponse,
    EvidenceType,
    ResearchAgentType,
    ResearchEvidence,
    ResearchTaskStatus,
    ResearchToolCall,
    ToolCallStatus,
)
from app.schemas.market import DataStatus


class AIResearchFixture(TypedDict):
    """AI Research Mock 输入数据结构，供创建回执和 Orchestrator 复用。"""

    query: str
    symbol: str
    data_status: DataStatus
    closes: list[float]
    fundamentals: dict[str, float | None]
    entry_conditions: list[dict[str, Any]]
    exit_conditions: list[dict[str, Any]]


AI_RESEARCH_FIXTURES: dict[MarketCode, AIResearchFixture] = {
    MarketCode.US: {
        "query": "为什么 NVDA 今天异动？",
        "symbol": "NVDA",
        "data_status": DataStatus.REALTIME,
        "closes": [float(value) for value in range(100, 131)],
        "fundamentals": {"roe": 0.18, "roic": 0.12, "gross_margin": 0.42},
        "entry_conditions": [
            {"field": "momentum_20d", "operator": "gt", "value": 0.08},
            {"field": "composite_score", "operator": "gte", "value": 0.7},
        ],
        "exit_conditions": [],
    },
    MarketCode.HK: {
        "query": "港股科技股今天为什么走强？",
        "symbol": "00700.HK",
        "data_status": DataStatus.DELAYED,
        "closes": [float(value) for value in range(80, 111)],
        "fundamentals": {"roe": 0.14, "roic": 0.1, "gross_margin": 0.36},
        "entry_conditions": [
            {"field": "momentum_20d", "operator": "gt", "value": 0.06},
        ],
        "exit_conditions": [],
    },
    MarketCode.CN: {
        "query": "A 股新能源链是否出现机会？",
        "symbol": "300750.SZ",
        "data_status": DataStatus.DELAYED,
        "closes": [
            100.0,
            101.0,
            99.0,
            104.0,
            96.0,
            106.0,
            94.0,
            108.0,
            92.0,
            110.0,
            90.0,
            112.0,
            88.0,
            114.0,
            86.0,
            116.0,
            84.0,
            118.0,
            82.0,
            120.0,
            80.0,
            122.0,
            78.0,
            124.0,
            76.0,
            126.0,
            74.0,
            128.0,
            72.0,
            130.0,
            70.0,
        ],
        "fundamentals": {"roe": 0.12, "roic": 0.08, "gross_margin": 0.28},
        "entry_conditions": [
            {"field": "momentum_20d", "operator": "gt", "value": 0.05},
        ],
        "exit_conditions": [
            {"field": "volatility_20d", "operator": "gt", "value": 0.45},
        ],
    },
}


def create_mock_ai_research_task(
    request: AIResearchRequest,
    *,
    route_prefix: str = "/ai-research",
) -> AIResearchTaskCreateResponse:
    """创建 AI Research Mock 任务回执，不启动真实异步执行。"""

    context = get_market_context(request.market)
    fixture = AI_RESEARCH_FIXTURES[request.market]
    settings = get_settings()
    api_prefix = settings.api_prefix.rstrip("/")
    normalized_route_prefix = route_prefix if route_prefix.startswith("/") else f"/{route_prefix}"
    task_id = _build_mock_task_id(request)

    return AIResearchTaskCreateResponse(
        task_id=task_id,
        market=request.market,
        query=request.query,
        status=ResearchTaskStatus.QUEUED,
        accepted_at=datetime.now(timezone.utc),
        timezone=context.timezone,
        data_status=fixture["data_status"],
        poll_url=f"{api_prefix}{normalized_route_prefix}/tasks/{task_id}",
    )


def get_mock_ai_research(
    market: MarketCode,
    *,
    settings: Settings | None = None,
    llm_client: LLMResearchClient | None = None,
    search_provider: NewsSearchProvider | None = None,
    query: str | None = None,
    symbol: str | None = None,
) -> AIResearchResponse:
    """生成 AI Research Mock 响应，经由 Orchestrator 和 Tool Registry 生成。"""

    fixture = AI_RESEARCH_FIXTURES[market]
    resolved_settings = settings or get_settings()
    resolved_llm_client = llm_client or _build_llm_client(resolved_settings)
    resolved_query = query.strip() if query and query.strip() else fixture["query"]
    resolved_symbol = symbol.strip().upper() if symbol and symbol.strip() else fixture["symbol"]

    response = run_research_orchestrator(
        market=market,
        query=resolved_query,
        symbol=resolved_symbol,
        closes=fixture["closes"],
        fundamentals=fixture["fundamentals"],
        entry_conditions=fixture["entry_conditions"],
        exit_conditions=fixture["exit_conditions"],
        data_status=fixture["data_status"],
        llm_client=resolved_llm_client,
    )
    return _append_search_event_evidence(
        response,
        settings=resolved_settings,
        search_provider=search_provider,
    )


def _append_search_event_evidence(
    response: AIResearchResponse,
    *,
    settings: Settings,
    search_provider: NewsSearchProvider | None = None,
) -> AIResearchResponse:
    """按配置追加公开搜索事件证据；失败时只追加工具状态，不影响量化结论。"""

    if settings.search_provider == SearchProviderMode.MOCK and search_provider is None:
        return response

    provider = search_provider or build_news_search_provider(settings)
    started_at = datetime.now(timezone.utc)
    try:
        results = provider.search(_build_search_query(response), limit=settings.search_result_limit)
    except SearchProviderError as exc:
        return response.model_copy(
            update={
                "tool_calls": [
                    *response.tool_calls,
                    _build_search_tool_call(
                        response,
                        status=ToolCallStatus.FAILED,
                        started_at=started_at,
                        summary=f"公开搜索源调用失败，已保留确定性 Quant 结论。原因={_format_search_error(exc)}。",
                    ),
                ]
            }
        )

    if not results:
        return response.model_copy(
            update={
                "tool_calls": [
                    *response.tool_calls,
                    _build_search_tool_call(
                        response,
                        status=ToolCallStatus.COMPLETED,
                        started_at=started_at,
                        summary="公开搜索源调用完成，但未返回可展示事件线索。",
                    ),
                ]
            }
        )

    event_evidence = _build_search_evidence(response, results)
    return response.model_copy(
        update={
            "tool_calls": [
                *response.tool_calls,
                _build_search_tool_call(
                    response,
                    status=ToolCallStatus.COMPLETED,
                    started_at=started_at,
                    summary=f"已调用公开搜索源，追加 {len(event_evidence)} 条事件证据。",
                ),
            ],
            "evidence": [*response.evidence, *event_evidence],
            "result": response.result.model_copy(
                update={
                    "evidence_ids": [
                        *response.result.evidence_ids,
                        *[item.evidence_id for item in event_evidence],
                    ]
                }
            ),
        }
    )


def _build_search_query(response: AIResearchResponse) -> str:
    """把研究问题、市场和标的组合成搜索关键词。"""

    market_label_map = {
        MarketCode.US: "US stock market",
        MarketCode.HK: "Hong Kong stock market",
        MarketCode.CN: "China A-share market",
    }
    return f"{response.query} {response.result.headline} {market_label_map[response.market]}"


def _build_search_evidence(
    response: AIResearchResponse,
    results: list[SearchResult],
) -> list[ResearchEvidence]:
    """把搜索结果转换为 AI Research 可审计事件证据。"""

    evidence_prefix = f"evidence-{response.market.value.lower()}-{response.result.headline.split()[0].lower()}-event"
    return [
        ResearchEvidence(
            evidence_id=f"{evidence_prefix}-{index:03d}",
            evidence_type=EvidenceType.EVENT,
            market=response.market,
            symbol=response.evidence[0].symbol if response.evidence else None,
            title=result["title"],
            value=_format_search_result_value(result),
            source=result["source"],
            data_status=DataStatus.DELAYED,
            timestamp=response.timestamp,
        )
        for index, result in enumerate(results, start=1)
    ]


def _format_search_result_value(result: SearchResult) -> str:
    """压缩搜索结果摘要，保留链接便于验收时追溯来源。"""

    snippet = " ".join(result["snippet"].split())
    url = result["url"]
    if result["published_at"]:
        return f"{snippet}; published_at={result['published_at']}; url={url}"
    return f"{snippet}; url={url}"


def _build_search_tool_call(
    response: AIResearchResponse,
    *,
    status: ToolCallStatus,
    started_at: datetime,
    summary: str,
) -> ResearchToolCall:
    """生成公开搜索工具调用记录，供前端 Tool Calls 表展示。"""

    return ResearchToolCall(
        tool_call_id=f"{response.task_id}-web-search",
        agent=ResearchAgentType.EVENT,
        tool_name="web_search",
        status=status,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        summary=summary,
    )


def _format_search_error(exc: Exception, *, max_length: int = 240) -> str:
    """生成可展示的搜索失败原因，避免把过长网络错误塞进表格。"""

    message = " ".join(str(exc).split()) or type(exc).__name__
    if len(message) <= max_length:
        return message
    return f"{message[:max_length]}..."


def _build_llm_client(settings: Settings) -> LLMResearchClient | None:
    """按配置创建百炼客户端；默认关闭，避免开发和测试误触发外部调用。"""

    if not settings.enable_llm_research:
        return None

    missing_configuration = _get_missing_llm_configuration(settings)
    if missing_configuration:
        return _MisconfiguredLLMClient(missing_configuration)

    client = BailianLLMClient(settings)
    return client if client.is_configured() else _MisconfiguredLLMClient(("BAILIAN_API_KEY", "BAILIAN_BASE_URL"))


def _get_missing_llm_configuration(settings: Settings) -> tuple[str, ...]:
    """列出启用 LLM 研究后仍缺失的必要配置项。"""

    missing: list[str] = []
    if not settings.bailian_api_key:
        missing.append("BAILIAN_API_KEY")
    if not settings.bailian_base_url:
        missing.append("BAILIAN_BASE_URL")
    return tuple(missing)


class _MisconfiguredLLMClient:
    """配置不完整时的占位客户端，用于在 AI Research Trace 中暴露可见失败原因。"""

    def __init__(self, missing_configuration: tuple[str, ...]) -> None:
        self._missing_configuration = missing_configuration

    def summarize_research(self, **_kwargs: Any) -> str:
        """阻止真实调用，并把缺失配置转换为 Orchestrator 可展示的失败原因。"""

        missing_text = ", ".join(self._missing_configuration)
        raise LLMClientError(f"ENABLE_LLM_RESEARCH=true，但缺少配置：{missing_text}")


def _build_mock_task_id(request: AIResearchRequest) -> str:
    """生成稳定可读的 Mock 任务 ID，真实任务系统后续会改为数据库 ID。"""

    subject = request.symbols[0] if request.symbols else "general"
    normalized_subject = subject.lower().replace(".", "-")
    return f"research-{request.market.value.lower()}-{normalized_subject}-queued"

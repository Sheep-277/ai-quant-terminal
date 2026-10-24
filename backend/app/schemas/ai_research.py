from datetime import datetime
from enum import StrEnum
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.market import MarketCode
from app.schemas.market import DataStatus, Direction


SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.-]+$")


class ResearchTaskStatus(StrEnum):
    """AI 研究任务状态，当前只用于 Mock 展示，不启动真实异步任务。"""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchAgentType(StrEnum):
    """V1 规划的 Agent 类型，保持 Orchestrator 与专业 Agent 边界清晰。"""

    ORCHESTRATOR = "orchestrator"
    MARKET_ANALYST = "market_analyst"
    FUNDAMENTAL = "fundamental"
    VALUATION = "valuation"
    EVENT = "event"
    STRATEGY = "strategy"
    RISK = "risk"


class ToolCallStatus(StrEnum):
    """工具调用状态，用于前端展示可审计 Research Trace。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvidenceType(StrEnum):
    """证据类型，区分行情、指标、新闻和规则等不同来源。"""

    MARKET_DATA = "market_data"
    FUNDAMENTAL = "fundamental"
    VALUATION = "valuation"
    EVENT = "event"
    RISK = "risk"
    TOOL_OUTPUT = "tool_output"


class ResearchHorizon(StrEnum):
    """AI Research 结论适用周期，避免后端返回任意字符串。"""

    SHORT_TERM = "short_term"
    RISK_REVIEW = "risk_review"
    WATCHLIST = "watchlist"


class AIResearchRequest(BaseModel):
    """POST /api/v1/research/tasks 的请求合同，后续由 Orchestrator 消费。"""

    model_config = ConfigDict(frozen=True)

    market: MarketCode
    query: str = Field(min_length=1, max_length=2000)
    symbols: list[str] = Field(default_factory=list, max_length=20)
    include_strategy_idea: bool = False

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, symbols: list[str]) -> list[str]:
        """规范化股票代码输入，但不根据代码推断市场。"""

        normalized_symbols: list[str] = []
        for symbol in symbols:
            normalized_symbol = symbol.strip().upper()
            if not normalized_symbol:
                raise ValueError("symbol must not be empty")
            if not SYMBOL_PATTERN.fullmatch(normalized_symbol):
                raise ValueError("symbol contains unsupported characters")
            normalized_symbols.append(normalized_symbol)

        return normalized_symbols


class AIResearchTaskCreateResponse(BaseModel):
    """AI Research 任务创建后的响应合同，当前只预留异步任务入口。"""

    model_config = ConfigDict(frozen=True)

    task_id: str
    market: MarketCode
    query: str
    status: ResearchTaskStatus
    accepted_at: datetime
    timezone: str
    data_status: DataStatus
    poll_url: str
    fallback_active: bool = False
    fallback_reason: str | None = None
    storage_source: str = "mock"

    @field_validator("poll_url")
    @classmethod
    def validate_poll_url(cls, poll_url: str) -> str:
        """限制轮询地址为后端相对路径，避免响应中混入外部 URL。"""

        if not poll_url.startswith("/"):
            raise ValueError("poll_url must be a relative path")
        if poll_url.startswith("//") or "://" in poll_url:
            raise ValueError("poll_url must not be an external URL")

        return poll_url


class ResearchToolCall(BaseModel):
    """Agent 对工具的一次受控调用记录，不包含私有思维链。"""

    model_config = ConfigDict(frozen=True)

    tool_call_id: str
    agent: ResearchAgentType
    tool_name: str
    status: ToolCallStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    summary: str


class ResearchEvidence(BaseModel):
    """支撑 AI Research 结论的结构化证据。"""

    model_config = ConfigDict(frozen=True)

    evidence_id: str
    evidence_type: EvidenceType
    market: MarketCode
    symbol: str | None = None
    title: str
    value: str
    source: str
    data_status: DataStatus
    timestamp: datetime


class ResearchTraceStep(BaseModel):
    """研究执行轨迹中的一个公开步骤，只展示状态和摘要。"""

    model_config = ConfigDict(frozen=True)

    step_id: str
    agent: ResearchAgentType
    status: ToolCallStatus
    title: str
    summary: str
    started_at: datetime
    completed_at: datetime | None = None


class StructuredResearchResult(BaseModel):
    """AI Research 的结构化结论，必须绑定证据而不是只给自然语言判断。"""

    model_config = ConfigDict(frozen=True)

    headline: str
    direction: Direction
    confidence: float = Field(ge=0, le=1)
    horizon: ResearchHorizon
    key_points: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class AIResearchResponse(BaseModel):
    """GET /api/v1/research/task 的响应合同。"""

    model_config = ConfigDict(frozen=True)

    task_id: str
    market: MarketCode
    query: str
    status: ResearchTaskStatus
    timestamp: datetime
    timezone: str
    data_status: DataStatus
    trace: list[ResearchTraceStep]
    tool_calls: list[ResearchToolCall]
    evidence: list[ResearchEvidence]
    result: StructuredResearchResult


class AIResearchLLMStatusResponse(BaseModel):
    """AI Research LLM 配置检查响应，不触发真实模型调用。"""

    model_config = ConfigDict(frozen=True)

    enabled: bool
    configured: bool
    provider_name: str = "bailian"
    model: str
    endpoint: str | None = None
    missing_configuration: list[str] = Field(default_factory=list)
    next_action: str


class AIResearchLLMCheckResponse(BaseModel):
    """AI Research LLM 连通性检查响应，会由调用方显式触发真实模型请求。"""

    model_config = ConfigDict(frozen=True)

    ok: bool
    provider_name: str = "bailian"
    model: str
    endpoint: str | None = None
    response_preview: str | None = None
    error: str | None = None
    next_action: str


class AIResearchSearchStatusResponse(BaseModel):
    """AI Research 公开搜索源配置状态，不触发真实搜索请求。"""

    model_config = ConfigDict(frozen=True)

    provider_name: str
    configured: bool
    api_key_configured: bool
    result_limit: int
    timeout_seconds: float
    missing_configuration: list[str] = Field(default_factory=list)
    next_action: str


class AIResearchSearchCheckResponse(BaseModel):
    """AI Research 公开搜索源连通性检查响应，由用户显式触发真实搜索请求。"""

    model_config = ConfigDict(frozen=True)

    ok: bool
    provider_name: str
    query: str
    result_count: int
    response_preview: str | None = None
    error: str | None = None
    next_action: str

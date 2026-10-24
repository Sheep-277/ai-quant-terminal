from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.market import MarketCode
from app.schemas.market import DataStatus, Direction
from app.schemas.stock import StockQuantSignal


class MonitorStreamStatus(StrEnum):
    """快照记录的流状态，不代表浏览器或真实行情源的当前连接状态。"""

    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"


class MonitorSignalSeverity(StrEnum):
    """监控信号严重程度，用于区分普通提示和需要重点关注的风险。"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class MonitorSource(StrEnum):
    """监控事件来源，保持 FAST PATH 和 AI PATH 边界清晰。"""

    FAST_PATH = "FAST_PATH"
    AI_PATH = "AI_PATH"
    RISK_ENGINE = "RISK_ENGINE"
    PROVIDER = "PROVIDER"


class MonitorStreamHealth(BaseModel):
    """实时流健康状态，当前为 Mock 心跳数据。"""

    model_config = ConfigDict(frozen=True)

    status: MonitorStreamStatus
    latency_ms: int = Field(ge=0)
    last_heartbeat_at: datetime
    reconnect_attempts: int = Field(ge=0)
    # 仅扩展监控合同，不改变市场行情模块的公共 DataStatus。
    data_status: DataStatus | Literal["mock"]


class MonitorSignal(BaseModel):
    """FAST PATH 产生的结构化信号，必须显式绑定市场和标的。"""

    model_config = ConfigDict(frozen=True)

    signal_id: str
    market: MarketCode
    symbol: str
    title: str
    direction: Direction
    severity: MonitorSignalSeverity
    score: float = Field(ge=0, le=1)
    triggered_at: datetime
    source: str | None = None
    data_origin: Literal["seed", "mock", "unknown"] = "unknown"
    evidence: list[str] = Field(default_factory=list)


class MonitorEvent(BaseModel):
    """AI PATH 或风控侧产生的事件摘要，不包含模型私有思维链。"""

    model_config = ConfigDict(frozen=True)

    event_id: str
    market: MarketCode
    source: MonitorSource
    title: str
    summary: str
    impact: Direction
    confidence: float = Field(ge=0, le=1)
    created_at: datetime


class MonitorProvenance(BaseModel):
    """分区数据来源；未知值不推断为真实行情，心跳也不等同于请求时间。"""

    model_config = ConfigDict(frozen=True)

    transport: Literal["rest_polling", "unknown"] = "unknown"
    stream_source: Literal["mock", "unknown"] = "unknown"
    signal_source: Literal["mock", "database", "unknown"] = "unknown"
    event_source: Literal["mock", "mixed", "unknown"] = "unknown"
    heartbeat_basis: Literal["mock_clock", "latest_signal", "unknown"] = "unknown"


class MonitorResponse(BaseModel):
    """GET /api/v1/monitor/stream 的响应合同。"""

    model_config = ConfigDict(frozen=True)

    market: MarketCode
    timestamp: datetime
    timezone: str
    currency: str
    provenance: MonitorProvenance = Field(default_factory=MonitorProvenance)
    stream: MonitorStreamHealth
    signals: list[MonitorSignal]
    events: list[MonitorEvent]


class MonitorCalculatedSignalsResponse(BaseModel):
    """公开价格输入的单标的计算结果，不包含模拟连接或事件数据。"""

    model_config = ConfigDict(frozen=True)

    market: MarketCode
    symbol: str
    timezone: str
    currency: str
    source: str
    data_status: DataStatus
    timestamp: datetime
    bar_count: int = Field(ge=21)
    calculation_scope: Literal["price_only"] = "price_only"
    signals: list[StockQuantSignal]

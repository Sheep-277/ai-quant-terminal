from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.market import DataStatus


class ProviderStatusResponse(BaseModel):
    """Response contract for GET /api/v1/provider/status."""

    model_config = ConfigDict(frozen=True)

    provider_name: str
    mode: str
    ready: bool
    data_status: DataStatus
    fallback_active: bool
    fallback_reason: str | None
    source_type: str = "mock"
    active_source: str = "provider"
    missing_configuration: list[str] = Field(default_factory=list)
    next_action: str | None = None
    last_logged_at: datetime | None = None
    recent_log_count: int = Field(default=0, ge=0)


class ProviderStatusLogItem(BaseModel):
    """单条 Provider 状态日志，用于展示数据源健康检查历史。"""

    model_config = ConfigDict(frozen=True)

    id: int
    provider_name: str
    mode: str
    ready: bool
    data_status: DataStatus
    fallback_active: bool
    fallback_reason: str | None
    checked_at: datetime


class ProviderStatusLogListResponse(BaseModel):
    """GET /api/v1/provider/status/logs 的响应合同。"""

    model_config = ConfigDict(frozen=True)

    items: list[ProviderStatusLogItem] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    database_available: bool = True
    fallback_reason: str | None = None

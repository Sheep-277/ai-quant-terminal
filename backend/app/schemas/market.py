from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.market import MarketCode


class DataStatus(StrEnum):
    REALTIME = "realtime"
    DELAYED = "delayed"
    UNAVAILABLE = "unavailable"


class Direction(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    WARNING = "warning"


class MarketEventOrigin(StrEnum):
    """市场事件的可观察来源类别，避免把样例或系统提示误读为真实新闻。"""

    MOCK_SAMPLE = "mock_sample"
    SYSTEM = "system"
    NEWS = "news"


class MarketIndex(BaseModel):
    """A headline index or macro metric shown in the market overview tape."""

    model_config = ConfigDict(frozen=True)

    name: str
    symbol: str
    value: float | None
    change_percent: float | None
    status: DataStatus
    source: str = "mock_provider"
    timestamp: datetime | None = None


class MarketBreadth(BaseModel):
    """Market breadth summarizes how broad the current move is."""

    model_config = ConfigDict(frozen=True)

    advancers_percent: float | None = Field(ge=0, le=1)
    decliners_percent: float | None = Field(ge=0, le=1)
    unchanged_percent: float | None = Field(ge=0, le=1)
    new_highs: int | None = Field(ge=0)
    new_lows: int | None = Field(ge=0)
    source: str
    status: DataStatus
    timestamp: datetime | None = None
    sample_size: int | None = Field(default=None, ge=0)
    sample_sources: list[str] = Field(default_factory=list)
    excluded_sample_size: int = Field(default=0, ge=0)


class SectorPerformance(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    change_percent: float
    direction: Direction
    source: str
    status: DataStatus
    timestamp: datetime | None = None


class MarketEvent(BaseModel):
    """Structured event item for the live event stream and AI market brief."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    source: str
    origin: MarketEventOrigin
    title: str
    impact: str
    confidence: float = Field(ge=0, le=1)


class MarketChartBar(BaseModel):
    """市场总览图表使用的指数历史 K 线。"""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = Field(ge=0)
    data_status: DataStatus
    source: str


class MarketWatchlistQuote(BaseModel):
    """本地股票池的逐股报价；缺失或样例不补零，不包含虚构的信号与风险结论。"""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    market: MarketCode
    symbol: str
    name: str
    currency: str
    timezone: str
    price: float | None = Field(gt=0)
    change_amount: float | None
    change_percent: float | None
    volume: int | None = Field(ge=0)
    turnover: float | None = Field(ge=0)
    source: str
    status: DataStatus
    timestamp: datetime | None


class MarketOverviewResponse(BaseModel):
    """Response contract for GET /api/v1/market/overview."""

    model_config = ConfigDict(frozen=True)

    market: MarketCode
    timestamp: datetime
    timezone: str
    currency: str
    benchmark: str
    data_status: DataStatus
    indices: list[MarketIndex]
    breadth: MarketBreadth
    chart_bars: list[MarketChartBar] = Field(default_factory=list)
    sectors: list[SectorPerformance]
    events: list[MarketEvent]
    # None 表示未使用本地股票池；[] 表示已读取但没有启用的普通股。
    watchlist: list[MarketWatchlistQuote] | None = None


class MarketQuoteRefreshRequest(BaseModel):
    """手动刷新必须指定市场，默认只预览，不接受多余或隐式写入参数。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    market: MarketCode
    dry_run: bool = Field(default=True, strict=True)


class MarketQuoteRefreshItem(BaseModel):
    """每只股票独立的执行结果；HTTP 成功并不等于全部股票更新成功。"""

    model_config = ConfigDict(frozen=True)

    symbol: str
    status: Literal["updated", "would_update", "skipped", "failed"]
    reason: str | None


class MarketQuoteRefreshResponse(BaseModel):
    """响应仅在事务成功结束后发出，不暴露原始供应商或数据库异常。"""

    model_config = ConfigDict(frozen=True)

    market: MarketCode
    dry_run: bool
    items: list[MarketQuoteRefreshItem]

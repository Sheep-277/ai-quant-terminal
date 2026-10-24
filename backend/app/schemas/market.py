from datetime import datetime
from enum import StrEnum

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

    advancers_percent: float = Field(ge=0, le=1)
    decliners_percent: float = Field(ge=0, le=1)
    unchanged_percent: float = Field(ge=0, le=1)
    new_highs: int = Field(ge=0)
    new_lows: int = Field(ge=0)
    source: str
    status: DataStatus
    timestamp: datetime | None = None


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

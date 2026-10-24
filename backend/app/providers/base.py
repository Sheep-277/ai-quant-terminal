from datetime import date, datetime
from typing import NotRequired, Protocol, TypedDict

from app.core.market import MarketCode
from app.schemas.market import DataStatus, Direction, MarketEventOrigin


class ProviderQuote(TypedDict):
    """Provider 标准行情快照，真实数据源接入时应优先转换到这个结构。"""

    price: float
    change: float
    change_percent: float
    volume: int
    turnover: float
    data_status: DataStatus
    timestamp: NotRequired[datetime]


class ProviderAssetProfile(TypedDict):
    """Provider 标准标的资料，避免 service 依赖具体供应商的 profile 字段。"""

    symbol: str
    name: str
    exchange: str
    sector: str
    industry: str


class ProviderBar(TypedDict):
    """Provider 标准 K 线数据，使用相对日序号保持 Mock 数据可重复。"""

    offset: int
    timestamp: NotRequired[datetime | str]
    data_status: NotRequired[DataStatus]
    source: NotRequired[str]
    open: float
    high: float
    low: float
    close: float
    volume: int


class ProviderFinancials(TypedDict):
    """Provider 标准财务指标，先覆盖个股研究页面需要的核心字段。"""

    pe_ttm: float
    pb: float
    ps_ttm: float
    pfcf_ttm: float
    roe_ttm: float
    roic_ttm: float
    gross_margin_ttm: float
    operating_margin_ttm: float
    fcf_ttm: float
    operating_cash_flow_ttm: float
    capex_ttm: float


class ProviderResearchNotes(TypedDict):
    """Provider 标准研究说明，承接摘要、风险提示和方向判断的非结构化部分。"""

    risk_flags: list[str]
    summary_points: list[str]
    direction: Direction
    fallback_symbol: str | None


class ProviderMarketIndex(TypedDict):
    """Provider 标准指数快照，用于市场总览顶部行情带。"""

    name: str
    symbol: str
    value: float | None
    change_percent: float | None
    data_status: NotRequired[DataStatus]
    source: NotRequired[str]
    timestamp: NotRequired[datetime | str | None]


class ProviderMarketOverviewData(TypedDict):
    """市场总览的两组独立输入，保留逐项来源、状态和供应商时间。"""

    indices: list[ProviderMarketIndex]
    bars: list[ProviderBar]


class ProviderMarketBreadth(TypedDict):
    """Provider 标准市场宽度，描述上涨、下跌和平盘标的占比。"""

    advancers_percent: float
    decliners_percent: float
    unchanged_percent: float
    new_highs: int
    new_lows: int
    source: str
    data_status: DataStatus
    timestamp: NotRequired[datetime | str | None]


class ProviderSectorPerformance(TypedDict):
    """Provider 标准行业表现，方向由 service 根据涨跌幅统一推导。"""

    name: str
    change_percent: float
    source: str
    data_status: DataStatus
    timestamp: NotRequired[datetime | str | None]


class ProviderMarketEvent(TypedDict):
    """Provider 标准市场事件，供 service 转换为 API 事件流。"""

    source: str
    origin: MarketEventOrigin
    title: str
    impact: str
    confidence: float


class ProviderStatus(TypedDict):
    """Provider 运行状态，供 service 判断数据源是否就绪以及是否发生回退。"""

    provider_name: str
    mode: str
    ready: bool
    data_status: DataStatus
    fallback_active: bool
    fallback_reason: str | None
    source_type: NotRequired[str]
    active_source: NotRequired[str]
    missing_configuration: NotRequired[list[str]]
    next_action: NotRequired[str | None]


class MarketDataProvider(Protocol):
    """市场数据 Provider 合同，隔离 service 与真实/Mock 数据源。"""

    def get_provider_status(self) -> ProviderStatus:
        """返回当前 Provider 的可观测运行状态。"""

    def get_default_stock_symbol(self, market: MarketCode) -> str:
        """返回指定市场的默认研究标的。"""

    def supports_symbol(self, market: MarketCode, symbol: str) -> bool:
        """判断 Provider 是否能直接提供指定市场和标的的数据。"""

    def get_quote(self, market: MarketCode, symbol: str) -> ProviderQuote:
        """返回标准行情快照，真实 Provider 应优先实现这个接口。"""

    def get_asset_profile(self, market: MarketCode, symbol: str) -> ProviderAssetProfile:
        """返回标准标的资料，真实 Provider 应把供应商字段转换到这个结构。"""

    def get_bars(
        self,
        market: MarketCode,
        symbol: str,
        *,
        interval: str = "1d",
        count: int = 30,
        start: date | None = None,
        end: date | None = None,
    ) -> list[ProviderBar]:
        """返回标准 K 线序列，真实 Provider 应显式处理周期和时间边界。"""

    def get_financials(self, market: MarketCode, symbol: str) -> ProviderFinancials:
        """返回标准财务指标，避免 service 直接解包 Provider fixture。"""

    def get_research_notes(self, market: MarketCode, symbol: str) -> ProviderResearchNotes:
        """返回标准研究说明，避免 service 依赖 Mock fixture 的整包结构。"""

    def get_market_data_status(self, market: MarketCode) -> DataStatus:
        """返回指定市场当前数据状态，例如实时、延迟或不可用。"""

    def get_market_indices(self, market: MarketCode) -> list[ProviderMarketIndex]:
        """返回市场总览需要展示的核心指数。"""

    def get_market_overview_data(
        self,
        market: MarketCode,
        chart_symbol: str,
        *,
        interval: str = "1d",
        count: int = 30,
    ) -> ProviderMarketOverviewData:
        """读取总览指数和图表序列；并发能力由 Provider 自身决定。"""

    def get_market_breadth(self, market: MarketCode) -> ProviderMarketBreadth:
        """返回市场宽度数据。"""

    def get_sector_performance(self, market: MarketCode) -> list[ProviderSectorPerformance]:
        """返回行业或板块表现。"""

    def get_market_events(self, market: MarketCode) -> list[ProviderMarketEvent]:
        """返回 Provider 原始市场事件。"""

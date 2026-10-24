from datetime import datetime
from enum import StrEnum
import re
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.market import MarketCode
from app.schemas.market import DataStatus, Direction


SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.-]+$")


class StockResearchQuery(BaseModel):
    """GET /stock/research 的查询参数合同，统一处理 market 和 symbol 校验。"""

    model_config = ConfigDict(frozen=True)

    market: MarketCode = Field(default=MarketCode.US, description="当前市场代码：US / HK / CN")
    symbol: str | None = Field(default=None, max_length=32, description="股票代码；不传时按市场使用默认 Mock 标的")

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, symbol: str | None) -> str | None:
        """规范化股票代码，拒绝空字符串和不受支持的特殊字符。"""

        if symbol is None:
            return None

        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be empty")
        if not SYMBOL_PATTERN.fullmatch(normalized_symbol):
            raise ValueError("symbol contains unsupported characters")

        return normalized_symbol


class StockAssetType(StrEnum):
    """个股研究当前只覆盖普通股票，后续可扩展 ETF、REIT 等资产类型。"""

    COMMON_STOCK = "common_stock"


class KLineInterval(StrEnum):
    """K 线周期枚举，避免接口调用方用随意字符串表达时间粒度。"""

    ONE_DAY = "1d"


class StockProfile(BaseModel):
    """股票基础资料，用于页面标题、标的摘要和市场归属展示。"""

    model_config = ConfigDict(frozen=True)

    market: MarketCode
    symbol: str
    name: str
    asset_type: StockAssetType
    exchange: str
    currency: str
    timezone: str
    sector: str
    industry: str


class StockQuote(BaseModel):
    """最新行情快照，所有涨跌幅均使用小数表达，例如 0.0123 表示 1.23%。"""

    model_config = ConfigDict(frozen=True)

    price: float = Field(gt=0)
    change: float
    change_percent: float
    volume: int = Field(ge=0)
    turnover: float = Field(ge=0)
    timestamp: datetime | None = Field(default=None, description="供应商或数据库报价时间；缺失时为 null，不以读取时间代替")
    data_status: DataStatus


class ValuationMetrics(BaseModel):
    """估值指标用于判断股票价格相对盈利、净资产和自由现金流是否偏贵。"""

    model_config = ConfigDict(frozen=True)

    pe_ttm: float | None = Field(default=None, description="PE TTM 市盈率")
    pb: float | None = Field(default=None, description="PB 市净率")
    ps_ttm: float | None = Field(default=None, description="PS TTM 市销率")
    pfcf_ttm: float | None = Field(default=None, description="P/FCF TTM 市值自由现金流比")


class ProfitabilityMetrics(BaseModel):
    """盈利能力指标用于观察公司把资本转化为利润的效率。"""

    model_config = ConfigDict(frozen=True)

    roe_ttm: float | None = Field(default=None, description="ROE 净资产收益率")
    roic_ttm: float | None = Field(default=None, description="ROIC 投入资本回报率")
    gross_margin_ttm: float | None = Field(default=None, description="毛利率")
    operating_margin_ttm: float | None = Field(default=None, description="营业利润率")


class CashFlowMetrics(BaseModel):
    """现金流指标用于补充利润表，判断企业真实现金创造能力。"""

    model_config = ConfigDict(frozen=True)

    fcf_ttm: float | None = Field(default=None, description="FCF 自由现金流")
    operating_cash_flow_ttm: float | None = Field(default=None, description="经营活动现金流")
    capex_ttm: float | None = Field(default=None, description="资本开支")


class FundamentalDataStatus(BaseModel):
    """基本面数据状态，说明估值、盈利能力和现金流来自数据库还是 Mock 回退。"""

    model_config = ConfigDict(frozen=True)

    source: str = Field(description="基本面数据来源：database 或 mock_provider")
    completeness: str = Field(description="基本面数据完整性：complete、partial 或 mock")
    available_sections: list[str] = Field(default_factory=list, description="数据库已覆盖的页面指标区域")
    missing_sections: list[str] = Field(default_factory=list, description="数据库缺失并需要回退的页面指标区域")


class FactorDataStatus(BaseModel):
    """因子数据状态，说明因子快照来自数据库还是即时 Quant Pipeline 计算。"""

    model_config = ConfigDict(frozen=True)

    source: str = Field(description="因子数据来源：database 或 quant_pipeline")
    completeness: str = Field(description="因子数据完整性：complete、partial 或 computed")
    available_factors: list[str] = Field(default_factory=list, description="数据库已覆盖的因子名称")
    missing_factors: list[str] = Field(default_factory=list, description="数据库缺失并需要即时计算回退的因子名称")


class SignalDataStatus(BaseModel):
    """量化信号数据状态，说明信号集来自数据库还是即时 Quant Pipeline 计算。"""

    model_config = ConfigDict(frozen=True)

    source: str = Field(description="信号数据来源：database 或 quant_pipeline")
    completeness: str = Field(description="信号数据完整性：complete 或 computed")
    signal_count: int = Field(ge=0, description="当前响应中的信号数量")


class MarketDataSourceStatus(BaseModel):
    """行情类数据来源状态，说明 Quote 或 K 线当前来自哪里。"""

    model_config = ConfigDict(frozen=True)

    source: str = Field(default="mock_provider", description="行情数据来源：database、provider、mock_provider 或 computed")
    detail: str = Field(default="当前使用 Mock Provider 回退数据", description="面向前端展示的数据来源说明")
    fallback_active: bool = Field(default=True, description="当前数据是否处于回退状态")
    data_status: DataStatus = Field(default=DataStatus.UNAVAILABLE, description="当前数据的新鲜度或可用性状态")


class TechnicalIndicators(BaseModel):
    """技术指标来自价格和成交量的确定性计算，不应由 LLM 手算。"""

    model_config = ConfigDict(frozen=True)

    rsi_14: float | None = Field(default=None, ge=0, le=100, description="RSI 14 日相对强弱指标")
    macd: float | None = Field(default=None, description="MACD 指数平滑异同移动平均线")
    macd_signal: float | None = Field(default=None, description="MACD 信号线")
    macd_histogram: float | None = Field(default=None, description="MACD 柱状图")


class StockFactorSnapshot(BaseModel):
    """个股量化因子快照，由 Quant Pipeline 基于价格和基本面输入计算。"""

    model_config = ConfigDict(frozen=True)

    momentum_20d: float | None = Field(default=None, description="20D Momentum 20 日动量")
    trend_strength: float | None = Field(default=None, description="价格相对 EMA 的趋势强度")
    volatility_20d: float | None = Field(default=None, ge=0, description="20 日年化波动率")
    quality_score: float | None = Field(default=None, ge=0, le=1, description="质量因子评分")
    composite_score: float | None = Field(default=None, ge=0, le=1, description="综合因子评分")


class StockQuantSignal(BaseModel):
    """个股量化信号，用结构化字段表达方向、严重程度、评分和证据。"""

    model_config = ConfigDict(frozen=True)

    code: str
    title: str
    direction: Direction
    severity: str
    score: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class KLineBar(BaseModel):
    """单根 K 线，拒绝非有限价格及不符合高低价关系的行情。"""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    timestamp: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_price_range(self) -> Self:
        """开盘价和收盘价必须落在最低价与最高价之间，不擅自修正行情。"""

        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("K-line open and close must be within low and high")
        return self


class KLineSeries(BaseModel):
    """按时间严格递增的 K 线序列，保留周期及数据状态。"""

    model_config = ConfigDict(frozen=True)

    interval: KLineInterval
    data_status: DataStatus
    bars: list[KLineBar]

    @model_validator(mode="after")
    def validate_timestamp_order(self) -> Self:
        """拒绝重复、倒序及不可比较的时间，不替调用方排序或补造日期。"""

        for previous, current in zip(self.bars, self.bars[1:]):
            try:
                increasing = current.timestamp > previous.timestamp
            except TypeError as error:
                raise ValueError("K-line timestamps must use comparable timezone information") from error
            if not increasing:
                raise ValueError("K-line timestamps must be strictly increasing")
        return self


class StockResearchResponse(BaseModel):
    """GET /api/v1/stock/research 的响应合同。"""

    model_config = ConfigDict(frozen=True)

    profile: StockProfile
    quote: StockQuote
    valuation: ValuationMetrics
    profitability: ProfitabilityMetrics
    cash_flow: CashFlowMetrics
    fundamental_data_status: FundamentalDataStatus
    technical: TechnicalIndicators
    technical_data_source: MarketDataSourceStatus = Field(
        description="技术指标的计算来源及其输入行情状态",
    )
    factor_snapshot: StockFactorSnapshot
    factor_data_status: FactorDataStatus
    quant_signals: list[StockQuantSignal]
    signal_data_status: SignalDataStatus
    quote_data_source: MarketDataSourceStatus = Field(default_factory=MarketDataSourceStatus)
    kline: KLineSeries
    kline_data_source: MarketDataSourceStatus = Field(default_factory=MarketDataSourceStatus)
    risk_flags: list[str]
    summary_points: list[str]
    summary_data_source: MarketDataSourceStatus = Field(
        description="研究摘要的生成来源及其输入数据状态",
    )
    direction: Direction

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.market import MarketCode
from app.schemas.market import DataStatus
from app.schemas.strategy import StrategyStatus


class BacktestStatus(StrEnum):
    """回测任务状态，当前阶段只定义合同，不运行真实任务队列。"""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class BacktestDataMode(StrEnum):
    """回测数据模式，用于明确当前结果来自 Mock、历史数据还是真实 Provider。"""

    MOCK = "mock"
    HISTORICAL = "historical"


class BacktestRequest(BaseModel):
    """POST /api/v1/backtests 的请求合同，后续由回测引擎消费。"""

    model_config = ConfigDict(frozen=True)

    market: MarketCode
    strategy_id: str
    strategy_status: StrategyStatus
    data_mode: BacktestDataMode = BacktestDataMode.MOCK
    start_date: date
    end_date: date
    sample_split_at: date | None = None
    initial_capital: float = Field(gt=0)
    benchmark: str
    transaction_fee_rate: float = Field(default=0.0005, ge=0, le=0.1)
    slippage_rate: float = Field(default=0.0005, ge=0, le=0.1)

    @model_validator(mode="after")
    def validate_request_boundaries(self) -> "BacktestRequest":
        """回测只能基于已确认策略，且样本切分必须落在回测区间内部。"""

        if self.strategy_status != StrategyStatus.CONFIRMED:
            raise ValueError("strategy_status must be confirmed before backtest")
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be later than start_date")
        if self.sample_split_at is not None and not self.start_date < self.sample_split_at < self.end_date:
            raise ValueError("sample_split_at must be between start_date and end_date")
        return self


class BacktestTaskCreateResponse(BaseModel):
    """回测任务创建后的 202 回执，当前只预留异步轮询入口。"""

    model_config = ConfigDict(frozen=True)

    backtest_id: str
    strategy_id: str
    market: MarketCode
    status: BacktestStatus
    accepted_at: datetime
    data_mode: BacktestDataMode
    timezone: str
    currency: str
    poll_url: str
    data_status: DataStatus = DataStatus.REALTIME
    fallback_active: bool = False
    fallback_reason: str | None = None
    storage_source: str = "mock"
    result_data_mode: BacktestDataMode | None = None

    @field_validator("poll_url")
    @classmethod
    def validate_poll_url(cls, poll_url: str) -> str:
        """限制轮询地址为后端相对路径，避免响应中混入外部 URL。"""

        if poll_url.startswith("//") or "://" in poll_url:
            raise ValueError("poll_url must not be an external URL")
        if not poll_url.startswith("/"):
            raise ValueError("poll_url must be a relative path")
        return poll_url


class BacktestPerformance(BaseModel):
    """回测绩效指标，百分比类字段统一使用小数表达。"""

    model_config = ConfigDict(frozen=True)

    initial_capital: float = Field(gt=0)
    final_value: float = Field(ge=0)
    total_return: float
    annualized_return: float
    benchmark_return: float
    maximum_drawdown: float = Field(ge=0, le=1)
    sharpe_ratio: float | None = None
    win_rate: float = Field(ge=0, le=1)
    trade_count: int = Field(ge=0)


class EquityCurvePoint(BaseModel):
    """权益曲线上的一个时间点，用于前端绘制策略净值变化。"""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    equity: float = Field(ge=0)
    benchmark_equity: float = Field(ge=0)
    drawdown: float = Field(ge=0, le=1)


class BacktestTrade(BaseModel):
    """回测中的模拟成交记录，不代表真实交易。"""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    market: MarketCode
    symbol: str
    side: str
    quantity: int = Field(gt=0)
    price: float = Field(gt=0)
    fee: float = Field(ge=0)
    slippage: float = Field(ge=0)


class BacktestResponse(BaseModel):
    """GET /api/v1/backtests/{backtest_id} 的响应合同。"""

    model_config = ConfigDict(frozen=True)

    backtest_id: str
    strategy_id: str
    market: MarketCode
    status: BacktestStatus
    data_mode: BacktestDataMode
    timestamp: datetime
    timezone: str
    currency: str
    benchmark: str
    start_date: date
    end_date: date
    performance: BacktestPerformance
    equity_curve: list[EquityCurvePoint]
    trades: list[BacktestTrade]
    assumptions: list[str]

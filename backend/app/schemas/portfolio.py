from datetime import datetime
from enum import StrEnum
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.market import MarketCode
from app.schemas.market import DataStatus

SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.-]+$")


class PortfolioDataMode(StrEnum):
    """组合数据模式，当前只返回 Mock，后续可扩展到持久化模拟账户。"""

    MOCK = "mock"
    PAPER = "paper"


class PaperOrderStatus(StrEnum):
    """模拟订单状态，不对应任何真实券商订单。"""

    SUBMITTED = "submitted"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PaperOrderSide(StrEnum):
    """模拟订单方向，用枚举避免前后端使用任意字符串。"""

    BUY = "buy"
    SELL = "sell"


class PaperOrderRiskDecision(StrEnum):
    """模拟订单回执中的风控结论快照。"""

    APPROVED = "approved"
    WARNING = "warning"
    REJECTED = "rejected"


class PaperOrderRequest(BaseModel):
    """POST /api/v1/paper/orders 的请求合同，只允许提交模拟订单。"""

    model_config = ConfigDict(frozen=True)

    account_id: str = Field(min_length=1, max_length=80)
    market: MarketCode
    symbol: str
    side: PaperOrderSide
    quantity: int = Field(gt=0)
    limit_price: float | None = Field(default=None, gt=0)
    paper_trading: bool = True

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, symbol: str) -> str:
        """规范化订单标的代码，但不根据代码推断市场。"""

        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be empty")
        if not SYMBOL_PATTERN.fullmatch(normalized_symbol):
            raise ValueError("symbol contains unsupported characters")
        return normalized_symbol

    @field_validator("paper_trading")
    @classmethod
    def validate_paper_trading(cls, paper_trading: bool) -> bool:
        """V1 只允许模拟交易请求，禁止把真实交易意图传入当前接口。"""

        if paper_trading is not True:
            raise ValueError("paper_trading must be true")
        return paper_trading


class PaperOrderCreateResponse(BaseModel):
    """模拟订单创建后的接收回执，不代表真实券商订单。"""

    model_config = ConfigDict(frozen=True)

    order_id: str
    account_id: str
    market: MarketCode
    symbol: str
    side: PaperOrderSide
    quantity: int = Field(gt=0)
    limit_price: float | None = Field(default=None, gt=0)
    status: PaperOrderStatus
    submitted_at: datetime
    currency: str
    risk_checked: bool
    risk_decision: PaperOrderRiskDecision
    risk_reason_codes: list[str] = Field(default_factory=list)
    risk_reasons: list[str] = Field(default_factory=list)
    data_status: DataStatus = DataStatus.REALTIME
    fallback_active: bool = False
    fallback_reason: str | None = None
    storage_source: str = "mock"


class PortfolioAccount(BaseModel):
    """模拟组合账户摘要，描述现金、权益和收益状态。"""

    model_config = ConfigDict(frozen=True)

    account_id: str
    market: MarketCode
    currency: str
    nav: float = Field(ge=0)
    cash: float = Field(ge=0)
    market_value: float = Field(ge=0)
    daily_pnl: float
    total_pnl: float
    total_return: float
    updated_at: datetime


class PortfolioPosition(BaseModel):
    """单个模拟持仓，所有金额字段使用响应中的 currency。"""

    model_config = ConfigDict(frozen=True)

    market: MarketCode
    symbol: str
    name: str
    quantity: int = Field(gt=0)
    average_cost: float = Field(gt=0)
    last_price: float = Field(gt=0)
    market_value: float = Field(ge=0)
    weight: float = Field(ge=0, le=1)
    unrealized_pnl: float
    unrealized_pnl_percent: float


class PaperOrder(BaseModel):
    """模拟订单记录，只用于学习和风控流程展示，不会提交真实交易。"""

    model_config = ConfigDict(frozen=True)

    order_id: str
    market: MarketCode
    symbol: str
    side: PaperOrderSide
    quantity: int = Field(gt=0)
    limit_price: float | None = Field(default=None, gt=0)
    status: PaperOrderStatus
    submitted_at: datetime
    filled_at: datetime | None = None
    source: str = Field(default="mock_summary", description="订单来源：mock_summary 或 paper_order")


class PortfolioRiskSummary(BaseModel):
    """组合级风险摘要，后续由 Risk Engine 计算并执行约束。"""

    model_config = ConfigDict(frozen=True)

    gross_exposure: float = Field(ge=0)
    net_exposure: float
    largest_position_weight: float = Field(ge=0, le=1)
    cash_weight: float = Field(ge=0, le=1)
    risk_flags: list[str] = Field(default_factory=list)


class PortfolioResponse(BaseModel):
    """GET /api/v1/portfolio/summary 的响应合同。"""

    model_config = ConfigDict(frozen=True)

    market: MarketCode
    timestamp: datetime
    timezone: str
    currency: str
    data_mode: PortfolioDataMode
    account: PortfolioAccount
    positions: list[PortfolioPosition]
    orders: list[PaperOrder]
    risk: PortfolioRiskSummary

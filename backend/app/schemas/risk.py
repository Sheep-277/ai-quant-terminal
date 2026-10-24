from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.market import MarketCode
from app.schemas.portfolio import PaperOrderSide, SYMBOL_PATTERN


class RiskPositionSide(StrEnum):
    """风险计算使用的持仓方向，V1 下单仍只允许模拟交易。"""

    LONG = "long"
    SHORT = "short"


class RiskCheckDecision(StrEnum):
    """下单前风险检查结论，用枚举避免调用方自行解释字符串。"""

    APPROVED = "approved"
    WARNING = "warning"
    REJECTED = "rejected"


class RiskCheckSeverity(StrEnum):
    """风险原因严重程度，用于前端决定提示层级。"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class RiskPositionInput(BaseModel):
    """下单前风险检查所需的当前持仓输入。"""

    model_config = ConfigDict(frozen=True)

    market: MarketCode
    symbol: str
    market_value: float = Field(ge=0)
    side: RiskPositionSide = RiskPositionSide.LONG

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, symbol: str) -> str:
        """规范化持仓标的代码，但不根据代码推断市场。"""

        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be empty")
        if not SYMBOL_PATTERN.fullmatch(normalized_symbol):
            raise ValueError("symbol contains unsupported characters")
        return normalized_symbol


class PreTradeRiskCheckRequest(BaseModel):
    """下单前风险检查请求合同，只评估模拟订单，不提交订单。"""

    model_config = ConfigDict(frozen=True)

    account_id: str = Field(min_length=1, max_length=80)
    market: MarketCode
    symbol: str
    side: PaperOrderSide
    quantity: int = Field(gt=0)
    limit_price: float | None = Field(default=None, gt=0)
    nav: float = Field(gt=0)
    cash: float = Field(ge=0)
    current_positions: list[RiskPositionInput] = Field(default_factory=list)
    max_position_weight: float = Field(default=0.3, gt=0, le=1)
    min_cash_weight: float = Field(default=0.05, ge=0, le=1)
    paper_trading: bool = True

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, symbol: str) -> str:
        """规范化订单标的代码，市场仍必须由 market 字段显式提供。"""

        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be empty")
        if not SYMBOL_PATTERN.fullmatch(normalized_symbol):
            raise ValueError("symbol contains unsupported characters")
        return normalized_symbol

    @field_validator("paper_trading")
    @classmethod
    def validate_paper_trading(cls, paper_trading: bool) -> bool:
        """V1 风险检查只服务模拟订单，禁止真实交易意图进入。"""

        if paper_trading is not True:
            raise ValueError("paper_trading must be true")
        return paper_trading

    @model_validator(mode="after")
    def validate_position_markets(self) -> "PreTradeRiskCheckRequest":
        """同一次风险检查中的持仓必须与请求市场一致。"""

        for position in self.current_positions:
            if position.market != self.market:
                raise ValueError("current_positions market must match request market")
        return self


class RiskCheckReason(BaseModel):
    """风险检查命中的单条原因，供前端和审计日志展示。"""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    severity: RiskCheckSeverity


class PreTradeRiskCheckResponse(BaseModel):
    """下单前风险检查响应合同，不代表订单已创建或已成交。"""

    model_config = ConfigDict(frozen=True)

    account_id: str
    market: MarketCode
    symbol: str
    side: PaperOrderSide
    decision: RiskCheckDecision
    risk_checked: bool
    checked_at: datetime
    projected_order_value: float = Field(ge=0)
    projected_cash: float
    projected_cash_weight: float
    projected_position_weight: float = Field(ge=0)
    reasons: list[RiskCheckReason] = Field(default_factory=list)

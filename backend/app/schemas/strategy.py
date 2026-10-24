from datetime import datetime, timezone
from enum import StrEnum
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.market import MarketCode

SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.-]+$")


class StrategyCreatedBy(StrEnum):
    """策略来源，区分用户手动创建和 AI 生成草案。"""

    USER = "user"
    AGENT = "agent"


class StrategyStatus(StrEnum):
    """策略当前状态，草案必须由用户确认后才进入后续回测。"""

    DRAFT = "draft"
    CONFIRMED = "confirmed"
    ARCHIVED = "archived"


class UniverseType(StrEnum):
    """股票池类型，用于表达策略在哪一组标的中选股。"""

    INDEX = "index"
    WATCHLIST = "watchlist"
    CUSTOM = "custom"


class StrategyConditionField(StrEnum):
    """当前 Strategy Lab 支持的条件字段，后续由 Quant Engine 负责真实计算。"""

    MOMENTUM_20D = "momentum_20d"
    ROE = "roe"
    VOLUME_RATIO = "volume_ratio"
    RSI_14 = "rsi_14"
    PE_TTM = "pe_ttm"


class StrategyConditionOperator(StrEnum):
    """条件比较符，避免前端和后端使用任意字符串表达规则。"""

    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    BETWEEN = "between"


class RebalanceFrequency(StrEnum):
    """调仓频率决定策略多久重新筛选标的和调整持仓。"""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class StrategyParseSource(StrEnum):
    """自然语言策略条件的解析来源，用于向前端说明结果由哪条路径生成。"""

    RULE_BASED = "rule_based"
    LLM = "llm"
    HYBRID = "hybrid"


class StrategyUniverse(BaseModel):
    """策略股票池，所有策略必须明确市场和可选标的范围。"""

    model_config = ConfigDict(frozen=True)

    market: MarketCode
    universe_type: UniverseType
    name: str
    symbols: list[str] = Field(default_factory=list, max_length=200)

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, symbols: list[str]) -> list[str]:
        """统一证券代码大小写，避免策略草案里混入无法识别的标的格式。"""

        normalized_symbols: list[str] = []
        for symbol in symbols:
            normalized_symbol = symbol.strip().upper()
            if not normalized_symbol:
                raise ValueError("symbols cannot contain empty values")
            if not SYMBOL_PATTERN.fullmatch(normalized_symbol):
                raise ValueError("symbols must contain only uppercase letters, digits, dots, and hyphens")
            normalized_symbols.append(normalized_symbol)
        return normalized_symbols


class StrategyCondition(BaseModel):
    """单条入场或出场条件，例如 momentum_20d > 10%。"""

    model_config = ConfigDict(frozen=True)

    field: StrategyConditionField
    operator: StrategyConditionOperator
    value: float
    upper_value: float | None = None
    description: str

    @model_validator(mode="after")
    def validate_range_condition(self) -> "StrategyCondition":
        """between 条件必须提供上界，且上界必须大于下界。"""

        if self.operator == StrategyConditionOperator.BETWEEN:
            if self.upper_value is None:
                raise ValueError("upper_value is required when operator is between")
            if self.upper_value <= self.value:
                raise ValueError("upper_value must be greater than value when operator is between")
        elif self.upper_value is not None:
            raise ValueError("upper_value is only allowed when operator is between")
        return self


class PositionRule(BaseModel):
    """仓位规则，控制单个标的权重和最多持仓数量。"""

    model_config = ConfigDict(frozen=True)

    max_holdings: int = Field(gt=0)
    max_position_weight: float = Field(gt=0, le=1)
    equal_weight: bool = True


class RiskConstraint(BaseModel):
    """策略级风险约束，先作为合同字段，后续由 Risk Engine 执行。"""

    model_config = ConfigDict(frozen=True)

    max_drawdown: float | None = Field(default=None, gt=0, le=1)
    stop_loss: float | None = Field(default=None, gt=0, le=1)
    min_liquidity: float | None = Field(default=None, ge=0)


class StrategyDraftCreateRequest(BaseModel):
    """POST /api/v1/strategies 的请求合同，只创建草案，不触发真实交易。"""

    model_config = ConfigDict(frozen=True)

    market: MarketCode
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    universe: StrategyUniverse
    entry_conditions: list[StrategyCondition] = Field(min_length=1, max_length=20)
    exit_conditions: list[StrategyCondition] = Field(min_length=1, max_length=20)
    position_rule: PositionRule
    rebalance_frequency: RebalanceFrequency
    risk_constraints: list[RiskConstraint] = Field(default_factory=list, max_length=5)
    created_by: StrategyCreatedBy = StrategyCreatedBy.USER

    @model_validator(mode="after")
    def validate_market_consistency(self) -> "StrategyDraftCreateRequest":
        """请求市场必须和股票池市场一致，禁止把一个市场的规则套到另一个市场。"""

        if self.universe.market != self.market:
            raise ValueError("universe.market must match request market")
        return self


class StrategyNaturalLanguageParseRequest(BaseModel):
    """自然语言转策略条件的请求合同，解析结果必须由用户确认后才能保存为草案。"""

    model_config = ConfigDict(frozen=True)

    market: MarketCode
    text: str = Field(min_length=1, max_length=2000)
    universe: StrategyUniverse | None = None
    preferred_source: StrategyParseSource | None = None
    require_user_confirmation: bool = True

    @field_validator("text")
    @classmethod
    def normalize_text(cls, text: str) -> str:
        """去掉首尾空白，避免空字符串通过最小长度校验。"""

        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("text cannot be empty")
        return normalized_text

    @model_validator(mode="after")
    def validate_market_consistency(self) -> "StrategyNaturalLanguageParseRequest":
        """如果请求携带股票池，股票池市场必须和解析市场一致。"""

        if self.universe is not None and self.universe.market != self.market:
            raise ValueError("universe.market must match request market")
        return self


class StrategyNaturalLanguageParseResult(BaseModel):
    """自然语言解析后的结构化策略片段，不直接触发回测或交易。"""

    model_config = ConfigDict(frozen=True)

    entry_conditions: list[StrategyCondition] = Field(default_factory=list, max_length=20)
    exit_conditions: list[StrategyCondition] = Field(default_factory=list, max_length=20)
    risk_constraints: list[RiskConstraint] = Field(default_factory=list, max_length=5)
    warnings: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_non_empty_result(self) -> "StrategyNaturalLanguageParseResult":
        """解析结果至少要包含一类可编辑规则，否则前端无法给用户确认。"""

        if not self.entry_conditions and not self.exit_conditions and not self.risk_constraints:
            raise ValueError("parse result must contain at least one structured rule")
        return self


class StrategyNaturalLanguageParseResponse(BaseModel):
    """自然语言解析响应，前端展示候选条件并等待用户确认。"""

    model_config = ConfigDict(frozen=True)

    market: MarketCode
    source: StrategyParseSource
    confidence: float = Field(ge=0, le=1)
    requires_user_confirmation: bool = True
    parsed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_text: str = Field(min_length=1, max_length=2000)
    result: StrategyNaturalLanguageParseResult


class StrategyDraft(BaseModel):
    """Strategy Lab 中可编辑、可确认的策略草案。"""

    model_config = ConfigDict(frozen=True)

    strategy_id: str
    name: str
    version: int = Field(gt=0)
    description: str
    status: StrategyStatus
    created_by: StrategyCreatedBy
    created_at: datetime
    updated_at: datetime
    universe: StrategyUniverse
    entry_conditions: list[StrategyCondition]
    exit_conditions: list[StrategyCondition]
    position_rule: PositionRule
    rebalance_frequency: RebalanceFrequency
    risk_constraints: list[RiskConstraint]
    parameters: dict[str, Any] = Field(default_factory=dict)


class StrategyLabResponse(BaseModel):
    """GET /api/v1/strategy/lab 的响应合同。"""

    model_config = ConfigDict(frozen=True)

    market: MarketCode
    timestamp: datetime
    default_universe: StrategyUniverse
    drafts: list[StrategyDraft]

"""策略规则评估。

Strategy Engine 负责把可计算因子和用户/Agent 定义的规则进行匹配。
本模块只输出条件是否命中，不生成投资建议，也不直接触发回测或模拟交易。
"""

from dataclasses import dataclass
from enum import StrEnum

from app.quant.factors import FactorSnapshot


class StrategyConditionField(StrEnum):
    """当前策略规则可引用的因子字段。"""

    MOMENTUM_20D = "momentum_20d"
    TREND_STRENGTH = "trend_strength"
    VOLATILITY_20D = "volatility_20d"
    QUALITY_SCORE = "quality_score"
    COMPOSITE_SCORE = "composite_score"


class StrategyConditionOperator(StrEnum):
    """策略条件比较符。"""

    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    BETWEEN = "between"


@dataclass(frozen=True)
class StrategyCondition:
    """一条可执行策略条件。"""

    field: StrategyConditionField
    operator: StrategyConditionOperator
    value: float
    upper_value: float | None = None


@dataclass(frozen=True)
class ConditionEvaluation:
    """单条策略条件的评估结果。"""

    condition: StrategyCondition
    actual_value: float | None
    matched: bool
    reason: str


@dataclass(frozen=True)
class StrategyEvaluation:
    """一组入场/出场条件的评估结果。"""

    entry_matched: bool
    exit_matched: bool
    entry_evaluations: list[ConditionEvaluation]
    exit_evaluations: list[ConditionEvaluation]


def evaluate_condition(
    snapshot: FactorSnapshot,
    condition: StrategyCondition,
) -> ConditionEvaluation:
    """评估单条策略条件。"""

    actual_value = _get_factor_value(snapshot, condition.field)
    if actual_value is None:
        return ConditionEvaluation(
            condition=condition,
            actual_value=None,
            matched=False,
            reason="factor_value_missing",
        )

    if condition.operator == StrategyConditionOperator.GREATER_THAN:
        matched = actual_value > condition.value
    elif condition.operator == StrategyConditionOperator.GREATER_THAN_OR_EQUAL:
        matched = actual_value >= condition.value
    elif condition.operator == StrategyConditionOperator.LESS_THAN:
        matched = actual_value < condition.value
    elif condition.operator == StrategyConditionOperator.LESS_THAN_OR_EQUAL:
        matched = actual_value <= condition.value
    elif condition.operator == StrategyConditionOperator.BETWEEN:
        if condition.upper_value is None:
            raise ValueError("upper_value is required for between operator")
        if condition.value > condition.upper_value:
            raise ValueError("value must be less than or equal to upper_value")
        matched = condition.value <= actual_value <= condition.upper_value
    else:
        raise ValueError(f"unsupported condition operator: {condition.operator}")

    return ConditionEvaluation(
        condition=condition,
        actual_value=actual_value,
        matched=matched,
        reason="matched" if matched else "not_matched",
    )


def evaluate_conditions(
    snapshot: FactorSnapshot,
    conditions: list[StrategyCondition],
) -> list[ConditionEvaluation]:
    """批量评估策略条件。"""

    return [evaluate_condition(snapshot, condition) for condition in conditions]


def evaluate_strategy(
    snapshot: FactorSnapshot,
    *,
    entry_conditions: list[StrategyCondition],
    exit_conditions: list[StrategyCondition],
) -> StrategyEvaluation:
    """评估一组入场和出场条件。

    当前采用最保守的 AND 逻辑：所有入场条件都满足才认为可入场；
    任意出场条件满足即认为触发出场。
    """

    entry_evaluations = evaluate_conditions(snapshot, entry_conditions)
    exit_evaluations = evaluate_conditions(snapshot, exit_conditions)

    return StrategyEvaluation(
        entry_matched=bool(entry_evaluations) and all(
            item.matched for item in entry_evaluations
        ),
        exit_matched=any(item.matched for item in exit_evaluations),
        entry_evaluations=entry_evaluations,
        exit_evaluations=exit_evaluations,
    )


def _get_factor_value(
    snapshot: FactorSnapshot,
    field: StrategyConditionField,
) -> float | None:
    """读取策略条件对应的因子值。"""

    if field == StrategyConditionField.MOMENTUM_20D:
        return snapshot.momentum_20d
    if field == StrategyConditionField.TREND_STRENGTH:
        return snapshot.trend_strength
    if field == StrategyConditionField.VOLATILITY_20D:
        return snapshot.volatility_20d
    if field == StrategyConditionField.QUALITY_SCORE:
        return snapshot.quality_score
    if field == StrategyConditionField.COMPOSITE_SCORE:
        return snapshot.composite_score

    raise ValueError(f"unsupported condition field: {field}")

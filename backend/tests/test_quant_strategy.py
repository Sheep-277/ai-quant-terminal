import pytest

from app.quant.factors import FactorSnapshot
from app.quant.strategy import (
    StrategyCondition,
    StrategyConditionField,
    StrategyConditionOperator,
    evaluate_condition,
    evaluate_strategy,
)


def _snapshot() -> FactorSnapshot:
    return FactorSnapshot(
        momentum_20d=0.12,
        trend_strength=0.05,
        volatility_20d=0.22,
        quality_score=0.72,
        composite_score=0.81,
    )


def test_evaluate_condition_supports_greater_than() -> None:
    condition = StrategyCondition(
        field=StrategyConditionField.MOMENTUM_20D,
        operator=StrategyConditionOperator.GREATER_THAN,
        value=0.08,
    )

    evaluation = evaluate_condition(_snapshot(), condition)

    assert evaluation.matched is True
    assert evaluation.actual_value == pytest.approx(0.12)
    assert evaluation.reason == "matched"


def test_evaluate_condition_supports_between() -> None:
    condition = StrategyCondition(
        field=StrategyConditionField.VOLATILITY_20D,
        operator=StrategyConditionOperator.BETWEEN,
        value=0.1,
        upper_value=0.3,
    )

    evaluation = evaluate_condition(_snapshot(), condition)

    assert evaluation.matched is True
    assert evaluation.reason == "matched"


def test_evaluate_condition_marks_missing_factor_as_not_matched() -> None:
    condition = StrategyCondition(
        field=StrategyConditionField.QUALITY_SCORE,
        operator=StrategyConditionOperator.GREATER_THAN_OR_EQUAL,
        value=0.6,
    )
    snapshot = FactorSnapshot(
        momentum_20d=0.12,
        trend_strength=0.05,
        volatility_20d=0.22,
        quality_score=None,
        composite_score=0.81,
    )

    evaluation = evaluate_condition(snapshot, condition)

    assert evaluation.matched is False
    assert evaluation.actual_value is None
    assert evaluation.reason == "factor_value_missing"


def test_evaluate_condition_requires_upper_value_for_between() -> None:
    condition = StrategyCondition(
        field=StrategyConditionField.VOLATILITY_20D,
        operator=StrategyConditionOperator.BETWEEN,
        value=0.1,
    )

    with pytest.raises(ValueError, match="upper_value is required"):
        evaluate_condition(_snapshot(), condition)


def test_evaluate_strategy_uses_all_entry_conditions_and_any_exit_condition() -> None:
    entry_conditions = [
        StrategyCondition(
            field=StrategyConditionField.MOMENTUM_20D,
            operator=StrategyConditionOperator.GREATER_THAN,
            value=0.08,
        ),
        StrategyCondition(
            field=StrategyConditionField.COMPOSITE_SCORE,
            operator=StrategyConditionOperator.GREATER_THAN_OR_EQUAL,
            value=0.75,
        ),
    ]
    exit_conditions = [
        StrategyCondition(
            field=StrategyConditionField.VOLATILITY_20D,
            operator=StrategyConditionOperator.GREATER_THAN,
            value=0.5,
        ),
        StrategyCondition(
            field=StrategyConditionField.TREND_STRENGTH,
            operator=StrategyConditionOperator.LESS_THAN,
            value=0,
        ),
    ]

    evaluation = evaluate_strategy(
        _snapshot(),
        entry_conditions=entry_conditions,
        exit_conditions=exit_conditions,
    )

    assert evaluation.entry_matched is True
    assert evaluation.exit_matched is False
    assert len(evaluation.entry_evaluations) == 2
    assert len(evaluation.exit_evaluations) == 2


def test_evaluate_strategy_triggers_exit_when_any_exit_condition_matches() -> None:
    exit_conditions = [
        StrategyCondition(
            field=StrategyConditionField.VOLATILITY_20D,
            operator=StrategyConditionOperator.GREATER_THAN,
            value=0.2,
        ),
    ]

    evaluation = evaluate_strategy(
        _snapshot(),
        entry_conditions=[],
        exit_conditions=exit_conditions,
    )

    assert evaluation.entry_matched is False
    assert evaluation.exit_matched is True

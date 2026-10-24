import pytest

from app.quant.pipeline import QuantPipelineInput, run_quant_pipeline
from app.quant.strategy import (
    StrategyCondition,
    StrategyConditionField,
    StrategyConditionOperator,
)


def test_run_quant_pipeline_returns_factors_signals_and_strategy_evaluation() -> None:
    payload = QuantPipelineInput(
        symbol="NVDA",
        closes=[float(value) for value in range(100, 131)],
        roe=0.18,
        roic=0.12,
        gross_margin=0.42,
        entry_conditions=[
            StrategyCondition(
                field=StrategyConditionField.MOMENTUM_20D,
                operator=StrategyConditionOperator.GREATER_THAN,
                value=0.08,
            ),
            StrategyCondition(
                field=StrategyConditionField.COMPOSITE_SCORE,
                operator=StrategyConditionOperator.GREATER_THAN_OR_EQUAL,
                value=0.7,
            ),
        ],
        exit_conditions=[
            StrategyCondition(
                field=StrategyConditionField.VOLATILITY_20D,
                operator=StrategyConditionOperator.GREATER_THAN,
                value=0.6,
            ),
        ],
    )

    result = run_quant_pipeline(payload)

    assert result.symbol == "NVDA"
    assert result.factors.momentum_20d is not None
    assert result.factors.composite_score is not None
    assert result.signals
    assert result.strategy.entry_matched is True
    assert result.strategy.exit_matched is False


def test_run_quant_pipeline_keeps_strategy_false_when_no_entry_conditions() -> None:
    payload = QuantPipelineInput(
        symbol="AAPL",
        closes=[float(value) for value in range(100, 131)],
    )

    result = run_quant_pipeline(payload)

    assert result.strategy.entry_matched is False
    assert result.strategy.entry_evaluations == []
    assert result.strategy.exit_evaluations == []


def test_run_quant_pipeline_rejects_empty_symbol() -> None:
    payload = QuantPipelineInput(
        symbol="",
        closes=[float(value) for value in range(100, 131)],
    )

    with pytest.raises(ValueError, match="symbol must not be empty"):
        run_quant_pipeline(payload)

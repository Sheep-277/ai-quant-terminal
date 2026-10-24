"""量化工具封装。

Tools 层把确定性 Quant 能力包装成 Agent 可调用的函数。
Agent 只能读取这里返回的结构化结果，不应自己手算指标、因子或策略规则。
"""

from typing import Any

from app.quant.pipeline import QuantPipelineInput, QuantPipelineResult, run_quant_pipeline
from app.quant.strategy import (
    ConditionEvaluation,
    StrategyCondition,
    StrategyConditionField,
    StrategyConditionOperator,
    StrategyEvaluation,
)


def run_quant_pipeline_tool(
    *,
    symbol: str,
    closes: list[float],
    fundamentals: dict[str, float | None] | None = None,
    entry_conditions: list[dict[str, Any]] | None = None,
    exit_conditions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """运行单标的量化流水线工具。

    输入使用普通 Python dict/list，方便后续 Tool Registry 或 Agent 框架接入。
    输出保持 JSON 友好结构，不泄露内部 dataclass 对象。
    """

    fundamentals = fundamentals or {}
    result = run_quant_pipeline(
        QuantPipelineInput(
            symbol=symbol,
            closes=closes,
            roe=fundamentals.get("roe"),
            roic=fundamentals.get("roic"),
            gross_margin=fundamentals.get("gross_margin"),
            entry_conditions=_parse_conditions(entry_conditions or []),
            exit_conditions=_parse_conditions(exit_conditions or []),
        )
    )

    return _serialize_pipeline_result(result)


def _parse_conditions(rows: list[dict[str, Any]]) -> list[StrategyCondition]:
    """把工具输入中的 dict 条件转换为 Strategy Engine 类型。"""

    return [
        StrategyCondition(
            field=StrategyConditionField(row["field"]),
            operator=StrategyConditionOperator(row["operator"]),
            value=float(row["value"]),
            upper_value=(
                None if row.get("upper_value") is None else float(row["upper_value"])
            ),
        )
        for row in rows
    ]


def _serialize_pipeline_result(result: QuantPipelineResult) -> dict[str, Any]:
    """序列化 Quant Pipeline 输出。"""

    return {
        "symbol": result.symbol,
        "factors": {
            "momentum_20d": result.factors.momentum_20d,
            "trend_strength": result.factors.trend_strength,
            "volatility_20d": result.factors.volatility_20d,
            "quality_score": result.factors.quality_score,
            "composite_score": result.factors.composite_score,
        },
        "signals": [
            {
                "code": signal.code,
                "title": signal.title,
                "direction": signal.direction.value,
                "severity": signal.severity.value,
                "score": signal.score,
                "evidence": signal.evidence,
            }
            for signal in result.signals
        ],
        "strategy": _serialize_strategy_evaluation(result.strategy),
    }


def _serialize_strategy_evaluation(evaluation: StrategyEvaluation) -> dict[str, Any]:
    """序列化策略评估结果。"""

    return {
        "entry_matched": evaluation.entry_matched,
        "exit_matched": evaluation.exit_matched,
        "entry_evaluations": [
            _serialize_condition_evaluation(item)
            for item in evaluation.entry_evaluations
        ],
        "exit_evaluations": [
            _serialize_condition_evaluation(item)
            for item in evaluation.exit_evaluations
        ],
    }


def _serialize_condition_evaluation(
    evaluation: ConditionEvaluation,
) -> dict[str, Any]:
    """序列化单条条件评估结果。"""

    return {
        "field": evaluation.condition.field.value,
        "operator": evaluation.condition.operator.value,
        "value": evaluation.condition.value,
        "upper_value": evaluation.condition.upper_value,
        "actual_value": evaluation.actual_value,
        "matched": evaluation.matched,
        "reason": evaluation.reason,
    }

"""确定性量化流水线。

Quant Pipeline 把价格和基本面输入转换为因子、信号和策略评估结果。
它是 FAST PATH 和 Agent Tool 后续复用的统一入口，但本身不访问 Provider 或 LLM。
"""

from dataclasses import dataclass, field

from app.quant.factors import FactorSnapshot, calculate_factor_snapshot
from app.quant.signals import QuantSignal, build_signals_from_factors
from app.quant.strategy import (
    StrategyCondition,
    StrategyEvaluation,
    evaluate_strategy,
)


@dataclass(frozen=True)
class QuantPipelineInput:
    """运行单标的量化流水线所需的最小输入。"""

    symbol: str
    closes: list[float]
    roe: float | None = None
    roic: float | None = None
    gross_margin: float | None = None
    entry_conditions: list[StrategyCondition] = field(default_factory=list)
    exit_conditions: list[StrategyCondition] = field(default_factory=list)


@dataclass(frozen=True)
class QuantPipelineResult:
    """单标的量化流水线输出。"""

    symbol: str
    factors: FactorSnapshot
    signals: list[QuantSignal]
    strategy: StrategyEvaluation


def run_quant_pipeline(payload: QuantPipelineInput) -> QuantPipelineResult:
    """运行单标的确定性量化流水线。"""

    if not payload.symbol:
        raise ValueError("symbol must not be empty")

    factors = calculate_factor_snapshot(
        payload.closes,
        roe=payload.roe,
        roic=payload.roic,
        gross_margin=payload.gross_margin,
    )
    signals = build_signals_from_factors(factors)
    strategy = evaluate_strategy(
        factors,
        entry_conditions=payload.entry_conditions,
        exit_conditions=payload.exit_conditions,
    )

    return QuantPipelineResult(
        symbol=payload.symbol,
        factors=factors,
        signals=signals,
        strategy=strategy,
    )

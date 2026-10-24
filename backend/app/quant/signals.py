"""结构化信号生成。

Signal Engine 把因子快照转换为可展示、可审计的提示。
这里不做买卖建议，也不触发订单，只输出规则命中的方向、严重度、评分和证据。
"""

from dataclasses import dataclass, field
from enum import StrEnum

from app.quant.factors import FactorSnapshot


class SignalDirection(StrEnum):
    """信号方向，用于表达因子含义，不代表交易指令。"""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    WARNING = "warning"


class SignalSeverity(StrEnum):
    """信号严重程度，用于排序和前端提示优先级。"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class QuantSignal:
    """由确定性规则生成的单条量化信号。"""

    code: str
    title: str
    direction: SignalDirection
    severity: SignalSeverity
    score: float
    evidence: list[str] = field(default_factory=list)


def build_signals_from_factors(snapshot: FactorSnapshot) -> list[QuantSignal]:
    """根据因子快照生成结构化信号列表。"""

    signals: list[QuantSignal] = []

    if snapshot.momentum_20d is not None:
        signals.extend(_build_momentum_signals(snapshot.momentum_20d))

    if snapshot.trend_strength is not None:
        signals.extend(_build_trend_signals(snapshot.trend_strength))

    if snapshot.volatility_20d is not None:
        signals.extend(_build_volatility_signals(snapshot.volatility_20d))

    if snapshot.composite_score is not None:
        signals.extend(_build_composite_signals(snapshot.composite_score))

    return sorted(signals, key=lambda signal: signal.score, reverse=True)


def _build_momentum_signals(momentum_20d: float) -> list[QuantSignal]:
    """生成 20 日动量相关信号。"""

    if momentum_20d >= 0.08:
        return [
            QuantSignal(
                code="momentum_strength",
                title="20D momentum strengthened",
                direction=SignalDirection.POSITIVE,
                severity=SignalSeverity.INFO,
                score=_clamp_score(0.55 + momentum_20d),
                evidence=[f"momentum_20d={momentum_20d:.4f}"],
            ),
        ]

    if momentum_20d <= -0.05:
        return [
            QuantSignal(
                code="momentum_weakness",
                title="20D momentum weakened",
                direction=SignalDirection.NEGATIVE,
                severity=SignalSeverity.WARNING,
                score=_clamp_score(0.55 + abs(momentum_20d)),
                evidence=[f"momentum_20d={momentum_20d:.4f}"],
            ),
        ]

    return []


def _build_trend_signals(trend_strength: float) -> list[QuantSignal]:
    """生成趋势强度相关信号。"""

    if trend_strength >= 0.04:
        return [
            QuantSignal(
                code="trend_above_ema",
                title="Price above EMA trend",
                direction=SignalDirection.POSITIVE,
                severity=SignalSeverity.INFO,
                score=_clamp_score(0.5 + trend_strength * 2),
                evidence=[f"trend_strength={trend_strength:.4f}"],
            ),
        ]

    if trend_strength <= -0.04:
        return [
            QuantSignal(
                code="trend_below_ema",
                title="Price below EMA trend",
                direction=SignalDirection.NEGATIVE,
                severity=SignalSeverity.WARNING,
                score=_clamp_score(0.5 + abs(trend_strength) * 2),
                evidence=[f"trend_strength={trend_strength:.4f}"],
            ),
        ]

    return []


def _build_volatility_signals(volatility_20d: float) -> list[QuantSignal]:
    """生成波动率风险信号。"""

    if volatility_20d >= 0.8:
        severity = SignalSeverity.CRITICAL
    elif volatility_20d >= 0.45:
        severity = SignalSeverity.WARNING
    else:
        return []

    return [
        QuantSignal(
            code="volatility_elevated",
            title="20D annualized volatility elevated",
            direction=SignalDirection.WARNING,
            severity=severity,
            score=_clamp_score(volatility_20d),
            evidence=[f"volatility_20d={volatility_20d:.4f}"],
        ),
    ]


def _build_composite_signals(composite_score: float) -> list[QuantSignal]:
    """生成综合评分信号。"""

    if composite_score >= 0.75:
        return [
            QuantSignal(
                code="composite_score_high",
                title="Composite factor score high",
                direction=SignalDirection.POSITIVE,
                severity=SignalSeverity.INFO,
                score=composite_score,
                evidence=[f"composite_score={composite_score:.4f}"],
            ),
        ]

    if composite_score <= 0.25:
        return [
            QuantSignal(
                code="composite_score_low",
                title="Composite factor score low",
                direction=SignalDirection.WARNING,
                severity=SignalSeverity.WARNING,
                score=1 - composite_score,
                evidence=[f"composite_score={composite_score:.4f}"],
            ),
        ]

    return []


def _clamp_score(value: float) -> float:
    """把信号评分限制在 0 到 1。"""

    return min(max(value, 0), 1)

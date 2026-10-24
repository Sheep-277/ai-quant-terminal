from app.quant.factors import FactorSnapshot
from app.quant.signals import (
    SignalDirection,
    SignalSeverity,
    build_signals_from_factors,
)


def test_build_signals_from_factors_returns_empty_list_for_missing_factors() -> None:
    snapshot = FactorSnapshot(
        momentum_20d=None,
        trend_strength=None,
        volatility_20d=None,
        quality_score=None,
        composite_score=None,
    )

    assert build_signals_from_factors(snapshot) == []


def test_build_signals_from_factors_detects_positive_momentum_and_trend() -> None:
    snapshot = FactorSnapshot(
        momentum_20d=0.12,
        trend_strength=0.06,
        volatility_20d=0.2,
        quality_score=0.7,
        composite_score=0.82,
    )

    signals = build_signals_from_factors(snapshot)
    codes = {signal.code for signal in signals}

    assert "momentum_strength" in codes
    assert "trend_above_ema" in codes
    assert "composite_score_high" in codes
    assert all(0 <= signal.score <= 1 for signal in signals)
    assert signals == sorted(signals, key=lambda signal: signal.score, reverse=True)


def test_build_signals_from_factors_detects_negative_momentum() -> None:
    snapshot = FactorSnapshot(
        momentum_20d=-0.08,
        trend_strength=-0.05,
        volatility_20d=0.2,
        quality_score=0.3,
        composite_score=0.2,
    )

    signals = build_signals_from_factors(snapshot)
    momentum_signal = next(signal for signal in signals if signal.code == "momentum_weakness")

    assert momentum_signal.direction == SignalDirection.NEGATIVE
    assert momentum_signal.severity == SignalSeverity.WARNING
    assert momentum_signal.evidence == ["momentum_20d=-0.0800"]


def test_build_signals_from_factors_marks_high_volatility_as_critical() -> None:
    snapshot = FactorSnapshot(
        momentum_20d=0,
        trend_strength=0,
        volatility_20d=0.92,
        quality_score=None,
        composite_score=None,
    )

    signals = build_signals_from_factors(snapshot)
    volatility_signal = next(signal for signal in signals if signal.code == "volatility_elevated")

    assert volatility_signal.direction == SignalDirection.WARNING
    assert volatility_signal.severity == SignalSeverity.CRITICAL
    assert volatility_signal.score == 0.92


def test_build_signals_from_factors_ignores_neutral_factor_values() -> None:
    snapshot = FactorSnapshot(
        momentum_20d=0.01,
        trend_strength=0.01,
        volatility_20d=0.18,
        quality_score=0.5,
        composite_score=0.5,
    )

    assert build_signals_from_factors(snapshot) == []

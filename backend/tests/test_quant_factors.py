import pytest

from app.quant.factors import (
    calculate_factor_snapshot,
    calculate_momentum,
    calculate_quality_score,
    calculate_volatility,
    normalize_factor,
)


def test_calculate_momentum_returns_none_when_sample_is_not_enough() -> None:
    closes = [10, 11, 12]

    assert calculate_momentum(closes, window=20) is None


def test_calculate_momentum_uses_price_before_window_as_base() -> None:
    closes = [100, *[102 for _ in range(19)], 120]

    assert calculate_momentum(closes, window=20) == pytest.approx(0.2)


def test_calculate_volatility_returns_annualized_value() -> None:
    closes = [100, 101, 99, 102, 98, 103, 97, 104, 96, 105, 95]

    volatility = calculate_volatility(closes, window=10)

    assert volatility is not None
    assert volatility > 0


def test_normalize_factor_clamps_and_supports_inverse_score() -> None:
    assert normalize_factor(2, lower=0, upper=1) == pytest.approx(1)
    assert normalize_factor(-1, lower=0, upper=1) == pytest.approx(0)
    assert normalize_factor(0.2, lower=0, upper=1, invert=True) == pytest.approx(0.8)


def test_calculate_quality_score_ignores_missing_inputs() -> None:
    score = calculate_quality_score(roe=0.15, roic=None, gross_margin=0.35)

    assert score == pytest.approx(0.5)


def test_calculate_factor_snapshot_returns_bounded_scores() -> None:
    closes = [float(value) for value in range(100, 131)]

    snapshot = calculate_factor_snapshot(
        closes,
        roe=0.18,
        roic=0.12,
        gross_margin=0.42,
    )

    assert snapshot.momentum_20d is not None
    assert snapshot.trend_strength is not None
    assert snapshot.volatility_20d is not None
    assert snapshot.quality_score is not None
    assert snapshot.composite_score is not None
    assert 0 <= snapshot.quality_score <= 1
    assert 0 <= snapshot.composite_score <= 1


def test_normalize_factor_rejects_invalid_range() -> None:
    with pytest.raises(ValueError, match="lower must be less than upper"):
        normalize_factor(1, lower=1, upper=1)

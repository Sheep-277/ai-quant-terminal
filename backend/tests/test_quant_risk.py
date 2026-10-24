import pytest

from app.quant.risk import (
    PositionInput,
    calculate_drawdown,
    calculate_exposure,
    calculate_max_drawdown,
    calculate_portfolio_risk,
    calculate_position_risk,
)


def test_calculate_drawdown_returns_empty_list_for_empty_curve() -> None:
    assert calculate_drawdown([]) == []


def test_calculate_drawdown_tracks_peak_to_current_decline() -> None:
    equity_curve = [100, 120, 90, 150, 135]

    drawdowns = calculate_drawdown(equity_curve)

    assert drawdowns == [
        pytest.approx(0),
        pytest.approx(0),
        pytest.approx(0.25),
        pytest.approx(0),
        pytest.approx(0.1),
    ]
    assert calculate_max_drawdown(equity_curve) == pytest.approx(0.25)


def test_calculate_drawdown_rejects_negative_equity() -> None:
    with pytest.raises(ValueError, match="equity value"):
        calculate_drawdown([100, -1])


def test_calculate_position_risk_uses_nav_as_denominator() -> None:
    positions = [
        PositionInput(symbol="NVDA", market_value=30_000),
        PositionInput(symbol="AAPL", market_value=20_000),
    ]

    risks = calculate_position_risk(positions, nav=100_000)

    assert risks[0].weight == pytest.approx(0.3)
    assert risks[1].weight == pytest.approx(0.2)


def test_calculate_exposure_supports_long_and_short_positions() -> None:
    positions = [
        PositionInput(symbol="NVDA", market_value=40_000, side="long"),
        PositionInput(symbol="SPY", market_value=15_000, side="short"),
    ]

    gross_exposure, net_exposure = calculate_exposure(positions, nav=100_000)

    assert gross_exposure == pytest.approx(0.55)
    assert net_exposure == pytest.approx(0.25)


def test_calculate_portfolio_risk_marks_concentration_and_low_cash() -> None:
    positions = [
        PositionInput(symbol="NVDA", market_value=42_000),
        PositionInput(symbol="AAPL", market_value=55_000),
    ]

    risk = calculate_portfolio_risk(
        positions,
        nav=100_000,
        cash=3_000,
        max_position_weight=0.4,
    )

    assert risk.gross_exposure == pytest.approx(0.97)
    assert risk.net_exposure == pytest.approx(0.97)
    assert risk.largest_position_weight == pytest.approx(0.55)
    assert risk.cash_weight == pytest.approx(0.03)
    assert risk.risk_flags == [
        "largest_position_weight_exceeded",
        "low_cash_weight",
    ]


def test_risk_calculation_rejects_invalid_nav() -> None:
    with pytest.raises(ValueError, match="nav must be greater than 0"):
        calculate_position_risk([], nav=0)

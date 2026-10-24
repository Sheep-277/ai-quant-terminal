import pytest

from app.quant.performance import (
    TradeResult,
    calculate_annualized_return,
    calculate_performance_snapshot,
    calculate_return_series,
    calculate_sharpe_ratio,
    calculate_total_return,
    calculate_win_rate,
)


def test_calculate_total_return_uses_initial_value_as_base() -> None:
    assert calculate_total_return(100_000, 125_000) == pytest.approx(0.25)


def test_calculate_total_return_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="initial_value"):
        calculate_total_return(0, 100)

    with pytest.raises(ValueError, match="final_value"):
        calculate_total_return(100, -1)


def test_calculate_annualized_return_handles_empty_period() -> None:
    assert calculate_annualized_return(0.1, trading_days=0) is None


def test_calculate_return_series_derives_period_returns() -> None:
    equity_curve = [100, 110, 99]

    returns = calculate_return_series(equity_curve)

    assert returns == [pytest.approx(0.1), pytest.approx(-0.1)]


def test_calculate_sharpe_ratio_returns_none_for_flat_returns() -> None:
    assert calculate_sharpe_ratio([0.01, 0.01, 0.01]) is None


def test_calculate_sharpe_ratio_returns_annualized_value() -> None:
    sharpe = calculate_sharpe_ratio([0.01, -0.005, 0.012, 0.003])

    assert sharpe is not None
    assert sharpe > 0


def test_calculate_win_rate_counts_profitable_trades() -> None:
    trades = [
        TradeResult(pnl=100),
        TradeResult(pnl=-20),
        TradeResult(pnl=0),
        TradeResult(pnl=50),
    ]

    assert calculate_win_rate(trades) == pytest.approx(0.5)


def test_calculate_performance_snapshot_combines_core_metrics() -> None:
    equity_curve = [100_000, 105_000, 102_000, 112_000]
    trades = [TradeResult(pnl=100), TradeResult(pnl=-50), TradeResult(pnl=30)]

    snapshot = calculate_performance_snapshot(equity_curve, trades)

    assert snapshot.initial_capital == pytest.approx(100_000)
    assert snapshot.final_value == pytest.approx(112_000)
    assert snapshot.total_return == pytest.approx(0.12)
    assert snapshot.annualized_return is not None
    assert snapshot.maximum_drawdown == pytest.approx(0.0285714286)
    assert snapshot.sharpe_ratio is not None
    assert snapshot.win_rate == pytest.approx(2 / 3)
    assert snapshot.trade_count == 3


def test_calculate_performance_snapshot_requires_two_equity_points() -> None:
    with pytest.raises(ValueError, match="at least two points"):
        calculate_performance_snapshot([100_000])

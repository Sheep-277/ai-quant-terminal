from datetime import date

import pytest

from app.quant.backtest import PriceBar, run_buy_and_hold_backtest


def test_run_buy_and_hold_backtest_builds_equity_curve_and_performance() -> None:
    bars = [
        PriceBar(timestamp=date(2025, 1, 1), close=100),
        PriceBar(timestamp=date(2025, 1, 2), close=105),
        PriceBar(timestamp=date(2025, 1, 3), close=110),
    ]

    result = run_buy_and_hold_backtest(
        "NVDA",
        bars,
        initial_capital=10_000,
        transaction_fee_rate=0,
        slippage_rate=0,
    )

    assert result.symbol == "NVDA"
    assert result.initial_capital == pytest.approx(10_000)
    assert result.final_value == pytest.approx(11_000)
    assert result.equity_curve == [pytest.approx(10_000), pytest.approx(10_500), pytest.approx(11_000)]
    assert result.performance is not None
    assert result.performance.total_return == pytest.approx(0.1)
    assert result.performance.win_rate == pytest.approx(1)
    assert result.performance.trade_count == 1


def test_run_buy_and_hold_backtest_applies_fee_and_slippage() -> None:
    bars = [
        PriceBar(timestamp=date(2025, 1, 1), close=100),
        PriceBar(timestamp=date(2025, 1, 2), close=110),
    ]

    result = run_buy_and_hold_backtest(
        "AAPL",
        bars,
        initial_capital=10_000,
        transaction_fee_rate=0.001,
        slippage_rate=0.001,
    )

    assert result.trades[0].price == pytest.approx(100.1)
    assert result.trades[1].price == pytest.approx(109.89)
    assert result.trades[0].fee > 0
    assert result.trades[1].fee > 0
    assert result.final_value < 10_989


def test_run_buy_and_hold_backtest_records_losing_trade() -> None:
    bars = [
        PriceBar(timestamp=date(2025, 1, 1), close=100),
        PriceBar(timestamp=date(2025, 1, 2), close=90),
    ]

    result = run_buy_and_hold_backtest(
        "AMD",
        bars,
        initial_capital=10_000,
        transaction_fee_rate=0,
        slippage_rate=0,
    )

    assert result.final_value == pytest.approx(9_000)
    assert result.trades[-1].pnl == pytest.approx(-1_000)
    assert result.performance is not None
    assert result.performance.win_rate == pytest.approx(0)


def test_run_buy_and_hold_backtest_rejects_unsorted_bars() -> None:
    bars = [
        PriceBar(timestamp=date(2025, 1, 2), close=100),
        PriceBar(timestamp=date(2025, 1, 1), close=101),
    ]

    with pytest.raises(ValueError, match="sorted by timestamp"):
        run_buy_and_hold_backtest("NVDA", bars, initial_capital=10_000)


def test_run_buy_and_hold_backtest_requires_enough_cash_for_one_share() -> None:
    bars = [
        PriceBar(timestamp=date(2025, 1, 1), close=100),
        PriceBar(timestamp=date(2025, 1, 2), close=101),
    ]

    with pytest.raises(ValueError, match="not enough to buy one share"):
        run_buy_and_hold_backtest("NVDA", bars, initial_capital=10)

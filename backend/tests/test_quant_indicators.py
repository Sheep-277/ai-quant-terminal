import pytest

from app.quant.indicators import calculate_ema, calculate_macd, calculate_rsi


def test_calculate_ema_keeps_input_length_and_starts_after_period() -> None:
    values = [10, 11, 12, 13, 14]

    ema = calculate_ema(values, period=3)

    assert ema[:2] == [None, None]
    assert ema[2] == pytest.approx(11)
    assert ema[3] == pytest.approx(12)
    assert ema[4] == pytest.approx(13)
    assert len(ema) == len(values)


def test_calculate_rsi_returns_none_when_sample_is_not_enough() -> None:
    closes = [10, 11, 12]

    rsi = calculate_rsi(closes, period=14)

    assert rsi == [None, None, None]


def test_calculate_rsi_handles_one_way_market_moves() -> None:
    rising = [float(value) for value in range(1, 18)]
    falling = [float(value) for value in range(18, 1, -1)]

    rising_rsi = calculate_rsi(rising, period=14)
    falling_rsi = calculate_rsi(falling, period=14)

    assert rising_rsi[-1] == pytest.approx(100)
    assert falling_rsi[-1] == pytest.approx(0)


def test_calculate_macd_returns_aligned_series() -> None:
    closes = [float(value) for value in range(1, 80)]

    macd = calculate_macd(closes)

    assert set(macd) == {"macd", "signal", "histogram"}
    assert len(macd["macd"]) == len(closes)
    assert len(macd["signal"]) == len(closes)
    assert len(macd["histogram"]) == len(closes)
    assert macd["macd"][-1] is not None
    assert macd["signal"][-1] is not None
    assert macd["histogram"][-1] == pytest.approx(
        macd["macd"][-1] - macd["signal"][-1],
    )


def test_calculate_macd_rejects_invalid_period_order() -> None:
    with pytest.raises(ValueError, match="fast_period must be less than slow_period"):
        calculate_macd([1, 2, 3], fast_period=26, slow_period=12)

"""技术指标计算。

本模块只放确定性量化计算，不访问数据库、Provider、LLM 或 HTTP 层。
所有函数输入相同价格序列时必须返回相同结果，方便服务层、回测和 Agent Tool 复用。
"""


def calculate_ema(values: list[float], period: int) -> list[float | None]:
    """计算 EMA 指数移动平均线。

    返回列表长度与输入一致；样本不足 `period` 前返回 None。
    第一条 EMA 使用前 `period` 个值的简单平均数作为起点。
    """

    if period <= 0:
        raise ValueError("period must be greater than 0")

    if len(values) < period:
        return [None for _ in values]

    multiplier = 2 / (period + 1)
    result: list[float | None] = [None for _ in range(period - 1)]
    ema = sum(values[:period]) / period
    result.append(ema)

    for value in values[period:]:
        ema = (value - ema) * multiplier + ema
        result.append(ema)

    return result


def calculate_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    """计算 RSI 相对强弱指标。

    RSI 取值范围通常为 0 到 100。样本不足或第一个价格点没有涨跌幅时返回 None。
    这里使用 Wilder 平滑方式，避免每个窗口完全重算导致结果不连续。
    """

    if period <= 0:
        raise ValueError("period must be greater than 0")

    if len(closes) <= period:
        return [None for _ in closes]

    gains: list[float] = []
    losses: list[float] = []

    for index in range(1, period + 1):
        change = closes[index] - closes[index - 1]
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))

    average_gain = sum(gains) / period
    average_loss = sum(losses) / period
    result: list[float | None] = [None for _ in range(period)]
    result.append(_to_rsi(average_gain, average_loss))

    for index in range(period + 1, len(closes)):
        change = closes[index] - closes[index - 1]
        gain = max(change, 0)
        loss = abs(min(change, 0))
        average_gain = ((average_gain * (period - 1)) + gain) / period
        average_loss = ((average_loss * (period - 1)) + loss) / period
        result.append(_to_rsi(average_gain, average_loss))

    return result


def calculate_macd(
    closes: list[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> dict[str, list[float | None]]:
    """计算 MACD、信号线和柱状图。

    返回字段：
    - `macd`：快 EMA 减慢 EMA。
    - `signal`：MACD 序列的 EMA。
    - `histogram`：MACD 减信号线。
    """

    if fast_period <= 0 or slow_period <= 0 or signal_period <= 0:
        raise ValueError("periods must be greater than 0")

    if fast_period >= slow_period:
        raise ValueError("fast_period must be less than slow_period")

    fast_ema = calculate_ema(closes, fast_period)
    slow_ema = calculate_ema(closes, slow_period)

    macd = [
        None if fast is None or slow is None else fast - slow
        for fast, slow in zip(fast_ema, slow_ema, strict=True)
    ]
    signal = _calculate_sparse_ema(macd, signal_period)
    histogram = [
        None if macd_value is None or signal_value is None else macd_value - signal_value
        for macd_value, signal_value in zip(macd, signal, strict=True)
    ]

    return {
        "macd": macd,
        "signal": signal,
        "histogram": histogram,
    }


def _to_rsi(average_gain: float, average_loss: float) -> float:
    """把平均上涨和平均下跌转换为 RSI 数值。"""

    if average_loss == 0:
        return 100.0

    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def _calculate_sparse_ema(
    values: list[float | None],
    period: int,
) -> list[float | None]:
    """对含 None 的序列计算 EMA，保持原始索引位置不变。"""

    first_valid_index = next(
        (index for index, value in enumerate(values) if value is not None),
        None,
    )
    if first_valid_index is None:
        return [None for _ in values]

    compact_values = [value for value in values[first_valid_index:] if value is not None]
    compact_ema = calculate_ema(compact_values, period)

    return [None for _ in range(first_valid_index)] + compact_ema

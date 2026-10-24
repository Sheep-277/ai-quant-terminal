"""量化因子计算。

因子是把原始行情、财务指标转换成可比较数值的中间层。
本模块只做确定性计算，不产生买卖建议，也不访问外部数据源。
"""

from dataclasses import dataclass
from math import sqrt
from statistics import pstdev

from app.quant.indicators import calculate_ema


TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class FactorSnapshot:
    """单个标的在某个时间点的核心因子快照。"""

    momentum_20d: float | None
    trend_strength: float | None
    volatility_20d: float | None
    quality_score: float | None
    composite_score: float | None


def calculate_momentum(closes: list[float], window: int = 20) -> float | None:
    """计算指定窗口的价格动量。

    例如 20 日动量 = 最新收盘价 / 20 个交易日前收盘价 - 1。
    样本不足时返回 None，避免用不完整窗口制造假信号。
    """

    if window <= 0:
        raise ValueError("window must be greater than 0")

    if len(closes) <= window:
        return None

    base_price = closes[-window - 1]
    if base_price == 0:
        return None

    return closes[-1] / base_price - 1


def calculate_trend_strength(closes: list[float], ema_period: int = 20) -> float | None:
    """计算最新价格相对 EMA 的趋势强度。

    返回值为 `最新收盘价 / EMA - 1`。正数通常表示价格高于趋势线。
    """

    if ema_period <= 0:
        raise ValueError("ema_period must be greater than 0")

    ema = calculate_ema(closes, ema_period)
    latest_ema = ema[-1] if ema else None
    if latest_ema in (None, 0):
        return None

    return closes[-1] / latest_ema - 1


def calculate_volatility(closes: list[float], window: int = 20) -> float | None:
    """计算年化波动率。

    先计算日收益率的总体标准差，再按 252 个交易日年化。
    """

    if window <= 0:
        raise ValueError("window must be greater than 0")

    if len(closes) <= window:
        return None

    returns = [
        closes[index] / closes[index - 1] - 1
        for index in range(len(closes) - window, len(closes))
        if closes[index - 1] != 0
    ]
    if len(returns) < window:
        return None

    return pstdev(returns) * sqrt(TRADING_DAYS_PER_YEAR)


def calculate_quality_score(
    roe: float | None = None,
    roic: float | None = None,
    gross_margin: float | None = None,
) -> float | None:
    """把盈利能力指标归一化为 0 到 1 的质量因子评分。"""

    scores = [
        _normalize_optional(roe, lower=0, upper=0.3),
        _normalize_optional(roic, lower=0, upper=0.25),
        _normalize_optional(gross_margin, lower=0, upper=0.7),
    ]
    valid_scores = [score for score in scores if score is not None]
    if not valid_scores:
        return None

    return sum(valid_scores) / len(valid_scores)


def normalize_factor(
    value: float | None,
    lower: float,
    upper: float,
    *,
    invert: bool = False,
) -> float | None:
    """把因子值压缩到 0 到 1，方便不同量纲的指标合成。"""

    if value is None:
        return None

    if lower >= upper:
        raise ValueError("lower must be less than upper")

    score = (value - lower) / (upper - lower)
    clamped_score = min(max(score, 0), 1)
    return 1 - clamped_score if invert else clamped_score


def calculate_factor_snapshot(
    closes: list[float],
    *,
    roe: float | None = None,
    roic: float | None = None,
    gross_margin: float | None = None,
) -> FactorSnapshot:
    """计算单个标的的基础因子快照。"""

    momentum_20d = calculate_momentum(closes, window=20)
    trend_strength = calculate_trend_strength(closes, ema_period=20)
    volatility_20d = calculate_volatility(closes, window=20)
    quality_score = calculate_quality_score(
        roe=roe,
        roic=roic,
        gross_margin=gross_margin,
    )
    composite_score = _average_available(
        [
            normalize_factor(momentum_20d, lower=-0.2, upper=0.2),
            normalize_factor(trend_strength, lower=-0.1, upper=0.1),
            normalize_factor(volatility_20d, lower=0, upper=0.6, invert=True),
            quality_score,
        ],
    )

    return FactorSnapshot(
        momentum_20d=momentum_20d,
        trend_strength=trend_strength,
        volatility_20d=volatility_20d,
        quality_score=quality_score,
        composite_score=composite_score,
    )


def _normalize_optional(
    value: float | None,
    *,
    lower: float,
    upper: float,
) -> float | None:
    """归一化可缺失指标，缺失时不参与平均。"""

    return normalize_factor(value, lower=lower, upper=upper)


def _average_available(values: list[float | None]) -> float | None:
    """计算非空评分的平均值。"""

    valid_values = [value for value in values if value is not None]
    if not valid_values:
        return None

    return sum(valid_values) / len(valid_values)

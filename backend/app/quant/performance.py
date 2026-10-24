"""绩效指标计算。

本模块用于回测和组合复盘中的确定性绩效计算。
它只根据输入数据计算指标，不评价策略好坏，也不生成投资建议。
"""

from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev

from app.quant.risk import calculate_max_drawdown


TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class TradeResult:
    """单笔交易结果，用于计算胜率。"""

    pnl: float


@dataclass(frozen=True)
class PerformanceSnapshot:
    """回测或组合在一个区间内的绩效快照。"""

    initial_capital: float
    final_value: float
    total_return: float
    annualized_return: float | None
    maximum_drawdown: float | None
    sharpe_ratio: float | None
    win_rate: float | None
    trade_count: int


def calculate_total_return(initial_value: float, final_value: float) -> float:
    """计算总收益率。"""

    if initial_value <= 0:
        raise ValueError("initial_value must be greater than 0")

    if final_value < 0:
        raise ValueError("final_value must be greater than or equal to 0")

    return final_value / initial_value - 1


def calculate_annualized_return(total_return: float, trading_days: int) -> float | None:
    """把区间收益率换算为年化收益率。"""

    if trading_days <= 0:
        return None

    if total_return <= -1:
        return -1.0

    return (1 + total_return) ** (TRADING_DAYS_PER_YEAR / trading_days) - 1


def calculate_return_series(equity_curve: list[float]) -> list[float]:
    """根据权益曲线计算逐期收益率序列。"""

    if len(equity_curve) < 2:
        return []

    returns: list[float] = []
    for previous, current in zip(equity_curve, equity_curve[1:]):
        if previous <= 0:
            raise ValueError("equity values must be greater than 0")
        if current < 0:
            raise ValueError("equity values must be greater than or equal to 0")
        returns.append(current / previous - 1)

    return returns


def calculate_sharpe_ratio(
    returns: list[float],
    *,
    risk_free_rate: float = 0,
) -> float | None:
    """计算年化 Sharpe Ratio 夏普比率。"""

    if len(returns) < 2:
        return None

    daily_risk_free_rate = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess_returns = [item - daily_risk_free_rate for item in returns]
    volatility = pstdev(excess_returns)
    if volatility == 0:
        return None

    return mean(excess_returns) / volatility * sqrt(TRADING_DAYS_PER_YEAR)


def calculate_win_rate(trades: list[TradeResult]) -> float | None:
    """计算盈利交易占比。"""

    if not trades:
        return None

    winning_trades = [trade for trade in trades if trade.pnl > 0]
    return len(winning_trades) / len(trades)


def calculate_performance_snapshot(
    equity_curve: list[float],
    trades: list[TradeResult] | None = None,
    *,
    risk_free_rate: float = 0,
) -> PerformanceSnapshot:
    """从权益曲线和交易结果生成绩效快照。"""

    if len(equity_curve) < 2:
        raise ValueError("equity_curve must contain at least two points")

    initial_capital = equity_curve[0]
    final_value = equity_curve[-1]
    total_return = calculate_total_return(initial_capital, final_value)
    returns = calculate_return_series(equity_curve)
    trade_results = trades or []

    return PerformanceSnapshot(
        initial_capital=initial_capital,
        final_value=final_value,
        total_return=total_return,
        annualized_return=calculate_annualized_return(
            total_return,
            trading_days=len(equity_curve) - 1,
        ),
        maximum_drawdown=calculate_max_drawdown(equity_curve),
        sharpe_ratio=calculate_sharpe_ratio(
            returns,
            risk_free_rate=risk_free_rate,
        ),
        win_rate=calculate_win_rate(trade_results),
        trade_count=len(trade_results),
    )

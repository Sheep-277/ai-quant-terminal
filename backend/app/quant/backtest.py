"""最小回测执行骨架。

Backtest Engine 负责用历史数据模拟策略表现。
本模块只使用调用方传入的价格序列，不读取真实行情 Provider，也不提交真实订单。
"""

from dataclasses import dataclass, field
from datetime import date

from app.quant.performance import PerformanceSnapshot, TradeResult, calculate_performance_snapshot


@dataclass(frozen=True)
class PriceBar:
    """回测所需的最小价格数据。"""

    timestamp: date
    close: float


@dataclass(frozen=True)
class SimulatedTrade:
    """回测中的模拟成交记录，不代表真实交易。"""

    timestamp: date
    symbol: str
    side: str
    quantity: int
    price: float
    fee: float
    slippage: float
    pnl: float


@dataclass(frozen=True)
class BacktestRunResult:
    """一次回测运行的结构化结果。"""

    symbol: str
    initial_capital: float
    final_value: float
    equity_curve: list[float]
    trades: list[SimulatedTrade] = field(default_factory=list)
    performance: PerformanceSnapshot | None = None


def run_buy_and_hold_backtest(
    symbol: str,
    bars: list[PriceBar],
    *,
    initial_capital: float,
    transaction_fee_rate: float = 0.0005,
    slippage_rate: float = 0.0005,
) -> BacktestRunResult:
    """运行单标的买入并持有回测。

    策略在第一根 K 线买入，最后一根 K 线平仓，期间每日按收盘价估算权益。
    这是最小回测闭环，后续多标的、调仓、风控规则会在它之上扩展。
    """

    _validate_backtest_inputs(
        bars=bars,
        initial_capital=initial_capital,
        transaction_fee_rate=transaction_fee_rate,
        slippage_rate=slippage_rate,
    )

    entry_bar = bars[0]
    exit_bar = bars[-1]
    entry_price = entry_bar.close * (1 + slippage_rate)
    quantity = int(initial_capital / (entry_price * (1 + transaction_fee_rate)))

    if quantity <= 0:
        raise ValueError("initial_capital is not enough to buy one share")

    entry_value = quantity * entry_price
    entry_fee = entry_value * transaction_fee_rate
    cash = initial_capital - entry_value - entry_fee
    equity_curve = [cash + quantity * bar.close for bar in bars]

    exit_price = exit_bar.close * (1 - slippage_rate)
    exit_value = quantity * exit_price
    exit_fee = exit_value * transaction_fee_rate
    final_value = cash + exit_value - exit_fee
    realized_pnl = final_value - initial_capital
    equity_curve[-1] = final_value

    trades = [
        SimulatedTrade(
            timestamp=entry_bar.timestamp,
            symbol=symbol,
            side="buy",
            quantity=quantity,
            price=entry_price,
            fee=entry_fee,
            slippage=entry_bar.close * slippage_rate * quantity,
            pnl=0,
        ),
        SimulatedTrade(
            timestamp=exit_bar.timestamp,
            symbol=symbol,
            side="sell",
            quantity=quantity,
            price=exit_price,
            fee=exit_fee,
            slippage=exit_bar.close * slippage_rate * quantity,
            pnl=realized_pnl,
        ),
    ]
    performance = calculate_performance_snapshot(
        equity_curve,
        trades=[TradeResult(pnl=realized_pnl)],
    )

    return BacktestRunResult(
        symbol=symbol,
        initial_capital=initial_capital,
        final_value=final_value,
        equity_curve=equity_curve,
        trades=trades,
        performance=performance,
    )


def _validate_backtest_inputs(
    *,
    bars: list[PriceBar],
    initial_capital: float,
    transaction_fee_rate: float,
    slippage_rate: float,
) -> None:
    """校验回测输入，避免生成无意义或带未来数据顺序错误的结果。"""

    if len(bars) < 2:
        raise ValueError("bars must contain at least two points")

    if initial_capital <= 0:
        raise ValueError("initial_capital must be greater than 0")

    if not 0 <= transaction_fee_rate <= 0.1:
        raise ValueError("transaction_fee_rate must be between 0 and 0.1")

    if not 0 <= slippage_rate <= 0.1:
        raise ValueError("slippage_rate must be between 0 and 0.1")

    previous_timestamp: date | None = None
    for bar in bars:
        if bar.close <= 0:
            raise ValueError("bar close must be greater than 0")

        if previous_timestamp is not None and bar.timestamp <= previous_timestamp:
            raise ValueError("bars must be sorted by timestamp ascending")

        previous_timestamp = bar.timestamp

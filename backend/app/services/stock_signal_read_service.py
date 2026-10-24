from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.market import MarketCode
from app.db.repositories.signal_repository import SignalRepository
from app.models.signal import Signal
from app.schemas.market import Direction
from app.schemas.stock import StockQuantSignal


@dataclass(frozen=True)
class StockSignalReadSnapshot:
    """个股量化信号只读快照。"""

    quant_signals: list[StockQuantSignal]
    source: str


def get_stock_signal_read_snapshot(
    session: Session,
    market: MarketCode,
    symbol: str,
) -> StockSignalReadSnapshot | None:
    """从数据库读取最新量化信号；无数据时返回 None，让调用方回退 Quant Pipeline。"""

    normalized_symbol = symbol.strip().upper()
    signals = SignalRepository(session).list_latest_by_market_symbol(market.value, normalized_symbol)
    if not signals:
        return None

    return StockSignalReadSnapshot(
        quant_signals=[_signal_to_schema(signal) for signal in signals],
        source="database",
    )


def _signal_to_schema(signal: Signal) -> StockQuantSignal:
    """把数据库信号转换成个股研究 API schema。"""

    return StockQuantSignal(
        code=signal.signal_type,
        title=_localize_signal_title(signal.signal_type),
        direction=Direction(signal.direction),
        severity=signal.severity,
        score=signal.score,
        evidence=list(signal.evidence),
    )


def _localize_signal_title(code: str) -> str:
    """把量化信号码转换成个股研究页面可读的中文标题。"""

    title_map = {
        "momentum_strength": "20 日动量增强",
        "momentum_weakness": "20 日动量转弱",
        "trend_above_ema": "价格站上 EMA 趋势线",
        "trend_below_ema": "价格跌破 EMA 趋势线",
        "volatility_elevated": "20 日年化波动率升高",
        "composite_score_high": "综合因子评分较高",
        "composite_score_low": "综合因子评分较低",
    }
    return title_map.get(code, code)

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.signal import Signal


class SignalRepository:
    """量化信号 Repository，封装 signals 表的基础读写。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_latest_by_market_symbol(self, market: str, symbol: str, *, limit: int = 20) -> list[Signal]:
        """按触发时间倒序查询指定标的的最新量化信号。"""

        statement = (
            select(Signal)
            .where(
                Signal.market == market.upper(),
                Signal.symbol == symbol.strip().upper(),
            )
            .order_by(Signal.triggered_at.desc(), Signal.score.desc(), Signal.id.desc())
            .limit(limit)
        )
        return list(self._session.execute(statement).scalars().all())

    def list_latest_by_market(self, market: str, *, limit: int = 20) -> list[Signal]:
        """按触发时间倒序查询指定市场的最新量化信号。"""

        statement = (
            select(Signal)
            .where(Signal.market == market.upper())
            .order_by(Signal.triggered_at.desc(), Signal.score.desc(), Signal.id.desc())
            .limit(limit)
        )
        return list(self._session.execute(statement).scalars().all())

    def save_signals(self, signals: Sequence[Signal]) -> list[Signal]:
        """批量保存信号；同市场、代码、信号类型和触发时间存在时更新原记录。"""

        saved_signals: list[Signal] = []
        for signal in signals:
            saved_signals.append(self._save_one(signal))
        return saved_signals

    def _save_one(self, signal: Signal) -> Signal:
        """保存单条信号，事务提交由调用方控制。"""

        statement = select(Signal).where(
            Signal.market == signal.market.upper(),
            Signal.symbol == signal.symbol.strip().upper(),
            Signal.signal_type == signal.signal_type,
            Signal.triggered_at == signal.triggered_at,
        )
        existing_signal = self._session.execute(statement).scalar_one_or_none()
        if existing_signal is None:
            self._session.add(signal)
            return signal

        existing_signal.stock_id = signal.stock_id
        existing_signal.direction = signal.direction
        existing_signal.severity = signal.severity
        existing_signal.score = signal.score
        existing_signal.evidence = signal.evidence
        existing_signal.source = signal.source
        return existing_signal

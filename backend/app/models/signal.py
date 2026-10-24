from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Signal(Base):
    """量化信号表，保存规则或因子在某一时点触发的结构化提示。"""

    __tablename__ = "signals"
    __table_args__ = (
        UniqueConstraint("market", "symbol", "signal_type", "triggered_at", name="uq_signals_trigger"),
        Index("idx_signals_market_time", "market", "triggered_at"),
        Index("idx_signals_symbol_time", "market", "symbol", "triggered_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    triggered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class MarketBar(Base):
    """历史 K 线表，保存标的在固定周期内的 OHLCV 行情。"""

    __tablename__ = "market_bars"
    __table_args__ = (
        UniqueConstraint("market", "symbol", "interval_code", "bar_timestamp", name="uq_market_bars"),
        CheckConstraint(
            "data_status IN ('realtime', 'delayed', 'unavailable')",
            name="ck_market_bars_status",
        ),
        Index("idx_market_bars_symbol_time", "market", "symbol", "interval_code", "bar_timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    interval_code: Mapped[str] = mapped_column(String(16), nullable=False)
    bar_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    open_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    high_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    low_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    data_status: Mapped[str] = mapped_column(String(16), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

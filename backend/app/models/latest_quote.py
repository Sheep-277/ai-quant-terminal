from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LatestQuote(Base):
    """最新行情表，保存每个市场标的当前可展示的行情快照。"""

    __tablename__ = "latest_quotes"
    __table_args__ = (
        UniqueConstraint("market", "symbol", name="uq_latest_quotes_market_symbol"),
        CheckConstraint(
            "data_status IN ('realtime', 'delayed', 'unavailable')",
            name="ck_latest_quotes_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    change_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    change_percent: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    turnover: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False, default=Decimal("0"))
    data_status: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    quote_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

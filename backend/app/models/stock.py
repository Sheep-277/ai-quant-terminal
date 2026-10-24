from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Stock(Base):
    """股票主数据表，记录跨市场标的的基础身份信息。"""

    __tablename__ = "stocks"
    __table_args__ = (
        UniqueConstraint("market", "symbol", name="uq_stocks_market_symbol"),
        CheckConstraint("market IN ('US', 'HK', 'CN')", name="ck_stocks_market"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False, default="common_stock")
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(64))
    industry: Mapped[str | None] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

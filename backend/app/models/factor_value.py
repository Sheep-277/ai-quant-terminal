from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class FactorValue(Base):
    """因子值表，保存某一交易日的动量、质量、波动率等可比较数值。"""

    __tablename__ = "factor_values"
    __table_args__ = (
        UniqueConstraint("market", "symbol", "factor_name", "as_of_date", name="uq_factor_values_daily"),
        Index("idx_factor_values_symbol_date", "market", "symbol", "as_of_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    factor_name: Mapped[str] = mapped_column(String(64), nullable=False)
    factor_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    data_status: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Financial(Base):
    """基本面财务表，保存财报期收入、利润率、资本回报和现金流指标。"""

    __tablename__ = "financials"
    __table_args__ = (
        UniqueConstraint("market", "symbol", "fiscal_period", "period_end_date", name="uq_financials_period"),
        Index("idx_financials_symbol_period", "market", "symbol", "period_end_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    fiscal_period: Mapped[str] = mapped_column(String(32), nullable=False)
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    net_income: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    gross_margin: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    operating_margin: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    roe: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    roic: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    operating_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    capex: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    fcf: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

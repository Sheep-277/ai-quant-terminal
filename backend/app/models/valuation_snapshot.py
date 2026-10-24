from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ValuationSnapshot(Base):
    """估值快照表，记录某一时点的 PE、PB、PS 和 P/FCF 指标。"""

    __tablename__ = "valuation_snapshots"
    __table_args__ = (
        UniqueConstraint("market", "symbol", "snapshot_timestamp", name="uq_valuation_snapshot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    pe_ttm: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    pb: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    ps_ttm: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    pfcf_ttm: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    snapshot_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

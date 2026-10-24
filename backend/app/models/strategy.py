from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Strategy(Base):
    """策略主表，保存 Strategy Lab 中策略草案的身份、状态和当前规则快照。"""

    __tablename__ = "strategies"
    __table_args__ = (
        UniqueConstraint("strategy_id", name="uq_strategies_strategy_id"),
        Index("idx_strategies_market_status", "market", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    universe: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    entry_conditions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    exit_conditions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    position_rule: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    rebalance_frequency: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_constraints: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

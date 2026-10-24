from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AgentTask(Base):
    """AI Research 任务表，保存用户提交的问题、市场和当前执行状态。"""

    __tablename__ = "agent_tasks"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_agent_tasks_task_id"),
        Index("idx_agent_tasks_market_status", "market", "status"),
        Index("idx_agent_tasks_market_time", "market", "accepted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(String(128), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    symbols: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    data_status: Mapped[str] = mapped_column(String(32), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    route_prefix: Mapped[str] = mapped_column(String(64), nullable=False)
    include_strategy_idea: Mapped[bool] = mapped_column(nullable=False, default=False)
    result_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    accepted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ResearchEvidence(Base):
    """AI Research 证据表，保存结论引用的结构化证据摘要。"""

    __tablename__ = "research_evidence"
    __table_args__ = (
        UniqueConstraint("task_id", "evidence_id", name="uq_research_evidence_task_evidence"),
        Index("idx_research_evidence_task", "task_id"),
        Index("idx_research_evidence_market_symbol", "market", "symbol"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    task_pk: Mapped[int] = mapped_column(ForeignKey("agent_tasks.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence_id: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(160), nullable=False)
    data_status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

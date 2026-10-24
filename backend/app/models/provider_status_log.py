from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ProviderStatusLog(Base):
    """数据源状态日志表，记录 Provider 健康检查和回退状态。"""

    __tablename__ = "provider_status_logs"
    __table_args__ = (
        CheckConstraint("mode IN ('mock', 'real')", name="ck_provider_status_mode"),
        CheckConstraint(
            "data_status IN ('realtime', 'delayed', 'unavailable')",
            name="ck_provider_status_data_status",
        ),
        Index("idx_provider_status_checked_at", "checked_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    ready: Mapped[bool] = mapped_column(Boolean, nullable=False)
    data_status: Mapped[str] = mapped_column(String(16), nullable=False)
    fallback_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fallback_reason: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

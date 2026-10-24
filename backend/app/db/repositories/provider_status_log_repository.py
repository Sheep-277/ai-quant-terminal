from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.provider_status_log import ProviderStatusLog


class ProviderStatusLogRepository:
    """数据源状态日志 Repository，封装 provider_status_logs 表的读写。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, status_log: ProviderStatusLog) -> ProviderStatusLog:
        """新增一条 Provider 状态日志，事务提交由调用方控制。"""

        self._session.add(status_log)
        return status_log

    def get_latest(self, provider_name: str | None = None) -> ProviderStatusLog | None:
        """查询最近一次 Provider 状态；可按数据源名称过滤。"""

        statement = select(ProviderStatusLog)
        if provider_name is not None:
            statement = statement.where(ProviderStatusLog.provider_name == provider_name)

        statement = statement.order_by(ProviderStatusLog.checked_at.desc(), ProviderStatusLog.id.desc()).limit(1)
        return self._session.execute(statement).scalar_one_or_none()

    def list_recent(self, *, limit: int = 20, provider_name: str | None = None) -> list[ProviderStatusLog]:
        """按检查时间倒序查询最近的 Provider 状态日志。"""

        statement = select(ProviderStatusLog)
        if provider_name is not None:
            statement = statement.where(ProviderStatusLog.provider_name == provider_name)

        statement = statement.order_by(ProviderStatusLog.checked_at.desc(), ProviderStatusLog.id.desc()).limit(limit)
        return list(self._session.execute(statement).scalars().all())

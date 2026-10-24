from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.ai_research import AgentTask, ResearchEvidence


class AIResearchRepository:
    """AI Research Repository，封装任务和证据表的基础读写。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_task_by_task_id(self, task_id: str) -> AgentTask | None:
        """根据业务 task_id 查询 AI Research 任务。"""

        statement = select(AgentTask).where(AgentTask.task_id == task_id.strip())
        return self._session.execute(statement).scalar_one_or_none()

    def list_tasks_by_market(self, market: str, *, status: str | None = None, limit: int = 20) -> list[AgentTask]:
        """按市场查询最近的 AI Research 任务，可选按状态过滤。"""

        statement = select(AgentTask).where(AgentTask.market == market.upper())
        if status is not None:
            statement = statement.where(AgentTask.status == status)
        statement = statement.order_by(AgentTask.accepted_at.desc(), AgentTask.id.desc()).limit(limit)
        return list(self._session.execute(statement).scalars().all())

    def save_task(self, task: AgentTask) -> AgentTask:
        """保存任务；task_id 已存在时更新任务状态和快照。"""

        existing_task = self.get_task_by_task_id(task.task_id)
        if existing_task is None:
            self._session.add(task)
            return task

        existing_task.market = task.market.upper()
        existing_task.query = task.query
        existing_task.symbols = task.symbols
        existing_task.status = task.status
        existing_task.data_status = task.data_status
        existing_task.timezone = task.timezone
        existing_task.route_prefix = task.route_prefix
        existing_task.include_strategy_idea = task.include_strategy_idea
        existing_task.result_snapshot = task.result_snapshot
        existing_task.accepted_at = task.accepted_at
        existing_task.completed_at = task.completed_at
        return existing_task

    def replace_evidence(
        self,
        task: AgentTask,
        evidence: Sequence[ResearchEvidence],
    ) -> list[ResearchEvidence]:
        """替换某个 AI Research 任务的证据列表，事务提交由调用方控制。"""

        self._session.execute(delete(ResearchEvidence).where(ResearchEvidence.task_id == task.task_id))
        evidence_list = list(evidence)
        for item in evidence_list:
            item.task_pk = task.id
            item.task_id = task.task_id
        self._session.add_all(evidence_list)
        return evidence_list

    def list_evidence(self, task_id: str) -> list[ResearchEvidence]:
        """按证据时间和主键顺序查询指定任务的证据。"""

        statement = (
            select(ResearchEvidence)
            .where(ResearchEvidence.task_id == task_id.strip())
            .order_by(ResearchEvidence.evidence_timestamp.asc(), ResearchEvidence.id.asc())
        )
        return list(self._session.execute(statement).scalars().all())

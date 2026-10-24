from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.strategy import Strategy


class StrategyRepository:
    """策略 Repository，封装 strategies 表的基础读写。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_strategy_id(self, strategy_id: str) -> Strategy | None:
        """根据业务 strategy_id 查询策略。"""

        statement = select(Strategy).where(Strategy.strategy_id == strategy_id.strip())
        return self._session.execute(statement).scalar_one_or_none()

    def list_by_market(self, market: str, *, status: str | None = None, limit: int = 20) -> list[Strategy]:
        """按市场查询策略草案，默认返回最近更新的策略。"""

        statement = select(Strategy).where(Strategy.market == market.upper())
        if status is not None:
            statement = statement.where(Strategy.status == status)
        statement = statement.order_by(Strategy.updated_at.desc(), Strategy.id.desc()).limit(limit)
        return list(self._session.execute(statement).scalars().all())

    def save_strategy(self, strategy: Strategy) -> Strategy:
        """保存策略；strategy_id 已存在时更新当前规则快照。"""

        existing_strategy = self.get_by_strategy_id(strategy.strategy_id)
        if existing_strategy is None:
            self._session.add(strategy)
            return strategy

        existing_strategy.market = strategy.market.upper()
        existing_strategy.name = strategy.name
        existing_strategy.description = strategy.description
        existing_strategy.status = strategy.status
        existing_strategy.created_by = strategy.created_by
        existing_strategy.current_version = strategy.current_version
        existing_strategy.universe = strategy.universe
        existing_strategy.entry_conditions = strategy.entry_conditions
        existing_strategy.exit_conditions = strategy.exit_conditions
        existing_strategy.position_rule = strategy.position_rule
        existing_strategy.rebalance_frequency = strategy.rebalance_frequency
        existing_strategy.risk_constraints = strategy.risk_constraints
        existing_strategy.parameters = strategy.parameters
        return existing_strategy

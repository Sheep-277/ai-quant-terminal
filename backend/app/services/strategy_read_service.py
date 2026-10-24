from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.market import MarketCode
from app.db.repositories.strategy_repository import StrategyRepository
from app.models.strategy import Strategy
from app.schemas.strategy import (
    PositionRule,
    RebalanceFrequency,
    RiskConstraint,
    StrategyCondition,
    StrategyCreatedBy,
    StrategyDraft,
    StrategyStatus,
    StrategyUniverse,
)


@dataclass(frozen=True)
class StrategyReadSnapshot:
    """Strategy Lab 策略草案只读快照。"""

    drafts: list[StrategyDraft]
    source: str


def get_strategy_read_snapshot(
    session: Session,
    market: MarketCode,
) -> StrategyReadSnapshot | None:
    """从数据库读取当前市场的策略草案；无数据时返回 None，让调用方回退 Mock。"""

    strategies = StrategyRepository(session).list_by_market(market.value, status=StrategyStatus.DRAFT.value)
    if not strategies:
        return None

    return StrategyReadSnapshot(
        drafts=[_strategy_to_draft(strategy) for strategy in strategies],
        source="database",
    )


def _strategy_to_draft(strategy: Strategy) -> StrategyDraft:
    """把数据库策略记录转换为 Strategy Lab API schema。"""

    return StrategyDraft(
        strategy_id=strategy.strategy_id,
        name=strategy.name,
        version=strategy.current_version,
        description=strategy.description,
        status=StrategyStatus(strategy.status),
        created_by=StrategyCreatedBy(strategy.created_by),
        created_at=strategy.created_at,
        updated_at=strategy.updated_at,
        universe=StrategyUniverse.model_validate(strategy.universe),
        entry_conditions=[StrategyCondition.model_validate(condition) for condition in strategy.entry_conditions],
        exit_conditions=[StrategyCondition.model_validate(condition) for condition in strategy.exit_conditions],
        position_rule=PositionRule.model_validate(strategy.position_rule),
        rebalance_frequency=RebalanceFrequency(strategy.rebalance_frequency),
        risk_constraints=[RiskConstraint.model_validate(constraint) for constraint in strategy.risk_constraints],
        parameters=strategy.parameters,
    )

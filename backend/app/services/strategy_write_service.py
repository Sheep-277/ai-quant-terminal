from sqlalchemy.orm import Session

from app.db.repositories.strategy_repository import StrategyRepository
from app.models.strategy import Strategy
from app.schemas.strategy import StrategyDraft, StrategyDraftCreateRequest, StrategyStatus
from app.services.mock_strategy_service import create_mock_strategy_draft
from app.services.strategy_read_service import _strategy_to_draft


def create_strategy_draft_record(session: Session, request: StrategyDraftCreateRequest) -> StrategyDraft:
    """把用户提交的策略草案保存到 strategies 表，并返回持久化后的草案快照。"""

    draft = create_mock_strategy_draft(request)
    strategy = Strategy(
        strategy_id=draft.strategy_id,
        market=request.market.value,
        name=draft.name,
        description=draft.description,
        status=StrategyStatus.DRAFT.value,
        created_by=draft.created_by.value,
        current_version=draft.version,
        universe=draft.universe.model_dump(mode="json"),
        entry_conditions=[condition.model_dump(mode="json") for condition in draft.entry_conditions],
        exit_conditions=[condition.model_dump(mode="json") for condition in draft.exit_conditions],
        position_rule=draft.position_rule.model_dump(mode="json"),
        rebalance_frequency=draft.rebalance_frequency.value,
        risk_constraints=[constraint.model_dump(mode="json") for constraint in draft.risk_constraints],
        parameters={
            **draft.parameters,
            "storage_source": "database",
        },
    )

    saved_strategy = StrategyRepository(session).save_strategy(strategy)
    session.commit()
    session.refresh(saved_strategy)
    return _strategy_to_draft(saved_strategy)

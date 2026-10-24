from datetime import datetime

from app.core.market import MarketCode
from app.db.repositories.strategy_repository import StrategyRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.strategy import Strategy
from app.services.strategy_read_service import get_strategy_read_snapshot


def _strategy(
    strategy_id: str = "mock-us-momentum-quality-v1",
    *,
    market: str = "US",
    status: str = "draft",
) -> Strategy:
    return Strategy(
        strategy_id=strategy_id,
        market=market,
        name="US Momentum Quality Draft",
        description="筛选 20 日动量较强、ROE 较高且成交量放大的美股科技标的。",
        status=status,
        created_by="agent",
        current_version=1,
        universe={
            "market": market,
            "universe_type": "index",
            "name": "NASDAQ 100",
            "symbols": ["NVDA", "AAPL"],
        },
        entry_conditions=[
            {
                "field": "momentum_20d",
                "operator": "gt",
                "value": 0.1,
                "upper_value": None,
                "description": "20 日动量大于 10%",
            }
        ],
        exit_conditions=[
            {
                "field": "rsi_14",
                "operator": "gt",
                "value": 75,
                "upper_value": None,
                "description": "RSI 过热时退出",
            }
        ],
        position_rule={"max_holdings": 10, "max_position_weight": 0.12, "equal_weight": True},
        rebalance_frequency="weekly",
        risk_constraints=[{"max_drawdown": 0.18, "stop_loss": 0.08, "min_liquidity": 50_000_000}],
        parameters={"data_mode": "mock", "live_trading_enabled": False},
        created_at=datetime(2026, 9, 28, 10, 30),
        updated_at=datetime(2026, 9, 28, 10, 30),
    )


def test_strategy_read_service_returns_database_drafts() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        StrategyRepository(session).save_strategy(_strategy())
        session.commit()

        snapshot = get_strategy_read_snapshot(session, MarketCode.US)

        assert snapshot is not None
        assert snapshot.source == "database"
        assert len(snapshot.drafts) == 1
        assert snapshot.drafts[0].strategy_id == "mock-us-momentum-quality-v1"
        assert snapshot.drafts[0].universe.symbols == ["NVDA", "AAPL"]
        assert snapshot.drafts[0].entry_conditions[0].field == "momentum_20d"
        assert snapshot.drafts[0].parameters["live_trading_enabled"] is False


def test_strategy_read_service_returns_none_without_drafts() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        snapshot = get_strategy_read_snapshot(session, MarketCode.US)

        assert snapshot is None


def test_strategy_read_service_uses_only_current_market_drafts() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = StrategyRepository(session)
        repository.save_strategy(_strategy("strategy-us-draft"))
        repository.save_strategy(_strategy("strategy-us-confirmed", status="confirmed"))
        repository.save_strategy(_strategy("strategy-hk-draft", market="HK"))
        session.commit()

        snapshot = get_strategy_read_snapshot(session, MarketCode.US)

        assert snapshot is not None
        assert [draft.strategy_id for draft in snapshot.drafts] == ["strategy-us-draft"]
        assert snapshot.drafts[0].status == "draft"
        assert snapshot.drafts[0].universe.market == MarketCode.US

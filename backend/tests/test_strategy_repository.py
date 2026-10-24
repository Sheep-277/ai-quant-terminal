from datetime import datetime

from app.db.repositories.strategy_repository import StrategyRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.strategy import Strategy


def _strategy(
    strategy_id: str = "mock-us-momentum-quality-v1",
    *,
    market: str = "US",
    name: str = "US Momentum Quality Draft",
    status: str = "draft",
    updated_at: datetime | None = None,
) -> Strategy:
    strategy = Strategy(
        strategy_id=strategy_id,
        market=market,
        name=name,
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
    )
    if updated_at is not None:
        strategy.updated_at = updated_at
    return strategy


def test_strategy_repository_saves_and_lists_by_market() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = StrategyRepository(session)
        repository.save_strategy(_strategy())
        session.commit()

        strategies = repository.list_by_market("us", status="draft")

        assert len(strategies) == 1
        assert strategies[0].strategy_id == "mock-us-momentum-quality-v1"
        assert strategies[0].universe["symbols"] == ["NVDA", "AAPL"]
        assert strategies[0].parameters["live_trading_enabled"] is False


def test_strategy_repository_updates_existing_strategy() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = StrategyRepository(session)
        first = repository.save_strategy(_strategy())
        session.commit()

        updated = repository.save_strategy(_strategy(name="Updated Momentum Draft"))
        session.commit()

        saved_strategy = repository.get_by_strategy_id("mock-us-momentum-quality-v1")

        assert updated.id == first.id
        assert saved_strategy is not None
        assert saved_strategy.name == "Updated Momentum Draft"
        assert len(repository.list_by_market("US")) == 1


def test_strategy_repository_filters_market_status_and_orders_latest_first() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = StrategyRepository(session)
        repository.save_strategy(
            _strategy(
                "strategy-us-old-draft",
                updated_at=datetime(2026, 9, 28, 10, 0),
            )
        )
        repository.save_strategy(
            _strategy(
                "strategy-us-latest-draft",
                updated_at=datetime(2026, 9, 28, 11, 0),
            )
        )
        repository.save_strategy(
            _strategy(
                "strategy-us-confirmed",
                status="confirmed",
                updated_at=datetime(2026, 9, 28, 12, 0),
            )
        )
        repository.save_strategy(
            _strategy(
                "strategy-hk-draft",
                market="HK",
                updated_at=datetime(2026, 9, 28, 13, 0),
            )
        )
        session.commit()

        strategies = repository.list_by_market("us", status="draft")

        assert [strategy.strategy_id for strategy in strategies] == [
            "strategy-us-latest-draft",
            "strategy-us-old-draft",
        ]

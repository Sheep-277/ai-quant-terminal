from datetime import date, datetime
from decimal import Decimal

from app.core.market import MarketCode
from app.db.init_db import init_database
from app.db.repositories.backtest_repository import BacktestRepository
from app.db.session import create_database_engine, create_session_factory
from app.models.backtest import Backtest
from app.services.backtest_read_service import get_backtest_snapshot_by_id, get_latest_backtest_snapshot
from app.services.backtest_write_service import save_backtest_result
from app.services.mock_backtest_service import get_mock_backtest_result


def test_get_latest_backtest_snapshot_reads_saved_result() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    session_factory = create_session_factory(engine)
    response = get_mock_backtest_result(MarketCode.CN)

    with session_factory() as session:
        save_backtest_result(session, response)

        snapshot = get_latest_backtest_snapshot(session, MarketCode.CN)

        assert snapshot is not None
        assert snapshot.source == "database"
        assert snapshot.response.backtest_id == response.backtest_id
        assert snapshot.response.market == MarketCode.CN
        assert snapshot.response.performance.final_value == round(response.performance.final_value, 6)
        assert len(snapshot.response.equity_curve) == len(response.equity_curve)
        assert len(snapshot.response.trades) == len(response.trades)


def test_get_latest_backtest_snapshot_returns_none_without_market_data() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        snapshot = get_latest_backtest_snapshot(session, MarketCode.US)

        assert snapshot is None


def test_get_backtest_snapshot_by_id_reads_saved_result() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    session_factory = create_session_factory(engine)
    response = get_mock_backtest_result(MarketCode.US)

    with session_factory() as session:
        save_backtest_result(session, response)

        snapshot = get_backtest_snapshot_by_id(session, response.backtest_id)

        assert snapshot is not None
        assert snapshot.source == "database"
        assert snapshot.response.strategy_id == response.strategy_id
        assert snapshot.response.currency == response.currency
        assert snapshot.response.trades[0].symbol == response.trades[0].symbol


def test_get_latest_backtest_snapshot_uses_only_current_market_completed_result() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = BacktestRepository(session)
        repository.save_backtest(
            _build_backtest(
                backtest_id="bt-us-old-completed",
                final_value=Decimal("110000.00"),
                updated_at=datetime(2026, 9, 28, 10, 0),
            )
        )
        repository.save_backtest(
            _build_backtest(
                backtest_id="bt-us-latest-completed",
                final_value=Decimal("120000.00"),
                updated_at=datetime(2026, 9, 28, 11, 0),
            )
        )
        repository.save_backtest(
            _build_backtest(
                backtest_id="bt-us-pending",
                final_value=Decimal("130000.00"),
                status="pending",
                updated_at=datetime(2026, 9, 28, 12, 0),
            )
        )
        repository.save_backtest(
            _build_backtest(
                backtest_id="bt-hk-completed",
                market="HK",
                final_value=Decimal("140000.00"),
                updated_at=datetime(2026, 9, 28, 13, 0),
            )
        )
        session.commit()

        snapshot = get_latest_backtest_snapshot(session, MarketCode.US)

        assert snapshot is not None
        assert snapshot.response.backtest_id == "bt-us-latest-completed"
        assert snapshot.response.market == MarketCode.US
        assert snapshot.response.status == "completed"
        assert snapshot.response.performance.final_value == 120000.0


def _build_backtest(
    *,
    backtest_id: str,
    final_value: Decimal,
    market: str = "US",
    status: str = "completed",
    updated_at: datetime,
) -> Backtest:
    """构造只读服务测试所需的回测主记录。"""

    return Backtest(
        backtest_id=backtest_id,
        strategy_id="strategy-us-001",
        market=market,
        status=status,
        data_mode="mock",
        timezone="America/New_York",
        currency="USD",
        benchmark="S&P 500",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        initial_capital=Decimal("100000.00"),
        final_value=final_value,
        total_return=Decimal("0.18"),
        annualized_return=Decimal("0.18"),
        benchmark_return=Decimal("0.09"),
        maximum_drawdown=Decimal("0.03"),
        sharpe_ratio=Decimal("1.60"),
        win_rate=Decimal("1.00"),
        trade_count=1,
        assumptions=["Mock 回测结果。"],
        source="test",
        updated_at=updated_at,
    )

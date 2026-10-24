from datetime import date, datetime
from decimal import Decimal

from app.db.init_db import init_database
from app.db.repositories.backtest_repository import BacktestRepository
from app.db.session import create_database_engine, create_session_factory
from app.models.backtest import Backtest, BacktestTrade, EquityCurvePoint


def test_backtest_repository_saves_and_reads_result_parts() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = BacktestRepository(session)
        backtest = repository.save_backtest(_build_backtest(final_value=Decimal("118000.00")))
        session.flush()
        repository.replace_equity_curve(
            backtest,
            [
                _build_equity_point(datetime(2026, 1, 1, 9, 30), Decimal("100000.00")),
                _build_equity_point(datetime(2026, 1, 2, 9, 30), Decimal("118000.00")),
            ],
        )
        repository.replace_trades(backtest, [_build_trade(datetime(2026, 1, 1, 9, 30))])
        session.commit()

        saved_backtest = repository.get_by_backtest_id("bt-us-001")
        market_backtests = repository.list_by_market("us", status="completed")
        equity_curve = repository.list_equity_curve("bt-us-001")
        trades = repository.list_trades("bt-us-001")

        assert saved_backtest is not None
        assert saved_backtest.final_value == Decimal("118000.000000")
        assert [item.backtest_id for item in market_backtests] == ["bt-us-001"]
        assert [point.equity for point in equity_curve] == [Decimal("100000.000000"), Decimal("118000.000000")]
        assert len(trades) == 1
        assert trades[0].symbol == "NVDA"


def test_backtest_repository_updates_existing_result_and_replaces_children() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = BacktestRepository(session)
        backtest = repository.save_backtest(_build_backtest(final_value=Decimal("118000.00")))
        session.flush()
        repository.replace_equity_curve(backtest, [_build_equity_point(datetime(2026, 1, 1, 9, 30), Decimal("100000.00"))])
        repository.replace_trades(backtest, [_build_trade(datetime(2026, 1, 1, 9, 30))])
        session.commit()

        updated_backtest = repository.save_backtest(_build_backtest(final_value=Decimal("121000.00")))
        session.flush()
        repository.replace_equity_curve(updated_backtest, [_build_equity_point(datetime(2026, 1, 2, 9, 30), Decimal("121000.00"))])
        repository.replace_trades(updated_backtest, [])
        session.commit()

        saved_backtest = repository.get_by_backtest_id("bt-us-001")
        equity_curve = repository.list_equity_curve("bt-us-001")
        trades = repository.list_trades("bt-us-001")

        assert saved_backtest is not None
        assert saved_backtest.final_value == Decimal("121000.000000")
        assert [point.equity for point in equity_curve] == [Decimal("121000.000000")]
        assert trades == []


def test_backtest_repository_filters_market_status_and_orders_latest_first() -> None:
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
                final_value=Decimal("140000.00"),
                market="HK",
                updated_at=datetime(2026, 9, 28, 13, 0),
            )
        )
        session.commit()

        backtests = repository.list_by_market("us", status="completed")

        assert [backtest.backtest_id for backtest in backtests] == [
            "bt-us-latest-completed",
            "bt-us-old-completed",
        ]


def _build_backtest(
    *,
    final_value: Decimal,
    backtest_id: str = "bt-us-001",
    market: str = "US",
    status: str = "completed",
    updated_at: datetime | None = None,
) -> Backtest:
    """构造最小合法回测主记录，供 Repository 测试复用。"""

    backtest = Backtest(
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
    )
    if updated_at is not None:
        backtest.updated_at = updated_at
    return backtest


def _build_equity_point(point_timestamp: datetime, equity: Decimal) -> EquityCurvePoint:
    """构造权益曲线点；backtest_pk/backtest_id 由 Repository 写入。"""

    return EquityCurvePoint(
        backtest_pk=0,
        backtest_id="",
        point_timestamp=point_timestamp,
        equity=equity,
        benchmark_equity=Decimal("109000.00"),
        drawdown=Decimal("0.01"),
        source="test",
    )


def _build_trade(trade_timestamp: datetime) -> BacktestTrade:
    """构造回测模拟成交；backtest_pk/backtest_id 由 Repository 写入。"""

    return BacktestTrade(
        backtest_pk=0,
        backtest_id="",
        trade_timestamp=trade_timestamp,
        market="US",
        symbol="NVDA",
        side="buy",
        quantity=10,
        price=Decimal("180.00"),
        fee=Decimal("1.80"),
        slippage=Decimal("0.90"),
        source="test",
    )

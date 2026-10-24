from app.core.market import MarketCode
from app.db.init_db import init_database
from app.db.repositories.backtest_repository import BacktestRepository
from app.db.session import create_database_engine, create_session_factory
from app.services.backtest_write_service import save_backtest_result
from app.services.mock_backtest_service import get_mock_backtest_result


def test_save_backtest_result_persists_response_parts() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    session_factory = create_session_factory(engine)
    response = get_mock_backtest_result(MarketCode.US)

    with session_factory() as session:
        saved_backtest = save_backtest_result(session, response)
        repository = BacktestRepository(session)

        stored_backtest = repository.get_by_backtest_id(response.backtest_id)
        equity_curve = repository.list_equity_curve(response.backtest_id)
        trades = repository.list_trades(response.backtest_id)

        assert saved_backtest.backtest_id == response.backtest_id
        assert stored_backtest is not None
        assert stored_backtest.strategy_id == response.strategy_id
        assert stored_backtest.market == "US"
        assert stored_backtest.source == "mock_result"
        assert len(equity_curve) == len(response.equity_curve)
        assert len(trades) == len(response.trades)
        assert trades[0].symbol == response.trades[0].symbol


def test_save_backtest_result_replaces_children_on_repeat_save() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    session_factory = create_session_factory(engine)
    response = get_mock_backtest_result(MarketCode.HK)

    with session_factory() as session:
        save_backtest_result(session, response)
        save_backtest_result(session, response)
        repository = BacktestRepository(session)

        market_backtests = repository.list_by_market("HK")
        equity_curve = repository.list_equity_curve(response.backtest_id)
        trades = repository.list_trades(response.backtest_id)

        assert len(market_backtests) == 1
        assert len(equity_curve) == len(response.equity_curve)
        assert len(trades) == len(response.trades)

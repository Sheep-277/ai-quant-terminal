from datetime import datetime

from app.db.repositories.ai_research_repository import AIResearchRepository
from app.db.repositories.backtest_repository import BacktestRepository
from app.db.repositories.factor_value_repository import FactorValueRepository
from app.db.repositories.financial_repository import FinancialRepository
from app.db.repositories.latest_quote_repository import LatestQuoteRepository
from app.db.repositories.market_bar_repository import MarketBarRepository
from app.db.repositories.portfolio_repository import PortfolioRepository
from app.db.repositories.signal_repository import SignalRepository
from app.db.repositories.stock_repository import StockRepository
from app.db.repositories.strategy_repository import StrategyRepository
from app.db.repositories.valuation_snapshot_repository import ValuationSnapshotRepository
from app.db.init_db import init_database
from app.db.seed import seed_development_data
from app.db.session import create_database_engine, create_session_factory


def test_seed_development_data_writes_stocks_quotes_and_market_bars() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")

    result = seed_development_data(engine, timestamp=datetime(2026, 9, 28, 10, 30, 0))
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        ai_research_repository = AIResearchRepository(session)
        stock_repository = StockRepository(session)
        backtest_repository = BacktestRepository(session)
        factor_repository = FactorValueRepository(session)
        quote_repository = LatestQuoteRepository(session)
        bar_repository = MarketBarRepository(session)
        financial_repository = FinancialRepository(session)
        portfolio_repository = PortfolioRepository(session)
        signal_repository = SignalRepository(session)
        strategy_repository = StrategyRepository(session)
        valuation_repository = ValuationSnapshotRepository(session)

        us_stocks = stock_repository.list_by_market("US")
        nvda_quote = quote_repository.get_by_market_symbol("US", "NVDA")
        nvda_bars = bar_repository.list_latest("US", "NVDA", "1d", limit=30)
        nvda_factors = factor_repository.list_latest_by_market_symbol("US", "NVDA")
        nvda_financial = financial_repository.get_latest_by_market_symbol("US", "NVDA")
        nvda_signals = signal_repository.list_latest_by_market_symbol("US", "NVDA")
        us_portfolios = portfolio_repository.list_by_market("US")
        us_positions = portfolio_repository.list_positions("paper-us-001")
        us_orders = portfolio_repository.list_orders("paper-us-001")
        us_trades = portfolio_repository.list_trades("paper-us-001")
        us_strategies = strategy_repository.list_by_market("US", status="draft")
        nvda_valuation = valuation_repository.get_latest_by_market_symbol("US", "NVDA")
        us_backtests = backtest_repository.list_by_market("US", status="completed")
        us_equity_curve = backtest_repository.list_equity_curve("mock-us-backtest-001")
        us_backtest_trades = backtest_repository.list_trades("mock-us-backtest-001")
        us_ai_tasks = ai_research_repository.list_tasks_by_market("US")
        us_ai_evidence = ai_research_repository.list_evidence("research-us-nvda-queued")

        assert result == {
            "stocks": 6,
            "latest_quotes": 6,
            "market_bars": 180,
            "financials": 6,
            "valuation_snapshots": 6,
            "factor_values": 30,
            "signals": 13,
            "strategies": 3,
            "portfolios": 3,
            "backtests": 3,
            "agent_tasks": 3,
        }
        assert [stock.symbol for stock in us_stocks] == ["AAPL", "NVDA"]
        assert nvda_quote is not None
        assert nvda_quote.source == "mock_seed"
        assert nvda_quote.data_status == "realtime"
        assert len(nvda_bars) == 30
        assert nvda_bars[-1].source == "mock_seed"
        nvda_closes = [float(bar.close_price) for bar in nvda_bars]
        nvda_close_diffs = [round(nvda_closes[index] - nvda_closes[index - 1], 2) for index in range(1, len(nvda_closes))]
        assert len(set(nvda_closes)) > 10
        assert max(nvda_close_diffs) > 1
        assert min(nvda_close_diffs) < 0
        assert len(nvda_factors) == 5
        assert {factor.factor_name for factor in nvda_factors} == {
            "composite_score",
            "momentum_20d",
            "quality_score",
            "trend_strength",
            "volatility_20d",
        }
        assert nvda_financial is not None
        assert nvda_financial.roe is not None
        assert nvda_financial.source == "mock_seed"
        assert nvda_signals
        assert nvda_signals[0].source == "mock_seed"
        assert len(us_portfolios) == 1
        assert us_portfolios[0].account_id == "paper-us-001"
        assert len(us_positions) == 3
        assert len(us_orders) == 2
        assert len(us_trades) == 2
        assert len(us_strategies) == 1
        assert us_strategies[0].strategy_id == "mock-us-momentum-quality-v1"
        assert us_strategies[0].parameters["data_mode"] == "mock"
        assert nvda_valuation is not None
        assert nvda_valuation.pe_ttm is not None
        assert nvda_valuation.source == "mock_seed"
        assert len(us_backtests) == 1
        assert us_backtests[0].backtest_id == "mock-us-backtest-001"
        assert us_backtests[0].strategy_id == "mock-us-momentum-quality-v1"
        assert len(us_equity_curve) == 12
        assert len(us_backtest_trades) == 2
        assert len(us_ai_tasks) == 1
        assert us_ai_tasks[0].task_id == "research-us-nvda-queued"
        assert us_ai_tasks[0].query == "分析 NVDA 今天异动原因"
        assert us_ai_tasks[0].result_snapshot is not None
        assert us_ai_evidence


def test_init_database_creates_backtest_tables() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")

    table_names = set(init_database(engine))

    assert {"backtests", "equity_curve_points", "backtest_trades"}.issubset(table_names)


def test_init_database_creates_portfolio_tables() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")

    table_names = set(init_database(engine))

    assert {"portfolios", "positions", "orders", "trades"}.issubset(table_names)


def test_seed_development_data_is_repeatable_for_existing_stocks() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")

    first_result = seed_development_data(engine, timestamp=datetime(2026, 9, 28, 10, 30, 0))
    second_result = seed_development_data(engine, timestamp=datetime(2026, 9, 28, 10, 35, 0))
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        ai_research_repository = AIResearchRepository(session)
        stock_repository = StockRepository(session)
        backtest_repository = BacktestRepository(session)
        factor_repository = FactorValueRepository(session)
        quote_repository = LatestQuoteRepository(session)
        bar_repository = MarketBarRepository(session)
        financial_repository = FinancialRepository(session)
        portfolio_repository = PortfolioRepository(session)
        signal_repository = SignalRepository(session)
        strategy_repository = StrategyRepository(session)
        valuation_repository = ValuationSnapshotRepository(session)

        all_us_stocks = stock_repository.list_by_market("US", active_only=False)
        all_us_quotes = quote_repository.list_by_market("US")
        nvda_bars = bar_repository.list_latest("US", "NVDA", "1d", limit=100)
        nvda_factors = factor_repository.list_latest_by_market_symbol("US", "NVDA")
        nvda_momentum_history = factor_repository.list_history("US", "NVDA", "momentum_20d", limit=10)
        nvda_financials = financial_repository.list_by_market_symbol("US", "NVDA", limit=10)
        nvda_signals = signal_repository.list_latest_by_market_symbol("US", "NVDA", limit=10)
        us_portfolios = portfolio_repository.list_by_market("US")
        us_positions = portfolio_repository.list_positions("paper-us-001")
        us_orders = portfolio_repository.list_orders("paper-us-001")
        us_trades = portfolio_repository.list_trades("paper-us-001")
        us_strategies = strategy_repository.list_by_market("US", status="draft")
        nvda_valuations = valuation_repository.list_by_market_symbol("US", "NVDA", limit=10)
        us_backtests = backtest_repository.list_by_market("US", status="completed")
        us_equity_curve = backtest_repository.list_equity_curve("mock-us-backtest-001")
        us_backtest_trades = backtest_repository.list_trades("mock-us-backtest-001")
        us_ai_tasks = ai_research_repository.list_tasks_by_market("US")
        us_ai_evidence = ai_research_repository.list_evidence("research-us-nvda-queued")

        assert first_result == {
            "stocks": 6,
            "latest_quotes": 6,
            "market_bars": 180,
            "financials": 6,
            "valuation_snapshots": 6,
            "factor_values": 30,
            "signals": 13,
            "strategies": 3,
            "portfolios": 3,
            "backtests": 3,
            "agent_tasks": 3,
        }
        assert second_result == {
            "stocks": 6,
            "latest_quotes": 6,
            "market_bars": 0,
            "financials": 6,
            "valuation_snapshots": 6,
            "factor_values": 30,
            "signals": 13,
            "strategies": 3,
            "portfolios": 3,
            "backtests": 3,
            "agent_tasks": 3,
        }
        assert len(all_us_stocks) == 2
        assert len(all_us_quotes) == 2
        assert len(nvda_bars) == 30
        assert len(nvda_factors) == 5
        assert len(nvda_momentum_history) == 1
        assert len(nvda_financials) == 1
        assert len(nvda_signals) >= 2
        assert len(us_portfolios) == 1
        assert len(us_positions) == 3
        assert len(us_orders) == 2
        assert len(us_trades) == 2
        assert len(us_strategies) == 1
        assert len(nvda_valuations) == 2
        assert len(us_backtests) == 1
        assert len(us_equity_curve) == 12
        assert len(us_backtest_trades) == 2
        assert len(us_ai_tasks) == 1
        assert us_ai_evidence
        assert {quote.quote_timestamp.minute for quote in all_us_quotes} == {35}

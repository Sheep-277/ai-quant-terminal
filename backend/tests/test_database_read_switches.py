from datetime import datetime

from app.api.v1.ai_research import build_ai_research_task_response
from app.api.v1.backtest import build_backtest_result_response
from app.api.v1.market import build_market_overview_response
from app.api.v1.monitor import build_monitor_stream_response
from app.api.v1.portfolio import build_portfolio_summary_response
from app.api.v1.stock import build_stock_research_response
from app.api.v1.strategy import build_strategy_lab_response
from app.core.config import Settings, get_settings
from app.core.market import MarketCode
from app.db.seed import seed_development_data
from app.db.session import create_database_engine, get_engine, get_session_factory
from app.schemas.stock import StockResearchQuery


def test_seeded_database_read_switches_cover_main_terminal_modules(monkeypatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    seed_development_data(engine, timestamp=datetime(2026, 9, 28, 10, 30, 0))
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_settings.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)
    settings = Settings(
        DATABASE_URL=database_url,
        ENABLE_MARKET_DATABASE_READS=True,
        ENABLE_STOCK_DATABASE_READS=True,
        ENABLE_AI_RESEARCH_DATABASE_READS=True,
        ENABLE_STRATEGY_DATABASE_READS=True,
        ENABLE_BACKTEST_DATABASE_READS=True,
        ENABLE_PORTFOLIO_DATABASE_READS=True,
        ENABLE_MONITOR_DATABASE_READS=True,
        _env_file=None,
    )

    market = build_market_overview_response(MarketCode.US, settings)
    stock = build_stock_research_response(
        StockResearchQuery(market=MarketCode.US, symbol="NVDA"),
        settings,
    )
    ai_research = build_ai_research_task_response(MarketCode.US, settings)
    strategy = build_strategy_lab_response(MarketCode.US, settings)
    backtest = build_backtest_result_response(MarketCode.US, settings)
    portfolio = build_portfolio_summary_response(MarketCode.US, settings)
    monitor = build_monitor_stream_response(MarketCode.US, settings)

    assert market.events[0].source == "DATABASE"
    assert {index.symbol for index in market.indices} == {"SPX", "NDX", "VIX"}

    assert stock.profile.symbol == "NVDA"
    assert stock.quote_data_source.source == "database"
    assert stock.kline_data_source.source == "database"
    assert stock.fundamental_data_status.source == "database"
    assert stock.factor_data_status.source == "database"
    assert stock.signal_data_status.source == "database"

    assert ai_research.task_id == "research-us-nvda-queued"
    assert ai_research.query == "分析 NVDA 今天异动原因"
    assert ai_research.evidence
    assert ai_research.result.headline

    assert strategy.drafts[0].strategy_id == "mock-us-momentum-quality-v1"
    assert strategy.drafts[0].parameters["data_mode"] == "mock"

    assert backtest.backtest_id == "mock-us-backtest-001"
    assert len(backtest.equity_curve) == 12
    assert len(backtest.trades) == 2

    assert portfolio.account.account_id == "paper-us-001"
    assert len(portfolio.positions) == 3
    assert len(portfolio.orders) == 2

    assert monitor.signals
    assert monitor.signals[0].signal_id.startswith("db-signal-")
    assert any(event.event_id == "event-us-db-signals" for event in monitor.events)

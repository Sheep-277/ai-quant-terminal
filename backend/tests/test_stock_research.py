from collections.abc import Generator, Iterator
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.stock import build_stock_research_response
from app.core.config import Settings, get_settings
from app.core.market import MarketCode
from app.db.repositories.financial_repository import FinancialRepository
from app.db.repositories.factor_value_repository import FactorValueRepository
from app.db.repositories.signal_repository import SignalRepository
from app.db.repositories.stock_repository import StockRepository
from app.db.repositories.valuation_snapshot_repository import ValuationSnapshotRepository
from app.db.seed import seed_development_data
from app.db.session import Base, create_database_engine, create_session_factory, get_engine, get_session_factory
from app.main import app
from app.models.financial import Financial
from app.models.latest_quote import LatestQuote
from app.models.market_bar import MarketBar
from app.models.stock import Stock
from app.models.valuation_snapshot import ValuationSnapshot
from app.providers.factory import get_market_data_provider
from app.providers.market_data import MockMarketDataProvider
from app.providers.provider_status_check import build_provider_status_report
from app.providers.real_market_data import RealMarketDataProvider
from app.schemas.stock import (
    CashFlowMetrics,
    ProfitabilityMetrics,
    StockFactorSnapshot,
    StockResearchQuery,
    StockResearchResponse,
    ValuationMetrics,
)
from app.services.mock_stock_service import get_mock_stock_research
from app.services.stock_factor_read_service import StockFactorReadSnapshot
from app.services.stock_fundamental_read_service import StockFundamentalReadSnapshot


@pytest.fixture
def stock_api_database(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[Settings, sessionmaker[Session], list[str]]]:
    """替换接口数据库边界，执行真实 Repository 并记录 Session 生命周期。"""

    # TestClient 在工作线程执行同步路由；共用同一条内存库连接才不会得到空库。
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    events: list[str] = []
    settings = Settings(
        DATABASE_URL="sqlite+pysqlite:///:memory:", ENABLE_STOCK_DATABASE_READS=True,
        DATA_PROVIDER="real", REAL_PROVIDER_NAME="YahooFinance",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="", _env_file=None,
    )

    def database_session(_: Settings) -> Generator[Session, None, None]:
        with factory() as session:
            events.append("opened")
            try:
                yield session
            finally:
                events.append("closed")

    monkeypatch.setattr("app.api.v1.stock.get_db_session", database_session)
    try:
        yield settings, factory, events
    finally:
        engine.dispose()


def _save_stock_api_snapshot(session: Session, market: MarketCode, symbol: str) -> None:
    """只写入本场景的个股资料、报价和 K 线，不初始化其他业务演示数据。"""

    stock = Stock(
        market=market.value, symbol=symbol, name="数据库研究标的", exchange="TEST",
        currency={MarketCode.US: "USD", MarketCode.HK: "HKD", MarketCode.CN: "CNY"}[market],
        timezone={MarketCode.US: "America/New_York", MarketCode.HK: "Asia/Hong_Kong", MarketCode.CN: "Asia/Shanghai"}[market],
    )
    session.add(stock)
    session.flush()
    session.add(LatestQuote(
        stock_id=stock.id, market=market.value, symbol=symbol,
        price=Decimal("321.23"), change_amount=Decimal("1.23"),
        change_percent=Decimal("0.00384375"), volume=12345, turnover=Decimal("3965534.85"),
        data_status="delayed", source="test", quote_timestamp=datetime(2026, 9, 28, 10, 30),
    ))
    for index in range(30):
        close = Decimal(100 + index)
        session.add(MarketBar(
            stock_id=stock.id, market=market.value, symbol=symbol, interval_code="1d",
            bar_timestamp=datetime(2026, 9, 28) - timedelta(days=29 - index),
            open_price=close, high_price=close + 1, low_price=close - 1,
            close_price=close, volume=1000, source="test", data_status="delayed",
        ))
    session.commit()


@pytest.mark.parametrize("market", list(MarketCode))
@pytest.mark.parametrize("transport", ["direct", "http"])
@pytest.mark.parametrize("scenario", [
    "database_hit", "database_miss", "quote_failure", "bars_failure",
    "both_failure", "missing_time", "database_disabled",
])
def test_stock_api_read_orchestration(
    monkeypatch: pytest.MonkeyPatch,
    stock_api_database: tuple[Settings, sessionmaker[Session], list[str]],
    market: MarketCode,
    scenario: str,
    transport: str,
) -> None:
    """验证数据库与 Provider 的完整编排结果，而不模拟 Service 或 Repository。"""

    settings, factory, session_events = stock_api_database
    mock = MockMarketDataProvider()
    symbol = mock.get_default_stock_symbol(market)
    provider = RealMarketDataProvider(settings=settings)
    calls = {"quote": 0, "bars": 0}
    quote_failed = scenario in ("quote_failure", "both_failure")
    bars_failed = scenario in ("bars_failure", "both_failure")

    def fetch_quote(request: object) -> dict[str, object] | None:
        calls["quote"] += 1
        if quote_failed:
            return None
        quote: dict[str, object] = dict(mock.get_quote(market, symbol))
        # 区分数据库值、公开报价值与失败回退值，防止只改来源标签也能通过测试。
        quote.update(price=456.78, change=1.0, change_percent=1.0 / 455.78, volume=1000, turnover=456780.0)
        if scenario != "missing_time":
            quote["timestamp"] = "2026-10-16T20:00:00Z"
        return quote

    def fetch_bars(request: object) -> list[dict[str, object]] | None:
        calls["bars"] += 1
        if bars_failed:
            return None
        return [dict(bar) for bar in mock.get_bars(market, symbol, count=40)]

    monkeypatch.setattr(provider, "_fetch_quote_response", fetch_quote)
    monkeypatch.setattr(provider, "_fetch_bars_response", fetch_bars)
    monkeypatch.setattr("app.services.stock_read_service.get_market_data_provider", lambda: provider)
    monkeypatch.setattr("app.services.mock_stock_service.get_market_data_provider", lambda: provider)
    if scenario == "database_hit":
        with factory() as session:
            _save_stock_api_snapshot(session, market, symbol)
    if scenario == "database_disabled":
        settings = settings.model_copy(update={"enable_stock_database_reads": False})

    if transport == "http":
        monkeypatch.setattr("app.api.v1.stock.get_settings", lambda: settings)
        with TestClient(app) as http_client:
            http_response = http_client.get("/api/v1/stock/research", params={"market": market.value, "symbol": symbol})
        assert http_response.status_code == 200
        payload = http_response.json()
        response = StockResearchResponse.model_validate(payload)
    else:
        response = build_stock_research_response(StockResearchQuery(market=market, symbol=symbol), settings)
        payload = response.model_dump(mode="json")
    assert StockResearchResponse.model_validate(payload) == response
    assert payload["profile"]["market"] == market.value
    assert payload["profile"]["symbol"] == symbol
    assert len(payload["kline"]["bars"]) == 30
    assert session_events == ([] if scenario == "database_disabled" else ["opened", "closed"])

    if scenario == "database_hit":
        assert calls == {"quote": 0, "bars": 0}
        assert payload["quote"]["price"] == 321.23
        assert payload["quote"]["timestamp"] == "2026-09-28T10:30:00"
        assert payload["quote_data_source"]["source"] == "database"
        assert payload["kline_data_source"]["source"] == "database"
        assert payload["kline"]["bars"][-1]["close"] == 129
    else:
        assert calls == {"quote": 1, "bars": 1}
        assert payload["quote"]["price"] == (mock.get_quote(market, symbol)["price"] if quote_failed else 456.78)
        expected_time = None if quote_failed or scenario == "missing_time" else datetime(2026, 10, 16, 20, tzinfo=timezone.utc)
        assert response.quote.timestamp == expected_time
        assert payload["quote_data_source"]["source"] == ("mock_fallback" if quote_failed else "yahoo_finance")
        assert payload["quote_data_source"]["fallback_active"] is quote_failed
        assert payload["kline_data_source"]["source"] == ("mock_provider" if bars_failed else "yahoo_finance")
    assert payload["quote"]["data_status"] == ("unavailable" if quote_failed else "delayed")
    assert payload["kline_data_source"]["fallback_active"] is bars_failed
    assert payload["kline"]["data_status"] == ("unavailable" if bars_failed else "delayed")
    for source in (payload["technical_data_source"], payload["summary_data_source"]):
        assert source["fallback_active"] is bars_failed
        assert source["data_status"] == payload["kline"]["data_status"]
    assert any("K 线读取已回退" in flag for flag in payload["risk_flags"]) is bars_failed


@pytest.mark.parametrize("transport", ["direct", "http"])
def test_stock_api_closes_session_when_downstream_raises(
    monkeypatch: pytest.MonkeyPatch,
    stock_api_database: tuple[Settings, sessionmaker[Session], list[str]],
    transport: str,
) -> None:
    """下游异常仍需释放接口取得的 Session，不把错误伪装成成功响应。"""

    settings, _, events = stock_api_database

    def fail_read(*args: object) -> None:
        raise RuntimeError("测试读取失败")

    monkeypatch.setattr("app.api.v1.stock.get_stock_read_snapshot", fail_read)
    if transport == "http":
        monkeypatch.setattr("app.api.v1.stock.get_settings", lambda: settings)
        with TestClient(app, raise_server_exceptions=False) as http_client:
            response = http_client.get("/api/v1/stock/research", params={"market": "US", "symbol": "NVDA"})
        assert response.status_code == 500
    else:
        with pytest.raises(RuntimeError, match="测试读取失败"):
            build_stock_research_response(StockResearchQuery(market=MarketCode.US, symbol="NVDA"), settings)
    assert events == ["opened", "closed"]


client = TestClient(app)
market_data_provider = MockMarketDataProvider()


@pytest.fixture(autouse=True)
def disable_stock_database_reads_by_default(monkeypatch: pytest.MonkeyPatch):
    """大多数接口测试验证默认 Mock 行为，避免本地 .env 影响测试结果。"""

    monkeypatch.setenv("DATA_PROVIDER", "mock")
    # 部分旧测试调用开发 seed，连带生成研究任务；不能因此使用本地真实 API Key。
    monkeypatch.setenv("ENABLE_LLM_RESEARCH", "false")
    monkeypatch.setenv("SEARCH_PROVIDER", "mock")
    monkeypatch.setenv("ENABLE_STOCK_DATABASE_READS", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_stock_research_defaults_to_us_stock() -> None:
    # 不传 market 和 symbol 时，接口应返回默认美股研究标的。
    response = client.get("/api/v1/stock/research")

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["market"] == "US"
    assert payload["profile"]["symbol"] == "NVDA"
    assert payload["profile"]["currency"] == "USD"
    assert payload["quote"]["data_status"] == "realtime"
    assert len(payload["kline"]["bars"]) == 30
    assert 0 <= payload["technical"]["rsi_14"] <= 100
    assert payload["technical"]["macd"] is not None
    # 当前页面只有 30 根 K 线，26 日慢线之后还不足 9 个有效样本计算信号线。
    assert payload["technical"]["macd_signal"] is None
    assert payload["technical"]["macd_histogram"] is None
    assert payload["factor_snapshot"]["momentum_20d"] is not None
    assert payload["factor_snapshot"]["composite_score"] is not None
    assert payload["quant_signals"]
    assert payload["quant_signals"][0]["title"]
    assert "20 日动量" in payload["summary_points"][0]
    assert "综合因子评分" in payload["summary_points"][1]
    assert payload["technical_data_source"]["source"] == "quant_pipeline"
    assert payload["technical_data_source"]["fallback_active"] is False
    assert payload["technical_data_source"]["data_status"] == "realtime"
    assert payload["summary_data_source"]["source"] == "quant_pipeline"
    assert payload["summary_data_source"]["fallback_active"] is False
    assert payload["summary_data_source"]["data_status"] == "realtime"


def test_mock_market_data_provider_covers_stock_research_markets() -> None:
    # Provider 层必须覆盖 V1 的三个市场，service 层才不需要自己维护数据源分支。
    for market in (MarketCode.US, MarketCode.HK, MarketCode.CN):
        default_symbol = market_data_provider.get_default_stock_symbol(market)
        profile = market_data_provider.get_asset_profile(market, default_symbol)
        quote = market_data_provider.get_quote(market, default_symbol)
        financials = market_data_provider.get_financials(market, default_symbol)
        notes = market_data_provider.get_research_notes(market, default_symbol)

        assert default_symbol == profile["symbol"]
        assert quote["price"] > 0
        assert financials["pe_ttm"] > 0
        assert financials["roe_ttm"] > 0
        assert notes["summary_points"]
        assert notes["fallback_symbol"] is None


def test_mock_market_data_provider_exposes_real_provider_contract_shapes() -> None:
    # Mock Provider 也要提供 quote / bars / financials，后续真实 Provider 才能按同一合同替换。
    profile = market_data_provider.get_asset_profile(MarketCode.US, "AAPL")
    quote = market_data_provider.get_quote(MarketCode.US, "AAPL")
    bars = market_data_provider.get_bars(MarketCode.US, "AAPL", count=5)
    financials = market_data_provider.get_financials(MarketCode.US, "AAPL")
    notes = market_data_provider.get_research_notes(MarketCode.US, "AAPL")

    assert profile["symbol"] == "AAPL"
    assert profile["name"] == "Apple Inc."
    assert profile["exchange"] == "NASDAQ"
    assert quote["price"] == 232.18
    assert quote["data_status"] == "realtime"
    assert len(bars) == 5
    assert bars[0]["offset"] == 4
    assert bars[-1]["offset"] == 0
    assert all(bar["high"] >= bar["low"] for bar in bars)
    assert financials["pe_ttm"] == 31.4
    assert financials["roe_ttm"] == 1.38
    assert notes["direction"] == "neutral"
    assert notes["fallback_symbol"] is None


def test_mock_market_data_provider_generates_visible_kline_swings() -> None:
    # Mock K 线需要有可见波动，方便前端原型演示，而不是在图表里接近一条直线。
    bars = market_data_provider.get_bars(MarketCode.US, "AAPL", count=30)
    closes = [bar["close"] for bar in bars]
    close_diffs = [round(closes[index] - closes[index - 1], 2) for index in range(1, len(closes))]

    assert len(set(closes)) > 10
    assert max(close_diffs) > 1
    assert min(close_diffs) < 0


def test_mock_market_data_provider_reports_symbol_coverage() -> None:
    # service 应通过 Provider 合同判断是否命中标的，而不是比较回退后的 fixture 内容。
    assert market_data_provider.supports_symbol(MarketCode.US, " aapl ") is True
    assert market_data_provider.supports_symbol(MarketCode.HK, "09988.HK") is False


@pytest.mark.parametrize(
    ("market", "symbol"),
    [
        (MarketCode.US, "NVDA"),
        (MarketCode.HK, "00700.HK"),
        (MarketCode.CN, "600519.SH"),
    ],
)
def test_stock_research_marks_demo_provider_market_data_source(
    monkeypatch: pytest.MonkeyPatch,
    market: MarketCode,
    symbol: str,
) -> None:
    # DemoProvider 模式下，三地样例标的的 Quote 和 K 线标签都应显示 demo_provider。
    monkeypatch.setenv("DATA_PROVIDER", "real")
    monkeypatch.setenv("REAL_PROVIDER_NAME", "DemoProvider")
    monkeypatch.setenv("REAL_PROVIDER_BASE_URL", "https://provider.example.test")
    monkeypatch.setenv("REAL_PROVIDER_API_KEY_ENV", "")
    get_settings.cache_clear()

    try:
        response = get_mock_stock_research(market, symbol)

        assert response.profile.market == market
        assert response.profile.symbol == symbol
        assert response.quote_data_source.source == "demo_provider"
        assert response.quote_data_source.detail == "最新行情来自本地 DemoProvider 样例数据"
        assert response.quote_data_source.fallback_active is False
        assert response.quote_data_source.data_status == "delayed"
        assert response.kline_data_source.source == "demo_provider"
        assert response.kline_data_source.detail == "K 线来自本地 DemoProvider 样例数据"
        assert response.kline_data_source.fallback_active is False
        assert response.kline_data_source.data_status == "delayed"
        assert response.technical_data_source is not None
        assert response.technical_data_source.source == "quant_pipeline"
        assert response.technical_data_source.fallback_active is False
        assert response.technical_data_source.data_status == "delayed"
        assert response.summary_data_source is not None
        assert response.summary_data_source.source == "quant_pipeline"
        assert response.summary_data_source.fallback_active is False
        assert response.summary_data_source.data_status == "delayed"
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize(
    ("market", "symbol"),
    [
        ("US", "NVDA"),
        ("HK", "00700.HK"),
        ("CN", "600519.SH"),
    ],
)
def test_stock_research_response_json_marks_demo_provider_market_data_source(
    monkeypatch: pytest.MonkeyPatch,
    market: str,
    symbol: str,
) -> None:
    # 路由响应模型序列化给前端的 JSON 也必须保留 demo_provider 数据来源字段。
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="",
        ENABLE_STOCK_DATABASE_READS=False,
        _env_file=None,
    )
    # Service 通过 Provider 工厂取数，不能只给响应构造函数传入 Demo 配置。
    provider = get_market_data_provider(settings)
    monkeypatch.setattr("app.services.mock_stock_service.get_market_data_provider", lambda: provider)
    response = build_stock_research_response(
        StockResearchQuery(market=MarketCode(market), symbol=symbol), settings,
    )
    payload = response.model_dump(mode="json")

    assert payload["profile"]["market"] == market
    assert payload["profile"]["symbol"] == symbol
    assert payload["quote_data_source"]["source"] == "demo_provider"
    assert payload["quote_data_source"]["detail"] == "最新行情来自本地 DemoProvider 样例数据"
    assert payload["quote_data_source"]["fallback_active"] is False
    assert payload["quote_data_source"]["data_status"] == "delayed"
    assert payload["kline_data_source"]["source"] == "demo_provider"
    assert payload["kline_data_source"]["detail"] == "K 线来自本地 DemoProvider 样例数据"
    assert payload["kline_data_source"]["fallback_active"] is False
    assert payload["kline_data_source"]["data_status"] == "delayed"


def test_stock_research_demo_provider_matches_provider_quick_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    # Provider 检查命令列出的个股研究路径，应都能生成 demo_provider 数据源响应。
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="",
        ENABLE_STOCK_DATABASE_READS=False,
        _env_file=None,
    )
    report = build_provider_status_report(settings)
    provider = get_market_data_provider(settings)
    monkeypatch.setattr("app.services.mock_stock_service.get_market_data_provider", lambda: provider)
    stock_checks = [
        check
        for check in report["quick_checks"]
        if check["path"].startswith(f"{settings.api_prefix}/stock/research")
    ]

    assert [check["path"] for check in stock_checks] == [
        "/api/v1/stock/research?market=US&symbol=NVDA",
        "/api/v1/stock/research?market=HK&symbol=00700.HK",
        "/api/v1/stock/research?market=CN&symbol=600519.SH",
    ]

    for check in stock_checks:
        query = parse_qs(urlparse(check["path"]).query)
        market = query["market"][0]
        symbol = query["symbol"][0]
        response = build_stock_research_response(
            StockResearchQuery(market=MarketCode(market), symbol=symbol),
            settings,
        )
        payload = response.model_dump(mode="json")

        assert payload["profile"]["market"] == market
        assert payload["profile"]["symbol"] == symbol
        assert payload["quote_data_source"]["source"] == "demo_provider"
        assert payload["kline_data_source"]["source"] == "demo_provider"
        assert payload["quote_data_source"]["fallback_active"] is False
        assert payload["kline_data_source"]["fallback_active"] is False


def test_stock_research_supports_all_v1_markets() -> None:
    # 个股研究必须和全局市场切换保持一致，覆盖 US / HK / CN。
    expected = {
        "US": "USD",
        "HK": "HKD",
        "CN": "CNY",
    }

    for market, currency in expected.items():
        response = client.get("/api/v1/stock/research", params={"market": market})

        assert response.status_code == 200
        payload = response.json()
        assert payload["profile"]["market"] == market
        assert payload["profile"]["currency"] == currency
        assert payload["quote"]["price"] > 0
        assert payload["valuation"]
        assert payload["fundamental_data_status"]["source"] == "mock_provider"
        assert payload["fundamental_data_status"]["completeness"] == "mock"
        assert payload["technical"]
        assert payload["technical"]["rsi_14"] is not None
        assert payload["summary_points"]
        assert payload["direction"] in {"positive", "neutral", "negative"}
        assert payload["factor_snapshot"]["quality_score"] is not None
        assert payload["factor_data_status"]["source"] == "quant_pipeline"
        assert payload["factor_data_status"]["completeness"] == "computed"
        assert payload["signal_data_status"]["source"] == "quant_pipeline"
        assert payload["signal_data_status"]["completeness"] == "computed"
        assert payload["signal_data_status"]["signal_count"] == len(payload["quant_signals"])
        assert all(signal["direction"] in {"positive", "neutral", "negative", "warning"} for signal in payload["quant_signals"])


def test_stock_research_keeps_requested_symbol() -> None:
    # 命中 Mock 股票池时，接口应返回对应标的的资料和行情，而不是只替换 symbol 文本。
    response = client.get("/api/v1/stock/research", params={"market": "US", "symbol": " aapl "})

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["market"] == "US"
    assert payload["profile"]["symbol"] == "AAPL"
    assert payload["profile"]["name"] == "Apple Inc."
    assert payload["profile"]["exchange"] == market_data_provider.get_asset_profile(MarketCode.US, "AAPL")["exchange"]
    assert payload["quote"]["price"] == 232.18
    assert payload["valuation"]["pe_ttm"] == 31.4
    assert payload["kline"]["bars"][-1]["close"] == market_data_provider.get_bars(MarketCode.US, "AAPL", count=40)[-1]["close"]


def test_stock_research_falls_back_to_market_fixture_for_unknown_symbol() -> None:
    # 未命中 Mock 股票池时，当前阶段保留用户输入的 symbol，但基础数据回退到该市场默认 fixture。
    response = client.get("/api/v1/stock/research", params={"market": "HK", "symbol": "09988.HK"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["market"] == "HK"
    assert payload["profile"]["symbol"] == "09988.HK"
    assert payload["profile"]["name"] == "Tencent Holdings Ltd."
    assert market_data_provider.get_research_notes(MarketCode.HK, "09988.HK")["fallback_symbol"] == "00700.HK"
    assert "09988.HK 暂未覆盖 Mock 数据" in payload["risk_flags"][0]
    assert "使用 00700.HK 的示例数据" in payload["summary_points"][2]


def test_stock_research_rejects_unknown_market() -> None:
    # 未支持市场必须返回参数校验错误，避免业务层隐式猜测市场。
    response = client.get("/api/v1/stock/research", params={"market": "EU"})

    assert response.status_code == 422


def test_stock_research_rejects_invalid_symbol() -> None:
    # symbol 校验应在 schema 层完成，避免非法代码进入 service 或 Provider。
    empty_response = client.get("/api/v1/stock/research", params={"market": "US", "symbol": " "})
    unsupported_response = client.get("/api/v1/stock/research", params={"market": "US", "symbol": "NVDA/USD"})

    assert empty_response.status_code == 422
    assert unsupported_response.status_code == 422


def test_stock_research_can_use_database_profile_and_quote(monkeypatch) -> None:
    # 开启数据库读取时，profile、quote、K 线、基本面和估值优先来自数据库。
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    seeded_at = datetime(2026, 9, 28, 10, 30, 0)
    seed_development_data(engine, timestamp=seeded_at)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        stock = StockRepository(session).get_by_market_symbol("US", "NVDA")
        assert stock is not None
        factor_values = FactorValueRepository(session).list_latest_by_market_symbol("US", "NVDA")
        assert factor_values
        stored_signals = SignalRepository(session).list_latest_by_market_symbol("US", "NVDA")
        assert stored_signals
        FinancialRepository(session).save_period(
            Financial(
                stock_id=stock.id,
                market="US",
                symbol="NVDA",
                fiscal_period="TTM",
                period_end_date=date(2026, 9, 30),
                revenue=Decimal("130500000000.0000"),
                net_income=Decimal("72880000000.0000"),
                gross_margin=Decimal("0.70000000"),
                operating_margin=Decimal("0.52000000"),
                roe=Decimal("0.55000000"),
                roic=Decimal("0.41000000"),
                operating_cash_flow=Decimal("15000000000.0000"),
                capex=Decimal("2700000000.0000"),
                fcf=Decimal("12300000000.0000"),
                source="test",
            )
        )
        ValuationSnapshotRepository(session).save_snapshot(
            ValuationSnapshot(
                stock_id=stock.id,
                market="US",
                symbol="NVDA",
                pe_ttm=Decimal("40.100000"),
                pb=Decimal("20.200000"),
                ps_ttm=Decimal("15.300000"),
                pfcf_ttm=Decimal("33.400000"),
                snapshot_timestamp=seeded_at,
                source="test",
            )
        )
        session.commit()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)

    response = build_stock_research_response(
        StockResearchQuery(market=MarketCode.US, symbol="NVDA"),
        Settings(
            DATABASE_URL=database_url,
            ENABLE_STOCK_DATABASE_READS=True,
            _env_file=None,
        ),
    )

    assert response.profile.symbol == "NVDA"
    assert response.profile.name == "NVIDIA Corporation"
    assert response.quote.price == 181.42
    assert response.quote.data_status == "realtime"
    assert response.valuation.pe_ttm == 40.1
    assert response.valuation.pb == 20.2
    assert response.profitability.roe_ttm == 0.55
    assert response.cash_flow.fcf_ttm == 12300000000.0
    assert response.fundamental_data_status.source == "database"
    assert response.fundamental_data_status.completeness == "complete"
    assert response.fundamental_data_status.available_sections == ["valuation", "profitability", "cash_flow"]
    assert response.fundamental_data_status.missing_sections == []
    assert response.factor_snapshot.momentum_20d == next(
        float(factor.factor_value)
        for factor in factor_values
        if factor.factor_name == "momentum_20d"
    )
    assert response.factor_snapshot.composite_score == next(
        float(factor.factor_value)
        for factor in factor_values
        if factor.factor_name == "composite_score"
    )
    assert response.factor_data_status.source == "database"
    assert response.factor_data_status.completeness == "complete"
    assert response.factor_data_status.available_factors == [
        "momentum_20d",
        "trend_strength",
        "volatility_20d",
        "quality_score",
        "composite_score",
    ]
    assert response.factor_data_status.missing_factors == []
    assert response.quant_signals
    assert response.quant_signals[0].code == stored_signals[0].signal_type
    assert response.quant_signals[0].score == stored_signals[0].score
    assert response.quant_signals[0].evidence == stored_signals[0].evidence
    assert response.signal_data_status.source == "database"
    assert response.signal_data_status.completeness == "complete"
    assert response.signal_data_status.signal_count == len(stored_signals)
    assert len(response.kline.bars) == 30
    assert response.kline.bars[-1].timestamp == datetime(2026, 9, 28, 0, 0, 0)


def test_stock_research_can_use_database_fundamental_snapshot() -> None:
    # Service 层收到数据库基本面快照时，估值、盈利能力和现金流展示应覆盖 Mock Provider。
    response = get_mock_stock_research(
        MarketCode.US,
        "NVDA",
        fundamental_read_snapshot=StockFundamentalReadSnapshot(
            valuation=ValuationMetrics(
                pe_ttm=40.1,
                pb=20.2,
                ps_ttm=15.3,
                pfcf_ttm=33.4,
            ),
            profitability=ProfitabilityMetrics(
                roe_ttm=0.55,
                roic_ttm=0.41,
                gross_margin_ttm=0.7,
                operating_margin_ttm=0.52,
            ),
            cash_flow=CashFlowMetrics(
                fcf_ttm=12300000000.0,
                operating_cash_flow_ttm=15000000000.0,
                capex_ttm=2700000000.0,
            ),
            source="database",
            completeness="complete",
            available_sections=("valuation", "profitability", "cash_flow"),
            missing_sections=(),
        ),
    )

    assert response.valuation.pe_ttm == 40.1
    assert response.valuation.pb == 20.2
    assert response.profitability.roe_ttm == 0.55
    assert response.profitability.gross_margin_ttm == 0.7
    assert response.cash_flow.fcf_ttm == 12300000000.0
    assert response.fundamental_data_status.source == "database"
    assert response.fundamental_data_status.completeness == "complete"
    assert response.factor_snapshot.quality_score is not None


def test_stock_research_can_use_database_factor_snapshot() -> None:
    # Service 层收到数据库因子快照时，factor_snapshot 展示应覆盖即时 Quant Pipeline 因子。
    response = get_mock_stock_research(
        MarketCode.US,
        "NVDA",
        factor_read_snapshot=StockFactorReadSnapshot(
            factor_snapshot=StockFactorSnapshot(
                momentum_20d=0.11,
                trend_strength=0.08,
                volatility_20d=0.22,
                quality_score=0.77,
                composite_score=0.66,
            ),
            source="database",
            available_factors=(
                "momentum_20d",
                "trend_strength",
                "volatility_20d",
                "quality_score",
                "composite_score",
            ),
            missing_factors=(),
        ),
    )

    assert response.factor_snapshot.momentum_20d == 0.11
    assert response.factor_snapshot.trend_strength == 0.08
    assert response.factor_snapshot.volatility_20d == 0.22
    assert response.factor_snapshot.quality_score == 0.77
    assert response.factor_snapshot.composite_score == 0.66
    assert response.factor_data_status.source == "database"
    assert response.factor_data_status.completeness == "complete"
    assert response.factor_data_status.available_factors == [
        "momentum_20d",
        "trend_strength",
        "volatility_20d",
        "quality_score",
        "composite_score",
    ]
    assert response.factor_data_status.missing_factors == []

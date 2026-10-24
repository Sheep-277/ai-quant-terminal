"""数据库缺记录后，页面必须保留本次 Provider 报价的真实来源。"""

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.market import MarketCode
from app.db.session import Base, create_database_engine, create_session_factory
from app.providers.base import ProviderQuote
from app.providers.market_data import MockMarketDataProvider
from app.providers.real_market_data import RealMarketDataProvider
from app.schemas.market import DataStatus
from app.services.mock_stock_service import get_mock_stock_research
from app.services.stock_read_service import get_stock_read_snapshot


@pytest.fixture
def session() -> Iterator[Session]:
    """空数据库触发 Provider 读取，不访问用户的 MySQL。"""

    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with create_session_factory(engine)() as session:
        yield session
    engine.dispose()


@pytest.mark.parametrize("market", list(MarketCode))
@pytest.mark.parametrize(
    ("provider_name", "quote_ok", "expected_source", "expected_fallback"),
    [
        ("Mock", True, "mock_provider", False),
        ("YahooFinance", True, "yahoo_finance", False),
        ("YahooFinance", False, "mock_fallback", True),
        ("DemoProvider", True, "demo_provider", False),
        ("DemoProvider", False, "mock_fallback", True),
    ],
)
def test_database_miss_keeps_provider_quote_provenance(
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
    market: MarketCode,
    provider_name: str,
    quote_ok: bool,
    expected_source: str,
    expected_fallback: bool,
) -> None:
    """正常 Mock、Demo、公开报价与实际失败回退使用相同的页面判定规则。"""

    mock = MockMarketDataProvider()
    symbol = mock.get_default_stock_symbol(market)
    provider = mock if provider_name == "Mock" else RealMarketDataProvider(settings=Settings(
        DATA_PROVIDER="real", REAL_PROVIDER_NAME=provider_name,
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="", _env_file=None,
    ))
    if isinstance(provider, RealMarketDataProvider):
        raw_quote = {
            **mock.get_quote(market, symbol),
            "timestamp": datetime(2026, 10, 16, 20, tzinfo=timezone.utc),
        }
        monkeypatch.setattr(provider, "_fetch_quote_response", lambda request: raw_quote if quote_ok else None)
        monkeypatch.setattr(provider, "_fetch_bars_response", lambda request: mock.get_bars(market, symbol, count=40))
    monkeypatch.setattr("app.services.stock_read_service.get_market_data_provider", lambda: provider)
    monkeypatch.setattr("app.services.mock_stock_service.get_market_data_provider", lambda: provider)
    quote_calls: list[tuple[MarketCode, str]] = []
    original_get_quote = provider.get_quote

    def tracked_get_quote(market: MarketCode, symbol: str) -> ProviderQuote:
        quote_calls.append((market, symbol))
        return original_get_quote(market, symbol)

    monkeypatch.setattr(provider, "get_quote", tracked_get_quote)

    snapshot = get_stock_read_snapshot(session, market, symbol)
    assert quote_calls == [(market, symbol)]
    assert snapshot.source == expected_source
    assert snapshot.quote_data_source is not None
    assert snapshot.quote_data_source.fallback_active is expected_fallback
    assert snapshot.quote_data_source.data_status == snapshot.quote.data_status

    direct = get_mock_stock_research(market, symbol)
    assert quote_calls == [(market, symbol), (market, symbol)]
    through_database = get_mock_stock_research(market, symbol, stock_read_snapshot=snapshot)
    assert quote_calls == [(market, symbol), (market, symbol)]
    assert through_database.quote_data_source == direct.quote_data_source
    assert "latest_quotes" not in through_database.quote_data_source.detail
    assert through_database.quote == snapshot.quote
    assert (through_database.quote_data_source.data_status == DataStatus.UNAVAILABLE) is expected_fallback

    # 后续请求失败或配置切回 Mock，不应改写已有价格对应的来源。
    monkeypatch.setattr("app.services.mock_stock_service.get_market_data_provider", lambda: mock)

    def unexpected_quote_read(market: MarketCode, symbol: str) -> ProviderQuote:
        raise AssertionError("已有报价快照，不应再次请求 Provider 报价")

    monkeypatch.setattr(mock, "get_quote", unexpected_quote_read)
    after_provider_change = get_mock_stock_research(market, symbol, stock_read_snapshot=snapshot)
    assert after_provider_change.quote_data_source == through_database.quote_data_source
    assert after_provider_change.quote == snapshot.quote

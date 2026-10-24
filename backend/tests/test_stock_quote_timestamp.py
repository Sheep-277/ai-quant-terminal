"""验证供应商报价时间经过归一化与个股服务后不会变成读取时间。"""

from datetime import datetime, timezone

import pytest

from app.core.config import Settings
from app.core.exceptions import ProviderResponseError
from app.core.market import MarketCode
from app.providers.base import ProviderQuote
from app.providers.market_data import MockMarketDataProvider
from app.providers.real_market_data import RealMarketDataProvider
from app.services.mock_stock_service import get_mock_stock_research
from app.services.stock_read_service import StockReadSnapshot, _get_mock_stock_read_snapshot


@pytest.fixture
def provider() -> RealMarketDataProvider:
    """仅归一化本地输入，不读取 .env、不访问供应商网络。"""

    return RealMarketDataProvider(settings=Settings(_env_file=None))


@pytest.mark.parametrize("timestamp", [
    "2026-10-16T20:00:00Z",
    "2026-10-17T04:00:00+08:00",
    datetime(2026, 10, 16, 20, tzinfo=timezone.utc),
])
def test_quote_time_survives_normalization_and_repeated_research_reads(
    monkeypatch: pytest.MonkeyPatch,
    provider: RealMarketDataProvider,
    timestamp: str | datetime,
) -> None:
    """相同时刻的 ISO 字符串与 datetime 输入都原样保留其时间含义。"""

    mock = MockMarketDataProvider()
    raw_quote = {**mock.get_quote(MarketCode.US, "NVDA"), "timestamp": timestamp}
    quote = provider.normalize_quote_response(raw_quote)
    expected = datetime(2026, 10, 16, 20, tzinfo=timezone.utc)
    assert quote["timestamp"] == expected
    monkeypatch.setattr(mock, "get_quote", lambda *args: quote)
    monkeypatch.setattr("app.services.mock_stock_service.get_market_data_provider", lambda: mock)
    monkeypatch.setattr("app.services.stock_read_service.get_market_data_provider", lambda: mock)

    for _ in range(2):
        response = get_mock_stock_research(MarketCode.US, "NVDA")
        assert response.quote.timestamp == expected
        serialized_time = response.model_dump(mode="json")["quote"]["timestamp"]
        assert datetime.fromisoformat(serialized_time.replace("Z", "+00:00")) == expected
        snapshot = _get_mock_stock_read_snapshot(MarketCode.US, "NVDA")
        assert snapshot.quote.timestamp == expected

    # 数据库行情优先级保持不变，不被后来获取的 Provider 报价时间覆盖。
    database_time = datetime(2026, 10, 15, 20, tzinfo=timezone.utc)
    database_snapshot = StockReadSnapshot(
        profile=response.profile,
        quote=response.quote.model_copy(update={"timestamp": database_time}),
        source="database",
    )

    def unexpected_quote_read(market: MarketCode, symbol: str) -> ProviderQuote:
        raise AssertionError("数据库报价已存在，不应补查 Provider 报价")

    monkeypatch.setattr(mock, "get_quote", unexpected_quote_read)
    assert get_mock_stock_research(
        MarketCode.US, "NVDA", stock_read_snapshot=database_snapshot,
    ).quote.timestamp == database_time


@pytest.mark.parametrize("timestamp", ["not-a-date", "2026-10-16T20:00:00", 123, ""])
def test_invalid_or_naive_quote_timestamp_is_rejected(
    provider: RealMarketDataProvider, timestamp: object,
) -> None:
    """不猜测缺失的时区，也不把坏时间替换成当前时间。"""

    quote = MockMarketDataProvider().get_quote(MarketCode.US, "NVDA")
    with pytest.raises(ProviderResponseError, match="报价时间"):
        provider.normalize_quote_response({**quote, "timestamp": timestamp})


def test_legacy_mock_quote_without_timestamp_stays_compatible(
    provider: RealMarketDataProvider,
) -> None:
    """旧样例未携带时间时，Provider 不自行生成虚假的供应商时间。"""

    quote = MockMarketDataProvider().get_quote(MarketCode.US, "NVDA")
    assert "timestamp" not in provider.normalize_quote_response(quote)


@pytest.mark.parametrize("market", list(MarketCode))
def test_missing_quote_time_stays_null_across_both_read_paths(
    monkeypatch: pytest.MonkeyPatch, market: MarketCode,
) -> None:
    """无供应商时间时，两条读取路径及 JSON 都保留空值，K 线仍可展示。"""

    provider = MockMarketDataProvider()
    monkeypatch.setattr("app.services.mock_stock_service.get_market_data_provider", lambda: provider)
    monkeypatch.setattr("app.services.stock_read_service.get_market_data_provider", lambda: provider)
    symbol = provider.get_default_stock_symbol(market)
    snapshot = _get_mock_stock_read_snapshot(market, symbol)
    assert snapshot.quote.timestamp is None

    for read_snapshot in (None, snapshot):
        response = get_mock_stock_research(market, symbol, stock_read_snapshot=read_snapshot)
        assert response.quote.timestamp is None
        assert response.model_dump(mode="json")["quote"]["timestamp"] is None
        assert response.quote.price > 0
        assert len(response.kline.bars) == 30

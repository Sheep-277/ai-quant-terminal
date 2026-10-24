import pytest

from app.core.config import Settings
from app.core.market import MarketCode
from app.providers.demo_quote_adapter import DemoQuoteAdapter
from app.providers.http_quote_fetcher import RealProviderReadRequest
from app.providers.real_market_data import RealMarketDataProvider
from app.schemas.market import DataStatus


def build_request(market: str = "US", symbol: str = "NVDA", **overrides: object) -> RealProviderReadRequest:
    request: RealProviderReadRequest = {
        "provider_name": "DemoProvider",
        "method": "GET",
        "url": "https://provider.example.test/quotes/US/NVDA",
        "market": market,
        "symbol": symbol,
        "api_key_env": "DEMO_PROVIDER_API_KEY",
        "api_key_configured": False,
        "missing_configuration": [],
    }
    request.update(overrides)
    return request


def test_demo_quote_adapter_returns_sample_quote_without_network() -> None:
    # demo adapter 只演示字段映射，不读取密钥、不访问外部网络。
    adapter = DemoQuoteAdapter()

    quote = adapter.fetch_quote(build_request())

    assert quote == {
        "lastPrice": "182.50",
        "priceChange": "1.50",
        "changeRate": "0.00829",
        "tradeVolume": "1000",
        "turnoverValue": "182500",
    }


def test_demo_quote_adapter_returns_none_for_unknown_symbol() -> None:
    # 未覆盖标的返回 None，让 RealMarketDataProvider 按既有规则回退 Mock。
    adapter = DemoQuoteAdapter()

    assert adapter.fetch_quote(build_request(symbol="UNKNOWN")) is None


def test_demo_quote_adapter_returns_sample_bars_without_network() -> None:
    # demo adapter 的 K 线样例模拟真实供应商常见包装结构，用于验证 Provider 解包路径。
    adapter = DemoQuoteAdapter()

    bars = adapter.fetch_json(build_request(url="https://provider.example.test/bars/US/NVDA"))

    assert bars == {
        "data": {
            "bars": [
                {"o": "180.00", "h": "183.00", "l": "179.50", "c": "182.50", "v": "1000"},
                {"o": "182.50", "h": "184.20", "l": "181.80", "c": "183.75", "v": "1200"},
            ]
        }
    }


def test_demo_quote_adapter_can_drive_real_provider_quote_normalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 端到端验证：供应商风格字段可以被真实 Provider 转成项目统一 ProviderQuote。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="DEMO_PROVIDER_API_KEY",
        _env_file=None,
    )
    provider = RealMarketDataProvider(settings=settings, quote_fetcher=DemoQuoteAdapter())

    quote = provider.get_quote(MarketCode.US, "NVDA")

    assert quote == {
        "price": 182.5,
        "change": 1.5,
        "change_percent": 0.00829,
        "volume": 1000,
        "turnover": 182500.0,
        "data_status": DataStatus.DELAYED,
    }


def test_demo_quote_adapter_can_drive_real_provider_bars_normalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 端到端验证：demo K 线样例可以被真实 Provider 转成项目统一 ProviderBar。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="DEMO_PROVIDER_API_KEY",
        _env_file=None,
    )
    provider = RealMarketDataProvider(settings=settings, quote_fetcher=DemoQuoteAdapter())

    bars = provider.get_bars(MarketCode.US, "NVDA", count=2)

    assert bars == [
        {
            "offset": 1,
            "open": 180.0,
            "high": 183.0,
            "low": 179.5,
            "close": 182.5,
            "volume": 1000,
        },
        {
            "offset": 0,
            "open": 182.5,
            "high": 184.2,
            "low": 181.8,
            "close": 183.75,
            "volume": 1200,
        },
    ]

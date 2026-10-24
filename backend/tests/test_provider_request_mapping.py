from datetime import date

from app.core.config import Settings
from app.core.market import MarketCode
from app.providers.request_mapping import (
    DEFAULT_REQUEST_MAPPING,
    ProviderRequestMapping,
    get_provider_request_mapping,
)
from app.providers.real_market_data import RealMarketDataProvider


def test_provider_request_mapping_returns_default_for_unknown_provider() -> None:
    # 未建立专属路径的供应商先使用通用 Quote/K 线路径，避免接入初期改 Provider 主流程。
    mapping = get_provider_request_mapping("VendorHttpProvider")

    assert mapping is DEFAULT_REQUEST_MAPPING
    assert mapping.quote_path_template == "/quotes/{market}/{symbol}"
    assert mapping.bars_path_template == "/bars/{market}/{symbol}"


def test_provider_request_mapping_normalizes_provider_name() -> None:
    # 供应商名称来自环境变量，大小写和空格不应影响路径映射选择。
    mapping = get_provider_request_mapping("  DemoProvider  ")

    assert mapping is DEFAULT_REQUEST_MAPPING


def test_provider_request_mapping_builds_default_urls() -> None:
    # 默认路径保持当前接口形态：Quote 走 quotes，历史 K 线走 bars。
    quote_url = DEFAULT_REQUEST_MAPPING.build_quote_url(
        "https://provider.example.test/",
        MarketCode.US,
        "NVDA",
    )
    bars_url = DEFAULT_REQUEST_MAPPING.build_bars_url(
        "https://provider.example.test/",
        MarketCode.US,
        "NVDA",
        interval="1d",
        count=120,
        start=date(2026, 1, 1),
        end=date(2026, 3, 31),
    )

    assert quote_url == "https://provider.example.test/quotes/US/NVDA"
    assert bars_url == "https://provider.example.test/bars/US/NVDA?interval=1d&count=120&start=2026-01-01&end=2026-03-31"


def test_real_provider_accepts_injected_request_mapping() -> None:
    # 真实供应商 URL 差异通过请求映射注入解决，不需要修改 service 或 API 层。
    provider = RealMarketDataProvider(
        settings=Settings(
            DATA_PROVIDER="real",
            REAL_PROVIDER_NAME="VendorHttpProvider",
            REAL_PROVIDER_BASE_URL="https://vendor.example.test/api/",
            _env_file=None,
        ),
        request_mapping=ProviderRequestMapping(
            quote_path_template="/v1/markets/{market}/symbols/{symbol}/quote",
            bars_path_template="/v1/markets/{market}/symbols/{symbol}/bars",
        ),
    )

    quote_request = provider.build_quote_request(MarketCode.HK, " 00700.hk ")
    bars_request = provider.build_bars_request(
        MarketCode.HK,
        " 00700.hk ",
        interval=" 1D ",
        count=30,
    )

    assert quote_request["url"] == "https://vendor.example.test/api/v1/markets/HK/symbols/00700.HK/quote"
    assert bars_request["url"] == "https://vendor.example.test/api/v1/markets/HK/symbols/00700.HK/bars?interval=1d&count=30"

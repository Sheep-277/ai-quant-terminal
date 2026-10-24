import pytest

from app.core.config import Settings
from app.providers.field_mapping import (
    DEFAULT_FIELD_MAPPING,
    ProviderFieldMapping,
    get_provider_field_mapping,
)
from app.providers.real_market_data import RealMarketDataProvider
from app.schemas.market import DataStatus


def test_provider_field_mapping_returns_default_for_unknown_provider() -> None:
    # 未建立专属映射的供应商先走通用字段别名，避免接入初期重复改归一化逻辑。
    mapping = get_provider_field_mapping("VendorHttpProvider")

    assert mapping is DEFAULT_FIELD_MAPPING
    assert "lastPrice" in mapping.quote["price"]
    assert "tradeVolume" in mapping.bars["volume"]


def test_provider_field_mapping_normalizes_provider_name() -> None:
    # 供应商名称来自环境变量，大小写和空格不应影响映射选择。
    mapping = get_provider_field_mapping("  DemoProvider  ")

    assert mapping is DEFAULT_FIELD_MAPPING


@pytest.mark.parametrize(
    ("provider_name", "expected_source"),
    [
        ("RealMarketDataProvider", "mock_fallback"),
        ("DemoProvider", "demo_provider"),
        ("YahooFinance", "yahoo_finance"),
    ],
)
def test_real_provider_accepts_injected_field_mapping(
    provider_name: str, expected_source: str,
) -> None:
    # 真实供应商字段差异通过映射注入解决，不需要修改 service 或 API 层。
    provider = RealMarketDataProvider(
        # 显式指定来源配置，避免运行者的环境变量改变元数据断言。
        settings=Settings(
            DATA_PROVIDER="real",
            REAL_PROVIDER_NAME=provider_name,
            REAL_PROVIDER_BASE_URL="https://provider.example.test",
            REAL_PROVIDER_API_KEY_ENV="",
            _env_file=None,
        ),
        field_mapping=ProviderFieldMapping(
            quote={
                "price": ("lastTradePrice",),
                "change": ("netChange",),
                "change_percent": ("netChangeRatio",),
                "volume": ("totalVolume",),
                "turnover": ("totalAmount",),
            },
            bars={
                "open": ("openValue",),
                "high": ("highValue",),
                "low": ("lowValue",),
                "close": ("closeValue",),
                "volume": ("barVolume",),
            },
        ),
    )

    quote = provider.normalize_quote_response(
        {
            "lastTradePrice": "100.00",
            "netChange": "2.50",
            "netChangeRatio": "2.5",
            "totalVolume": "1000",
            "totalAmount": "100000",
        },
        data_status=DataStatus.DELAYED,
    )
    bars = provider.normalize_bars_response(
        [
            {
                "openValue": "98.00",
                "highValue": "101.00",
                "lowValue": "97.50",
                "closeValue": "100.00",
                "barVolume": "1200",
                "timestamp": "2026-10-16T20:00:00Z",
            }
        ]
    )

    assert quote == {
        "price": 100.0,
        "change": 2.5,
        "change_percent": 0.025,
        "volume": 1000,
        "turnover": 100000.0,
        "data_status": DataStatus.DELAYED,
    }
    assert bars == [
        {
            "offset": 0,
            "timestamp": "2026-10-16T20:00:00Z",
            "data_status": DataStatus.DELAYED,
            "source": expected_source,
            "open": 98.0,
            "high": 101.0,
            "low": 97.5,
            "close": 100.0,
            "volume": 1200,
        }
    ]

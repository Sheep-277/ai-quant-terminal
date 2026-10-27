from datetime import date

import pytest
from pydantic import ValidationError

from app.core.config import DataProviderMode, Settings
from app.core.exceptions import ProviderResponseError, ProviderUnavailableError
from app.core.market import MarketCode
from app.providers.factory import get_market_data_provider
from app.providers.market_data import MockMarketDataProvider
from app.providers.real_market_data import RealMarketDataProvider
from app.schemas.market import DataStatus


def test_settings_defaults_to_mock_data_provider() -> None:
    # 不配置 DATA_PROVIDER 时，后端必须默认停留在安全的 Mock 数据模式。
    settings = Settings(_env_file=None)

    assert settings.data_provider == DataProviderMode.MOCK
    assert settings.real_provider_name == "RealMarketDataProvider"
    assert settings.real_provider_base_url is None
    assert settings.real_provider_api_key_env is None
    assert settings.real_provider_api_key_header == "Authorization"
    assert settings.enable_provider_status_logging is False
    assert settings.enable_market_database_reads is False
    assert settings.enable_market_database_writes is False
    assert settings.enable_stock_database_reads is False
    assert settings.enable_monitor_database_reads is False
    assert settings.enable_ai_research_database_writes is False


def test_settings_reads_data_provider_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # 真实 Provider 接入前，环境变量已经具备统一入口，避免未来散落到各个 service 中。
    monkeypatch.setenv("DATA_PROVIDER", "mock")
    monkeypatch.setenv("REAL_PROVIDER_NAME", "DemoProvider")
    monkeypatch.setenv("REAL_PROVIDER_BASE_URL", "https://provider.example.test")
    monkeypatch.setenv("REAL_PROVIDER_API_KEY_ENV", "DEMO_PROVIDER_API_KEY")
    monkeypatch.setenv("REAL_PROVIDER_API_KEY_HEADER", "X-API-Key")
    monkeypatch.setenv("ENABLE_PROVIDER_STATUS_LOGGING", "true")
    monkeypatch.setenv("ENABLE_MARKET_DATABASE_READS", "true")
    monkeypatch.setenv("ENABLE_MARKET_DATABASE_WRITES", "true")
    monkeypatch.setenv("ENABLE_STOCK_DATABASE_READS", "true")
    monkeypatch.setenv("ENABLE_MONITOR_DATABASE_READS", "true")
    monkeypatch.setenv("ENABLE_AI_RESEARCH_DATABASE_WRITES", "true")

    settings = Settings(_env_file=None)

    assert settings.data_provider == DataProviderMode.MOCK
    assert settings.real_provider_name == "DemoProvider"
    assert settings.real_provider_base_url == "https://provider.example.test"
    assert settings.real_provider_api_key_env == "DEMO_PROVIDER_API_KEY"
    assert settings.real_provider_api_key_header == "X-API-Key"
    assert settings.enable_provider_status_logging is True
    assert settings.enable_market_database_reads is True
    assert settings.enable_market_database_writes is True
    assert settings.enable_stock_database_reads is True
    assert settings.enable_monitor_database_reads is True
    assert settings.enable_ai_research_database_writes is True


def test_settings_rejects_unknown_data_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    # 拼错或未实现的数据源模式要在启动配置阶段失败，避免误以为已经接入真实行情。
    monkeypatch.setenv("DATA_PROVIDER", "alpaca")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_provider_factory_returns_mock_provider_for_mock_mode() -> None:
    # Provider 工厂是后续切换真实数据源的唯一入口，当前 mock 模式应返回 Mock 实现。
    settings = Settings(DATA_PROVIDER="mock", _env_file=None)

    provider = get_market_data_provider(settings)
    status = provider.get_provider_status()

    assert isinstance(provider, MockMarketDataProvider)
    assert status["provider_name"] == "MockMarketDataProvider"
    assert status["ready"] is True
    assert status["fallback_active"] is False


def test_provider_factory_returns_real_placeholder_for_real_mode() -> None:
    # real 模式当前只代表真实 Provider 占位边界，不能伪装成已接入真实行情。
    settings = Settings(DATA_PROVIDER="real", _env_file=None)

    provider = get_market_data_provider(settings)
    status = provider.get_provider_status()

    assert isinstance(provider, RealMarketDataProvider)
    assert provider.get_market_data_status(MarketCode.US) == DataStatus.UNAVAILABLE
    assert status["provider_name"] == "RealMarketDataProvider"
    assert status["ready"] is False
    assert status["data_status"] == DataStatus.UNAVAILABLE
    assert status["fallback_active"] is True
    assert "REAL_PROVIDER_BASE_URL" in (status["fallback_reason"] or "")


def test_demo_provider_status_reports_local_demo_source() -> None:
    # DemoProvider 是本地样例 Provider，状态应明确显示 demo 源可用，而不是 HTTP 待验证。
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="",
        _env_file=None,
    )

    provider = get_market_data_provider(settings)
    status = provider.get_provider_status()

    assert isinstance(provider, RealMarketDataProvider)
    assert status["provider_name"] == "DemoProvider"
    assert status["ready"] is True
    assert status["data_status"] == DataStatus.DELAYED
    assert status["fallback_active"] is False
    assert status["fallback_reason"] is None
    assert status["source_type"] == "demo_provider"
    assert status["active_source"] == "demo_provider"
    assert status["next_action"] == "当前使用本地 DemoProvider 样例行情；接真实行情时请替换 Provider 配置。"


def test_real_http_provider_reads_configuration_but_still_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    # 非 Demo 的真实 Provider 配置齐全只代表 HTTP 入口已准备好，供应商响应验证前仍保留回退。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="VendorHttpProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="DEMO_PROVIDER_API_KEY",
        _env_file=None,
    )

    provider = get_market_data_provider(settings)
    status = provider.get_provider_status()

    assert isinstance(provider, RealMarketDataProvider)
    assert status["provider_name"] == "VendorHttpProvider"
    assert status["ready"] is False
    assert status["data_status"] == DataStatus.DELAYED
    assert status["fallback_active"] is True
    assert "Quote HTTP 读取边界已启用" in (status["fallback_reason"] or "")
    assert status["source_type"] == "real_http_configured"
    assert status["active_source"] == "mock_fallback"
    assert status["next_action"] == "调用个股 Quote 接口验证真实 Provider 响应字段，再逐步关闭 Mock 回退。"


def test_provider_factory_uses_demo_adapter_for_demo_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # DemoProvider 是本地真实源演示 adapter，可在不访问外部网络的情况下跑通 real 模式。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="DEMO_PROVIDER_API_KEY",
        _env_file=None,
    )

    provider = get_market_data_provider(settings)

    quote = provider.get_quote(MarketCode.US, "NVDA")

    assert isinstance(provider, RealMarketDataProvider)
    assert quote == {
        "price": 182.5,
        "change": 1.5,
        "change_percent": 0.00829,
        "volume": 1000,
        "turnover": 182500.0,
        "data_status": DataStatus.DELAYED,
    }


def test_demo_provider_does_not_require_api_key_environment() -> None:
    # DemoProvider 只用于本地 real 模式演示，不应要求用户额外配置真实供应商密钥。
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="",
        _env_file=None,
    )

    provider = get_market_data_provider(settings)

    status = provider.get_provider_status()
    quote = provider.get_quote(MarketCode.US, "NVDA")

    assert status["missing_configuration"] == []
    assert status["ready"] is True
    assert status["fallback_active"] is False
    assert status["source_type"] == "demo_provider"
    assert quote["price"] == 182.5
    assert quote["data_status"] == DataStatus.DELAYED


def test_demo_provider_exposes_demo_market_status_and_notes() -> None:
    # DemoProvider 已启用时，页面说明应提示样例行情，而不是误报真实源缺配置。
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="",
        _env_file=None,
    )
    provider = get_market_data_provider(settings)

    notes = provider.get_research_notes(MarketCode.US, "NVDA")

    assert provider.get_market_data_status(MarketCode.US) == DataStatus.DELAYED
    assert notes["risk_flags"][0] == "当前行情来自本地 DemoProvider 样例数据，不能作为真实投资依据。"
    assert notes["summary_points"][0] == "当前 DATA_PROVIDER=real，行情链路使用本地 DemoProvider 样例数据。"


def test_real_provider_fallback_snapshot_drives_status_and_event() -> None:
    # 状态接口和市场事件应复用同一份回退说明，避免不同页面展示不一致。
    settings = Settings(DATA_PROVIDER="real", _env_file=None)
    provider = RealMarketDataProvider(settings=settings)

    fallback_snapshot = provider.get_fallback_snapshot()
    status = provider.get_provider_status()
    events = provider.get_market_events(MarketCode.US)

    assert fallback_snapshot["active_source"] == status["active_source"]
    assert fallback_snapshot["fallback_reason"] == status["fallback_reason"]
    assert fallback_snapshot["missing_configuration"] == status["missing_configuration"]
    assert fallback_snapshot["event_title"] == events[0]["title"]


def test_real_provider_validate_configuration_raises_unavailable_error() -> None:
    # 缺少真实 Provider 配置时，内部流程应使用统一异常，而不是让上层解析状态字符串。
    settings = Settings(DATA_PROVIDER="real", _env_file=None)
    provider = RealMarketDataProvider(settings=settings)

    with pytest.raises(ProviderUnavailableError, match="REAL_PROVIDER_BASE_URL") as error:
        provider.validate_configuration()

    assert error.value.provider_name == "RealMarketDataProvider"
    assert error.value.retryable is False


def test_real_provider_builds_quote_request_without_exposing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    # 请求骨架只描述未来如何读取 Quote，不发网络请求，也不把密钥值放进返回结构。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test/",
        REAL_PROVIDER_API_KEY_ENV="DEMO_PROVIDER_API_KEY",
        _env_file=None,
    )
    provider = RealMarketDataProvider(settings=settings)

    request = provider.build_quote_request(MarketCode.US, " nvda ")

    assert request == {
        "provider_name": "DemoProvider",
        "method": "GET",
        "url": "https://provider.example.test/quotes/US/NVDA",
        "market": "US",
        "symbol": "NVDA",
        "api_key_env": "DEMO_PROVIDER_API_KEY",
        "api_key_configured": True,
        "missing_configuration": [],
    }
    assert "test-token" not in str(request)


def test_real_provider_builds_bars_request_without_exposing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    # 历史 K 线请求只描述目标 URL 和查询参数，真实密钥仍只通过环境变量读取。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test/",
        REAL_PROVIDER_API_KEY_ENV="DEMO_PROVIDER_API_KEY",
        _env_file=None,
    )
    provider = RealMarketDataProvider(settings=settings)

    request = provider.build_bars_request(
        MarketCode.US,
        " nvda ",
        interval="1d",
        count=120,
        start=date(2026, 1, 1),
        end=date(2026, 3, 31),
    )

    assert request == {
        "provider_name": "DemoProvider",
        "method": "GET",
        "url": "https://provider.example.test/bars/US/NVDA?interval=1d&count=120&start=2026-01-01&end=2026-03-31",
        "market": "US",
        "symbol": "NVDA",
        "api_key_env": "DEMO_PROVIDER_API_KEY",
        "api_key_configured": True,
        "missing_configuration": [],
        "interval": "1d",
        "count": 120,
        "start": "2026-01-01",
        "end": "2026-03-31",
    }
    assert "test-token" not in str(request)


def test_real_provider_builds_bars_request_normalizes_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    # 周期参数在 Provider 边界统一规范，后续真实供应商 adapter 不再重复处理大小写和空格。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="DEMO_PROVIDER_API_KEY",
        _env_file=None,
    )
    provider = RealMarketDataProvider(settings=settings)

    request = provider.build_bars_request(MarketCode.US, "NVDA", interval=" 1D ", count=30)

    assert request["url"] == "https://provider.example.test/bars/US/NVDA?interval=1d&count=30"
    assert request["interval"] == "1d"
    assert request["count"] == 30
    assert request["start"] is None
    assert request["end"] is None


@pytest.mark.parametrize(
    ("interval", "count", "start", "end", "error_text"),
    [
        (" ", 30, None, None, "interval 不能为空"),
        ("1d", 0, None, None, "count 必须在 1 到 500 之间"),
        ("1d", 501, None, None, "count 必须在 1 到 500 之间"),
        ("1d", 30, date(2026, 3, 31), date(2026, 1, 1), "start 不能晚于 end"),
    ],
)
def test_real_provider_rejects_invalid_bars_request_params(
    interval: str,
    count: int,
    start: date | None,
    end: date | None,
    error_text: str,
) -> None:
    # 无效 K 线边界在 Provider 层直接失败，避免构造出真实供应商无法解释的请求。
    settings = Settings(DATA_PROVIDER="real", REAL_PROVIDER_BASE_URL="https://provider.example.test", _env_file=None)
    provider = RealMarketDataProvider(settings=settings)

    with pytest.raises(ProviderResponseError, match=error_text) as error:
        provider.build_bars_request(MarketCode.US, "NVDA", interval=interval, count=count, start=start, end=end)

    assert error.value.provider_name == "RealMarketDataProvider"
    assert error.value.retryable is False


def test_real_provider_normalizes_quote_response() -> None:
    # 真实供应商字段进入 service 前，必须先转换为项目统一 ProviderQuote 结构。
    settings = Settings(DATA_PROVIDER="real", _env_file=None)
    provider = RealMarketDataProvider(settings=settings)

    quote = provider.normalize_quote_response(
        {
            "last_price": "181.42",
            "change_amount": "2.38",
            "change_pct": "1.33",
            "volume": "218430000",
            "notional": "39612000000",
        },
        data_status=DataStatus.DELAYED,
    )

    assert quote == {
        "price": 181.42,
        "change": 2.38,
        "change_percent": 0.0133,
        "volume": 218430000,
        "turnover": 39612000000.0,
        "data_status": DataStatus.DELAYED,
    }


def test_real_provider_normalizes_bars_response() -> None:
    # 历史 K 线供应商字段进入 service 前，也必须先转换为项目统一 ProviderBar 结构。
    settings = Settings(DATA_PROVIDER="real", _env_file=None)
    provider = RealMarketDataProvider(settings=settings)

    bars = provider.normalize_bars_response(
        [
            {"o": "180.00", "h": "183.00", "l": "179.50", "c": "182.50", "v": "1000"},
            {
                "openPrice": "182.50",
                "highPrice": "184.20",
                "lowPrice": "181.80",
                "closePrice": "183.75",
                "tradeVolume": "1200",
            },
        ]
    )

    assert bars == [
        {
            "offset": 1,
            "data_status": DataStatus.DELAYED,
            "source": "mock_fallback",
            "open": 180.0,
            "high": 183.0,
            "low": 179.5,
            "close": 182.5,
            "volume": 1000,
        },
        {
            "offset": 0,
            "open": 182.5,
            "data_status": DataStatus.DELAYED,
            "source": "mock_fallback",
            "high": 184.2,
            "low": 181.8,
            "close": 183.75,
            "volume": 1200,
        },
    ]


def test_real_provider_normalizes_common_vendor_quote_aliases() -> None:
    # 真实供应商常使用驼峰字段或不同成交额命名，Provider 层统一转换后再进入业务层。
    settings = Settings(DATA_PROVIDER="real", _env_file=None)
    provider = RealMarketDataProvider(settings=settings)

    quote = provider.normalize_quote_response(
        {
            "lastPrice": "182.50",
            "priceChange": "1.50",
            "changeRate": "0.00829",
            "tradeVolume": "1000",
            "turnoverValue": "182500",
        },
        data_status=DataStatus.DELAYED,
    )

    assert quote == {
        "price": 182.5,
        "change": 1.5,
        "change_percent": 0.00829,
        "volume": 1000,
        "turnover": 182500.0,
        "data_status": DataStatus.DELAYED,
    }


def test_real_provider_rejects_incomplete_quote_response() -> None:
    # 缺字段的真实行情不能静默进入量化计算，否则会造成误导性指标。
    settings = Settings(DATA_PROVIDER="real", _env_file=None)
    provider = RealMarketDataProvider(settings=settings)

    with pytest.raises(ProviderResponseError, match="Quote 响应缺少必填字段") as error:
        provider.normalize_quote_response({"last_price": 181.42})

    assert error.value.provider_name == "RealMarketDataProvider"
    assert error.value.retryable is False


def test_real_provider_rejects_incomplete_bars_response() -> None:
    # 缺字段的 K 线同样不能进入技术指标计算和图表展示。
    settings = Settings(DATA_PROVIDER="real", _env_file=None)
    provider = RealMarketDataProvider(settings=settings)

    with pytest.raises(ProviderResponseError, match="K 线响应缺少必填字段") as error:
        provider.normalize_bars_response([{"open": 180.0, "high": 183.0}])

    assert error.value.provider_name == "RealMarketDataProvider"
    assert error.value.retryable is False


def test_real_provider_rejects_empty_bars_response() -> None:
    # 真实供应商返回空 K 线数组时，应明确失败并触发上层 Mock 回退。
    settings = Settings(DATA_PROVIDER="real", _env_file=None)
    provider = RealMarketDataProvider(settings=settings)

    with pytest.raises(ProviderResponseError, match="K 线响应不能为空数组") as error:
        provider.normalize_bars_response([])

    assert error.value.provider_name == "RealMarketDataProvider"
    assert error.value.retryable is False


def test_real_provider_rejects_invalid_bars_number() -> None:
    # K 线字段类型错误时，错误信息应明确指向 K 线，而不是误报为 Quote 字段。
    settings = Settings(DATA_PROVIDER="real", _env_file=None)
    provider = RealMarketDataProvider(settings=settings)

    with pytest.raises(ProviderResponseError, match="K 线字段 close 不是有效数字") as error:
        provider.normalize_bars_response(
            [{"open": 180.0, "high": 183.0, "low": 179.0, "close": "bad-close", "volume": 1000}]
        )

    assert error.value.provider_name == "RealMarketDataProvider"
    assert error.value.retryable is False


def test_real_provider_rejects_invalid_bar_high_price() -> None:
    # high 低于 open 或 close 的 K 线是明显脏数据，不能进入图表和指标计算。
    settings = Settings(DATA_PROVIDER="real", _env_file=None)
    provider = RealMarketDataProvider(settings=settings)

    with pytest.raises(ProviderResponseError, match="K 线字段 high 不能低于 open 或 close") as error:
        provider.normalize_bars_response(
            [{"open": 180.0, "high": 179.0, "low": 178.0, "close": 181.0, "volume": 1000}]
        )

    assert error.value.provider_name == "RealMarketDataProvider"
    assert error.value.retryable is False


def test_real_provider_rejects_invalid_bar_low_price() -> None:
    # low 高于 open 或 close 同样说明供应商原始 K 线不合法。
    settings = Settings(DATA_PROVIDER="real", _env_file=None)
    provider = RealMarketDataProvider(settings=settings)

    with pytest.raises(ProviderResponseError, match="K 线字段 low 不能高于 open 或 close") as error:
        provider.normalize_bars_response(
            [{"open": 180.0, "high": 183.0, "low": 181.0, "close": 179.0, "volume": 1000}]
        )

    assert error.value.provider_name == "RealMarketDataProvider"
    assert error.value.retryable is False


def test_real_provider_rejects_negative_bar_volume() -> None:
    # 成交量不能为负数，否则会污染成交量图表和后续量化特征。
    settings = Settings(DATA_PROVIDER="real", _env_file=None)
    provider = RealMarketDataProvider(settings=settings)

    with pytest.raises(ProviderResponseError, match="K 线字段 volume 不能为负数") as error:
        provider.normalize_bars_response(
            [{"open": 180.0, "high": 183.0, "low": 179.0, "close": 181.0, "volume": -1}]
        )

    assert error.value.provider_name == "RealMarketDataProvider"
    assert error.value.retryable is False


def test_real_provider_get_quote_uses_fetch_flow_when_adapter_returns_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 该测试不访问网络，只验证真实 Provider 的请求构造、响应读取和归一化流程已经串通。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="DEMO_PROVIDER_API_KEY",
        _env_file=None,
    )
    captured_request: dict[str, object] = {}

    class FakeQuoteFetcher:
        """测试用 QuoteFetcher，不访问网络，只返回固定供应商原始字段。"""

        def fetch_quote(self, request: dict[str, object]) -> dict[str, object]:
            captured_request.update(request)
            return {
                "last": "182.50",
                "change": "1.50",
                "change_percent": "0.00829",
                "volume": "1000",
                "amount": "182500",
            }

    provider = RealMarketDataProvider(settings=settings, quote_fetcher=FakeQuoteFetcher())

    quote = provider.get_quote(MarketCode.US, " nvda ")

    assert captured_request["url"] == "https://provider.example.test/quotes/US/NVDA"
    assert quote == {
        "price": 182.5,
        "change": 1.5,
        "change_percent": 0.00829,
        "volume": 1000,
        "turnover": 182500.0,
        "data_status": DataStatus.DELAYED,
    }


def test_real_provider_get_quote_falls_back_when_adapter_returns_no_data() -> None:
    # Adapter 尚未实现时，get_quote 必须继续返回 Mock 回退，并显式标记 unavailable。
    settings = Settings(DATA_PROVIDER="real", _env_file=None)
    provider = RealMarketDataProvider(settings=settings)

    quote = provider.get_quote(MarketCode.US, "NVDA")

    assert quote["price"] > 0
    assert quote["data_status"] == DataStatus.UNAVAILABLE


def test_real_provider_get_bars_uses_fetch_json_when_adapter_returns_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 该测试不访问网络，只验证真实 K 线请求、JSON 读取和 ProviderBar 归一化流程已经串通。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="DEMO_PROVIDER_API_KEY",
        _env_file=None,
    )
    captured_request: dict[str, object] = {}

    class FakeBarsFetcher:
        """测试用 K 线 fetcher，不访问网络，只返回固定供应商原始字段。"""

        def fetch_quote(self, request: dict[str, object]) -> None:
            return None

        def fetch_json(
            self,
            request: dict[str, object],
            *,
            wrapper_keys: tuple[str, ...] = (),
            require_wrapped_object: bool = False,
        ) -> list[dict[str, str]]:
            captured_request.update(request)
            assert wrapper_keys == ("data", "bars", "result")
            assert require_wrapped_object is False
            return [{"o": "180.00", "h": "183.00", "l": "179.50", "c": "182.50", "v": "1000"}]

    provider = RealMarketDataProvider(settings=settings, quote_fetcher=FakeBarsFetcher())

    bars = provider.get_bars(MarketCode.US, " nvda ", count=1)

    assert captured_request["url"] == "https://provider.example.test/bars/US/NVDA?interval=1d&count=1"
    assert bars == [
        {
            "offset": 0,
            "data_status": DataStatus.DELAYED,
            "source": "demo_provider",
            "open": 180.0,
            "high": 183.0,
            "low": 179.5,
            "close": 182.5,
            "volume": 1000,
        }
    ]


def test_real_provider_get_bars_extracts_nested_vendor_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 部分真实供应商会把 K 线数组包在 data.bars 或 result.items 中，Provider 层负责解包。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="DEMO_PROVIDER_API_KEY",
        _env_file=None,
    )

    class NestedBarsFetcher:
        """测试用 K 线 fetcher，模拟真实供应商的嵌套响应结构。"""

        def fetch_quote(self, request: dict[str, object]) -> None:
            return None

        def fetch_json(
            self,
            request: dict[str, object],
            *,
            wrapper_keys: tuple[str, ...] = (),
            require_wrapped_object: bool = False,
        ) -> dict[str, object]:
            return {
                "data": {
                    "bars": [
                        {"open": "180.00", "high": "183.00", "low": "179.50", "close": "182.50", "volume": "1000"}
                    ]
                }
            }

    provider = RealMarketDataProvider(settings=settings, quote_fetcher=NestedBarsFetcher())

    bars = provider.get_bars(MarketCode.US, "NVDA", count=1)

    assert bars == [
        {
            "offset": 0,
            "data_status": DataStatus.DELAYED,
            "source": "demo_provider",
            "open": 180.0,
            "high": 183.0,
            "low": 179.5,
            "close": 182.5,
            "volume": 1000,
        }
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"data": [{"open": "180.00", "high": "183.00", "low": "179.50", "close": "182.50", "volume": "1000"}]},
        {
            "result": {
                "items": [
                    {"open": "180.00", "high": "183.00", "low": "179.50", "close": "182.50", "volume": "1000"}
                ]
            }
        },
        {"candles": [{"open": "180.00", "high": "183.00", "low": "179.50", "close": "182.50", "volume": "1000"}]},
        {"klines": [{"open": "180.00", "high": "183.00", "low": "179.50", "close": "182.50", "volume": "1000"}]},
    ],
)
def test_real_provider_get_bars_extracts_common_vendor_payload_shapes(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
) -> None:
    # 固定真实供应商常见 K 线包装形态，避免接入新供应商时只适配单一 data.bars 结构。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="DEMO_PROVIDER_API_KEY",
        _env_file=None,
    )

    class CommonShapeBarsFetcher:
        """测试用 K 线 fetcher，返回不同供应商风格的包装结构。"""

        def fetch_quote(self, request: dict[str, object]) -> None:
            return None

        def fetch_json(
            self,
            request: dict[str, object],
            *,
            wrapper_keys: tuple[str, ...] = (),
            require_wrapped_object: bool = False,
        ) -> dict[str, object]:
            return payload

    provider = RealMarketDataProvider(settings=settings, quote_fetcher=CommonShapeBarsFetcher())

    bars = provider.get_bars(MarketCode.US, "NVDA", count=1)

    assert bars == [
        {
            "offset": 0,
            "data_status": DataStatus.DELAYED,
            "source": "demo_provider",
            "open": 180.0,
            "high": 183.0,
            "low": 179.5,
            "close": 182.5,
            "volume": 1000,
        }
    ]


def test_real_provider_get_bars_falls_back_when_adapter_returns_no_data() -> None:
    # 真实 K 线 fetcher 未接入或配置缺失时，get_bars 仍应稳定回退 Mock K 线。
    settings = Settings(DATA_PROVIDER="real", _env_file=None)
    provider = RealMarketDataProvider(settings=settings)

    bars = provider.get_bars(MarketCode.US, "NVDA", count=2)

    assert len(bars) == 2
    assert bars[-1]["offset"] == 0
    assert all(bar["close"] > 0 for bar in bars)


def test_real_provider_get_bars_falls_back_when_nested_payload_has_no_bars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 供应商返回对象但没有 K 线数组时，也应触发 Mock 回退，避免前端图表空白。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="DEMO_PROVIDER_API_KEY",
        _env_file=None,
    )

    class MissingBarsFetcher:
        """测试用 K 线 fetcher，模拟供应商返回了非 K 线业务对象。"""

        def fetch_quote(self, request: dict[str, object]) -> None:
            return None

        def fetch_json(
            self,
            request: dict[str, object],
            *,
            wrapper_keys: tuple[str, ...] = (),
            require_wrapped_object: bool = False,
        ) -> dict[str, object]:
            return {"data": {"message": "no bars"}}

    provider = RealMarketDataProvider(settings=settings, quote_fetcher=MissingBarsFetcher())

    bars = provider.get_bars(MarketCode.US, "NVDA", count=2)

    assert len(bars) == 2
    assert bars[-1]["offset"] == 0
    assert all(bar["close"] > 0 for bar in bars)


def test_real_provider_get_bars_falls_back_when_payload_item_is_not_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # K 线数组元素不是对象时属于供应商脏数据，应触发 Mock 回退而不是进入归一化。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="DEMO_PROVIDER_API_KEY",
        _env_file=None,
    )

    class ScalarBarsFetcher:
        """测试用 K 线 fetcher，模拟供应商返回了错误的数组元素类型。"""

        def fetch_quote(self, request: dict[str, object]) -> None:
            return None

        def fetch_json(
            self,
            request: dict[str, object],
            *,
            wrapper_keys: tuple[str, ...] = (),
            require_wrapped_object: bool = False,
        ) -> dict[str, object]:
            return {"data": ["bad-bar"]}

    provider = RealMarketDataProvider(settings=settings, quote_fetcher=ScalarBarsFetcher())

    bars = provider.get_bars(MarketCode.US, "NVDA", count=2)

    assert len(bars) == 2
    assert bars[-1]["offset"] == 0
    assert all(bar["close"] > 0 for bar in bars)


def test_real_provider_get_bars_falls_back_when_adapter_returns_empty_bars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 真实供应商返回空 K 线数组时，Provider 应触发 Mock 回退，而不是把空列表传给 service。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="DEMO_PROVIDER_API_KEY",
        _env_file=None,
    )

    class EmptyBarsFetcher:
        """测试用 K 线 fetcher，模拟供应商返回空数组。"""

        def fetch_quote(self, request: dict[str, object]) -> None:
            return None

        def fetch_json(
            self,
            request: dict[str, object],
            *,
            wrapper_keys: tuple[str, ...] = (),
            require_wrapped_object: bool = False,
        ) -> list[dict[str, object]]:
            return []

    provider = RealMarketDataProvider(settings=settings, quote_fetcher=EmptyBarsFetcher())

    bars = provider.get_bars(MarketCode.US, "NVDA", count=2)

    assert len(bars) == 2
    assert bars[-1]["offset"] == 0
    assert all(bar["close"] > 0 for bar in bars)


def test_real_provider_get_quote_falls_back_when_adapter_raises_response_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 真实源请求失败或响应异常时，页面不应直接报错，而是展示明确的 unavailable 回退行情。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="DemoProvider",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="DEMO_PROVIDER_API_KEY",
        _env_file=None,
    )

    class FailingQuoteFetcher:
        """测试用 QuoteFetcher，模拟真实供应商请求或解析失败。"""

        def fetch_quote(self, request: dict[str, object]) -> dict[str, object]:
            raise ProviderResponseError(
                "真实行情 Provider 请求失败。",
                provider_name=str(request["provider_name"]),
                retryable=True,
            )

    provider = RealMarketDataProvider(settings=settings, quote_fetcher=FailingQuoteFetcher())

    quote = provider.get_quote(MarketCode.US, "NVDA")

    assert quote["price"] > 0
    assert quote["data_status"] == DataStatus.UNAVAILABLE

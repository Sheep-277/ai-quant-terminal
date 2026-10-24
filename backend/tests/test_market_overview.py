from datetime import datetime, timezone
from typing import Mapping

import pytest

from app.api.v1.market import build_market_overview_response
from app.core.config import Settings, get_settings
from app.core.exceptions import ProviderUnavailableError
from app.core.market import MarketCode
from app.db.seed import seed_development_data
from app.db.session import create_database_engine, get_engine, get_session_factory
from app.providers.factory import get_market_data_provider
from app.providers.http_quote_fetcher import JsonPayload, RealProviderReadRequest
from app.providers.real_market_data import RealMarketDataProvider
from app.schemas.market import DataStatus, MarketEventOrigin, MarketOverviewResponse


@pytest.fixture(autouse=True)
def disable_market_database_reads_by_default(monkeypatch: pytest.MonkeyPatch):
    """多数市场总览测试验证默认 Mock 行为，避免本地 .env 影响测试结果。"""

    monkeypatch.setenv("ENABLE_MARKET_DATABASE_READS", "false")
    monkeypatch.setenv("DATA_PROVIDER", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _build_mock_overview(market: MarketCode = MarketCode.US):
    """直接测试市场总览构造逻辑，避开当前环境中 TestClient.get 阻塞问题。"""

    return build_market_overview_response(
        market,
        Settings(
            ENABLE_MARKET_DATABASE_READS=False,
            _env_file=None,
        ),
    )


def test_market_overview_can_use_database_latest_quotes(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    seed_development_data(engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_settings.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)

    response = build_market_overview_response(
        MarketCode.US,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_MARKET_DATABASE_READS=True,
            _env_file=None,
        ),
    )

    assert response.market == MarketCode.US
    assert response.data_status == "realtime"
    assert {index.symbol for index in response.indices} == {"SPX", "NDX", "VIX"}
    assert response.indices[0].name == "S&P 500"
    assert response.indices[0].value != 232.18
    assert response.breadth.advancers_percent == 0.5
    assert response.breadth.decliners_percent == 0.5
    assert response.breadth.source == "database"
    assert response.breadth.timestamp == response.timestamp
    assert response.events[0].source == "DATABASE"
    assert response.events[0].origin == "system"


def test_market_overview_appends_fallback_event_when_database_read_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_database_error(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("app.api.v1.market.get_market_overview_read_snapshot", raise_database_error)

    response = build_market_overview_response(
        MarketCode.US,
        Settings(
            ENABLE_MARKET_DATABASE_READS=True,
            _env_file=None,
        ),
    )

    assert response.market == MarketCode.US
    assert response.data_status == "unavailable"
    assert response.events[0].source == "PROVIDER"
    assert response.events[0].origin == "system"
    assert response.events[0].impact == "warning"
    assert "RuntimeError" in response.events[0].title
    assert "Mock 市场总览" in response.events[0].title


def test_market_overview_defaults_to_us() -> None:
    # market 不传时应使用 US，保证前端默认页面可以直接请求。
    payload = _build_mock_overview()

    assert payload.market == MarketCode.US
    assert payload.currency == "USD"
    assert payload.indices


def test_market_overview_supports_all_v1_markets() -> None:
    # V1 必须覆盖美股、港股、A股三个市场。
    expected = {
        "US": "USD",
        "HK": "HKD",
        "CN": "CNY",
    }

    for market, currency in expected.items():
        payload = _build_mock_overview(MarketCode(market))

        assert payload.market == market
        assert payload.currency == currency
        assert payload.indices
        assert payload.breadth
        assert payload.chart_bars
        assert payload.sectors
        assert payload.events


def test_market_overview_includes_chart_bars_for_dashboard() -> None:
    # 市场总览图表应直接消费后端 bars，不能只依赖前端派生点位。
    payload = _build_mock_overview(MarketCode.HK)
    first_bar = payload.chart_bars[0]

    assert first_bar.timestamp
    assert first_bar.high >= max(first_bar.open, first_bar.close)
    assert first_bar.low <= min(first_bar.open, first_bar.close)
    assert first_bar.volume >= 0
    assert first_bar.data_status in {"delayed", "unavailable"}
    assert first_bar.source


def test_market_data_provider_exposes_market_overview_contract_shapes() -> None:
    # 市场总览 service 应读取标准 Provider 合同，而不是依赖 Mock fixture 的 tuple 顺序。
    market_data_provider = get_market_data_provider()
    data_status = market_data_provider.get_market_data_status(MarketCode.US)
    indices = market_data_provider.get_market_indices(MarketCode.US)
    breadth = market_data_provider.get_market_breadth(MarketCode.US)
    sectors = market_data_provider.get_sector_performance(MarketCode.US)
    events = market_data_provider.get_market_events(MarketCode.US)

    assert data_status == "realtime"
    assert indices[0]["symbol"] == "SPX"
    assert indices[0]["value"] > 0
    assert 0 <= breadth["advancers_percent"] <= 1
    assert breadth["new_highs"] >= 0
    assert breadth["source"] == "mock_provider"
    assert sectors[0]["name"]
    assert "change_percent" in sectors[0]
    assert sectors[0]["source"] == "mock_provider"
    assert events[0]["source"]
    assert events[0]["origin"] == "mock_sample"
    assert 0 <= events[0]["confidence"] <= 1


def test_market_overview_sector_direction_matches_return() -> None:
    # 行业方向应由涨跌幅统一推导，避免 Mock fixture 手工写错。
    payload = _build_mock_overview(MarketCode.CN)

    for sector in payload.sectors:
        assert sector.source == "mock_provider"
        if sector.change_percent > 0:
            assert sector.direction == "positive"
        elif sector.change_percent < 0:
            assert sector.direction == "negative"
        else:
            assert sector.direction == "neutral"


def test_market_overview_delayed_market_contains_data_status_event() -> None:
    # 延迟行情必须显式提示，不能让前端或用户误以为是实时数据。
    payload = _build_mock_overview(MarketCode.HK)

    assert payload.data_status == "delayed"
    assert any("延迟数据" in event.title for event in payload.events)
    assert all(event.origin in {"mock_sample", "system", "news"} for event in payload.events)


def test_market_overview_rejects_unknown_market() -> None:
    # 未支持的市场不能被静默映射，避免业务层靠 ticker 猜市场。
    with pytest.raises(ValueError):
        MarketCode("EU")


@pytest.mark.parametrize("market", list(MarketCode))
@pytest.mark.parametrize("failed_kind", ["indices", "bars", "both"])
def test_market_overview_preserves_item_provenance_on_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
    market: MarketCode,
    failed_kind: str,
) -> None:
    """在响应边界校验局部失败，成功行情与回退数据不能互相覆盖来源和时间。"""

    quote_time = datetime(2024, 1, 3, tzinfo=timezone.utc)
    bar_time = datetime(2024, 1, 2, tzinfo=timezone.utc)

    class ScenarioFetcher:
        """只返回内存行情或统一 Provider 异常，不读取密钥，也不发网络请求。"""

        def fetch_quote(self, request: RealProviderReadRequest) -> Mapping[str, object]:
            assert request["market"] == market.value
            if failed_kind in {"indices", "both"}:
                raise ProviderUnavailableError("测试用指数读取失败", provider_name="YahooFinance")
            return {"price": 183.75, "change_percent": 0.0125, "timestamp": quote_time.isoformat()}

        def fetch_json(
            self,
            request: RealProviderReadRequest,
            *,
            wrapper_keys: tuple[str, ...] = (),
            require_wrapped_object: bool = False,
        ) -> JsonPayload:
            assert request["market"] == market.value
            assert request["symbol"] == {
                MarketCode.US: "^GSPC", MarketCode.HK: "^HSI", MarketCode.CN: "000300.SS",
            }[market]
            assert request["interval"] == "1d"
            assert request["count"] == 30
            if failed_kind in {"bars", "both"}:
                raise ProviderUnavailableError("测试用曲线读取失败", provider_name="YahooFinance")
            return [{
                "timestamp": bar_time.isoformat(),
                "open": 180.0, "high": 184.0, "low": 179.0, "close": 183.0, "volume": 1000,
            }]

    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="YahooFinance",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV=None,
        ENABLE_MARKET_DATABASE_READS=False,
        _env_file=None,
    )
    provider = RealMarketDataProvider(settings, quote_fetcher=ScenarioFetcher())
    monkeypatch.setattr("app.services.mock_market_service.get_market_data_provider", lambda: provider)

    response = build_market_overview_response(market, settings)
    # 经过与 HTTP 输出相同的 JSON 序列化，防止来源、空值或带时区时间在输出时丢失。
    payload = MarketOverviewResponse.model_validate_json(response.model_dump_json())

    assert payload.market == market
    assert payload.currency == {MarketCode.US: "USD", MarketCode.HK: "HKD", MarketCode.CN: "CNY"}[market]
    assert [index.symbol for index in payload.indices] == {
        MarketCode.US: ["SPX", "NDX", "VIX"],
        MarketCode.HK: ["HSI", "HSTECH", "VHSI"],
        MarketCode.CN: ["000300.SH", "000001.SH", "399006.SZ"],
    }[market]
    for index in payload.indices:
        # 港股未覆盖的两个指数始终不可用，不用样例点位冒充报价。
        unavailable = failed_kind in {"indices", "both"} or (market == MarketCode.HK and index.symbol != "HSI")
        assert index.source == "yahoo_finance"
        if unavailable:
            assert index.status == DataStatus.UNAVAILABLE
            assert index.value is None
            assert index.change_percent is None
            assert index.timestamp is None
            assert any(
                event.source == "PROVIDER" and event.origin == MarketEventOrigin.SYSTEM
                and index.symbol in event.title and "不可用" in event.title
                for event in payload.events
            )
        else:
            assert index.status == DataStatus.DELAYED
            assert index.value == 183.75
            assert index.change_percent == 0.0125
            assert index.timestamp == quote_time

    if failed_kind in {"bars", "both"}:
        assert len(payload.chart_bars) == 30
        assert all(bar.source == "mock_fallback" for bar in payload.chart_bars)
        assert all(bar.data_status == DataStatus.UNAVAILABLE for bar in payload.chart_bars)
    else:
        assert len(payload.chart_bars) == 1
        bar = payload.chart_bars[0]
        assert bar.source == "yahoo_finance"
        assert bar.data_status == DataStatus.DELAYED
        assert bar.timestamp == bar_time
        assert (bar.open, bar.high, bar.low, bar.close, bar.volume) == (180.0, 184.0, 179.0, 183.0, 1000)

    assert payload.breadth.source == "mock_fallback"
    assert payload.breadth.status == DataStatus.UNAVAILABLE
    assert payload.breadth.timestamp is None
    assert payload.sectors
    assert all(sector.source == "mock_fallback" and sector.status == DataStatus.UNAVAILABLE for sector in payload.sectors)
    assert all(sector.timestamp is None for sector in payload.sectors)

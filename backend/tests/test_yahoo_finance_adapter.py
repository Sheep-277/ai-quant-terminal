from collections.abc import Callable
from datetime import datetime, timezone
import json
import logging
from threading import Event, Lock
from unittest.mock import Mock
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request

import pytest

from app.core.config import Settings
from app.core.exceptions import ProviderResponseError
from app.core.market import MarketCode
from app.providers.http_quote_fetcher import RealProviderReadRequest
from app.providers.market_data import MockMarketDataProvider
from app.providers.real_market_data import RealMarketDataProvider
from app.providers.yahoo_finance_adapter import YahooFinanceAdapter
from app.schemas.market import DataStatus
from app.services.mock_market_service import get_mock_market_overview


def build_request(market: str = "US", symbol: str = "NVDA") -> RealProviderReadRequest:
    return {
        "provider_name": "YahooFinance",
        "method": "GET",
        "url": "https://query1.finance.yahoo.com/v8/finance/chart/NVDA",
        "market": market,
        "symbol": symbol,
        "api_key_env": None,
        "api_key_configured": False,
        "missing_configuration": [],
    }


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def build_chart_payload() -> bytes:
    return b"""
    {
      "chart": {
        "result": [
          {
            "meta": {
              "regularMarketPrice": 183.75,
              "previousClose": 182.50
            },
            "timestamp": [1704067200, 1704153600, 1704240000],
            "indicators": {
              "quote": [
                {
                  "open": [180.00, 182.50, 183.00],
                  "high": [183.00, 184.20, 184.80],
                  "low": [179.50, 181.80, 182.20],
                  "close": [182.50, 183.75, 183.90],
                  "volume": [1000, 1200, 1300]
                }
              ]
            }
          }
        ],
        "error": null
      }
    }
    """


def test_yahoo_finance_adapter_fetches_quote_without_api_key() -> None:
    captured_request: Request | None = None

    def fake_opener(http_request: Request, *, timeout: float) -> FakeResponse:
        nonlocal captured_request
        captured_request = http_request
        assert timeout == 8.0
        return FakeResponse(build_chart_payload())

    adapter = YahooFinanceAdapter(opener=fake_opener)

    quote = adapter.fetch_quote(build_request())

    assert captured_request is not None
    assert "query1.finance.yahoo.com/v8/finance/chart/NVDA" in captured_request.full_url
    assert quote == {
        "price": 183.75,
        "change": 1.25,
        "change_percent": 0.00684931506849315,
        "volume": 1300,
        "turnover": 238875.0,
        "timestamp": "2024-01-03T00:00:00+00:00",
    }


def test_yahoo_finance_adapter_fetches_bars_without_api_key() -> None:
    adapter = YahooFinanceAdapter(opener=lambda *_args, **_kwargs: FakeResponse(build_chart_payload()))

    bars = adapter.fetch_json(build_request())

    assert bars == [
        {"timestamp": "2024-01-01T00:00:00+00:00", "open": 180.0, "high": 183.0, "low": 179.5, "close": 182.5, "volume": 1000},
        {"timestamp": "2024-01-02T00:00:00+00:00", "open": 182.5, "high": 184.2, "low": 181.8, "close": 183.75, "volume": 1200},
        {"timestamp": "2024-01-03T00:00:00+00:00", "open": 183.0, "high": 184.8, "low": 182.2, "close": 183.9, "volume": 1300},
    ]


def test_yahoo_request_logs_connection_read_and_total_time(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    """用可控时钟验证分段耗时，不依赖网络和真实等待。"""

    ticks = iter([10.0, 10.1, 10.3, 10.4])
    monkeypatch.setattr("app.providers.yahoo_finance_adapter.perf_counter", lambda: next(ticks))
    caplog.set_level(logging.INFO, logger="app.providers.yahoo_finance_adapter")
    adapter = YahooFinanceAdapter(opener=lambda *_args, **_kwargs: FakeResponse(build_chart_payload()))

    assert len(adapter.fetch_json(build_request())) == 3

    assert len(caplog.records) == 1
    assert "market=US symbol=NVDA interval=1d outcome=success phase=complete" in caplog.text
    assert "elapsed_ms=400.0 connect_ms=100.0 read_ms=200.0 io_timeout_seconds=8.0" in caplog.text
    assert caplog.records[0].levelno == logging.INFO


@pytest.mark.parametrize("phase", ["connect", "read", "parse", "validate"])
def test_yahoo_request_failure_logs_phase_without_sensitive_payload(
    phase: str, caplog: pytest.LogCaptureFixture,
) -> None:
    """失败日志保留定位信息，但不泄露响应正文或原始网络异常。"""

    secret = "sensitive-upstream-detail"

    class ReadFailureResponse(FakeResponse):
        def read(self) -> bytes:
            raise TimeoutError(secret)

    calls = 0

    def opener(*_args: object, **_kwargs: object) -> FakeResponse:
        nonlocal calls
        calls += 1
        if phase == "connect":
            raise TimeoutError(secret)
        if phase == "read":
            return ReadFailureResponse(b"")
        return FakeResponse(secret.encode() if phase == "parse" else b"[]")

    with pytest.raises(ProviderResponseError):
        YahooFinanceAdapter(opener=opener).fetch_json(build_request("HK", "00700.HK"))

    assert calls == 1
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING
    assert f"outcome=failed phase={phase}" in caplog.text
    assert "market=HK symbol=00700.HK" in caplog.text
    assert secret not in caplog.text
    assert "https://" not in caplog.text
    assert caplog.records[0].exc_info is None


def test_yahoo_slow_success_is_warning_not_a_fabricated_timeout(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    """总耗时超过读写超时不等于请求失败，仍返回真实响应。"""

    ticks = iter([10.0, 19.0, 20.0, 20.1])
    monkeypatch.setattr("app.providers.yahoo_finance_adapter.perf_counter", lambda: next(ticks))
    adapter = YahooFinanceAdapter(opener=lambda *_args, **_kwargs: FakeResponse(build_chart_payload()))

    assert len(adapter.fetch_json(build_request())) == 3

    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING
    assert "outcome=success phase=complete elapsed_ms=10100.0" in caplog.text


def test_yahoo_finance_adapter_uses_request_period_for_bars() -> None:
    captured_url = ""

    def fake_opener(http_request: Request, *, timeout: float) -> FakeResponse:
        nonlocal captured_url
        captured_url = http_request.full_url
        return FakeResponse(build_chart_payload())

    request = build_request()
    request["interval"] = "1d"
    request["start"] = "2025-01-01"
    request["end"] = "2025-12-31"
    adapter = YahooFinanceAdapter(opener=fake_opener)

    adapter.fetch_json(request)

    assert "period1=1735689600" in captured_url
    assert "period2=1767225600" in captured_url
    assert "interval=1d" in captured_url
    assert "range=3mo" not in captured_url


def test_yahoo_finance_adapter_maps_cn_sh_symbol_to_ss() -> None:
    captured_url = ""

    def fake_opener(http_request: Request, *, timeout: float) -> FakeResponse:
        nonlocal captured_url
        captured_url = http_request.full_url
        return FakeResponse(build_chart_payload())

    adapter = YahooFinanceAdapter(opener=fake_opener)

    adapter.fetch_quote(build_request(market="CN", symbol="600519.SH"))

    assert "/chart/600519.SS" in captured_url


def test_yahoo_finance_adapter_maps_hk_five_digit_symbol_to_yahoo_four_digit_symbol() -> None:
    captured_url = ""

    def fake_opener(http_request: Request, *, timeout: float) -> FakeResponse:
        nonlocal captured_url
        captured_url = http_request.full_url
        return FakeResponse(build_chart_payload())

    adapter = YahooFinanceAdapter(opener=fake_opener)

    adapter.fetch_quote(build_request(market="HK", symbol="00700.HK"))

    assert "/chart/0700.HK" in captured_url


def test_yahoo_finance_adapter_keeps_cn_sz_symbol() -> None:
    captured_url = ""

    def fake_opener(http_request: Request, *, timeout: float) -> FakeResponse:
        nonlocal captured_url
        captured_url = http_request.full_url
        return FakeResponse(build_chart_payload())

    adapter = YahooFinanceAdapter(opener=fake_opener)

    adapter.fetch_quote(build_request(market="CN", symbol="300750.SZ"))

    assert "/chart/300750.SZ" in captured_url


def test_yahoo_finance_adapter_can_drive_real_provider() -> None:
    settings = Settings(
        DATA_PROVIDER="real",
        REAL_PROVIDER_NAME="YahooFinance",
        REAL_PROVIDER_BASE_URL="https://query1.finance.yahoo.com",
        REAL_PROVIDER_API_KEY_ENV=None,
        _env_file=None,
    )
    provider = RealMarketDataProvider(
        settings=settings,
        quote_fetcher=YahooFinanceAdapter(opener=lambda *_args, **_kwargs: FakeResponse(build_chart_payload())),
    )

    quote = provider.get_quote(MarketCode.US, "NVDA")
    bars = provider.get_bars(MarketCode.US, "NVDA", count=3)
    status = provider.get_provider_status()

    assert quote["data_status"] == DataStatus.DELAYED
    assert quote["price"] == 183.75
    assert len(bars) == 3
    assert status["ready"] is True
    assert status["source_type"] == "yahoo_finance"
    assert status["active_source"] == "yahoo_finance"


@pytest.mark.parametrize("market,symbol,yahoo_symbol", [
    ("US", "SPX", "^GSPC"), ("US", "NDX", "^NDX"), ("US", "VIX", "^VIX"),
    ("HK", "HSI", "^HSI"), ("CN", "000300.SH", "000300.SS"),
    ("CN", "000001.SH", "000001.SS"), ("CN", "399006.SZ", "399006.SZ"),
])
def test_yahoo_index_symbol_mapping(market: str, symbol: str, yahoo_symbol: str) -> None:
    captured_urls: list[str] = []

    def opener(request: Request, **_kwargs: object) -> FakeResponse:
        captured_urls.append(request.full_url)
        return FakeResponse(build_chart_payload())

    YahooFinanceAdapter(opener=opener).fetch_quote(build_request(market, symbol))
    assert unquote(urlparse(captured_urls[0]).path).endswith(f"/chart/{yahoo_symbol}")


def test_yahoo_daily_change_does_not_use_five_day_window_previous_close() -> None:
    payload = json.loads(build_chart_payload())
    meta = payload["chart"]["result"][0]["meta"]
    meta.pop("previousClose")
    meta["chartPreviousClose"] = 150.0
    meta["regularMarketTime"] = 1704240000
    adapter = YahooFinanceAdapter(opener=lambda *_args, **_kwargs: FakeResponse(json.dumps(payload).encode()))

    quote = adapter.fetch_quote(build_request("US", "SPX"))

    assert quote is not None
    assert quote["change_percent"] == pytest.approx(0)
    assert quote["timestamp"] == "2024-01-03T00:00:00+00:00"


def _index_provider(opener: Callable[..., FakeResponse]) -> RealMarketDataProvider:
    """测试只注入内存响应，不访问真实网络或数据库。"""

    return RealMarketDataProvider(
        Settings(DATA_PROVIDER="real", REAL_PROVIDER_NAME="YahooFinance",
                 REAL_PROVIDER_BASE_URL="https://query1.finance.yahoo.com", _env_file=None),
        quote_fetcher=YahooFinanceAdapter(opener=opener),
    )


@pytest.mark.parametrize("market", list(MarketCode))
def test_real_provider_index_items_keep_their_own_status_and_time(market: MarketCode) -> None:
    provider = _index_provider(lambda *_args, **_kwargs: FakeResponse(build_chart_payload()))
    indices = provider.get_market_indices(market)

    assert len(indices) == 3
    for index in indices:
        assert index["source"] == "yahoo_finance"
        if market == MarketCode.HK and index["symbol"] != "HSI":
            assert index["value"] is None
            assert index["timestamp"] is None
            assert index["data_status"] == DataStatus.UNAVAILABLE
        else:
            assert index["value"] == 183.75
            assert index["data_status"] == DataStatus.DELAYED
            assert index["timestamp"] == datetime(2024, 1, 3, tzinfo=timezone.utc)


def test_one_index_failure_does_not_discard_other_index_quotes() -> None:
    def opener(request: Request, **_kwargs: object) -> FakeResponse:
        if "^NDX" in unquote(request.full_url):
            raise TimeoutError("timeout")
        return FakeResponse(build_chart_payload())

    indices = _index_provider(opener).get_market_indices(MarketCode.US)
    assert indices[0]["value"] == 183.75
    assert indices[1]["value"] is None
    assert indices[1]["data_status"] == DataStatus.UNAVAILABLE
    assert indices[2]["value"] == 183.75


@pytest.mark.parametrize("price", [float("nan"), float("inf"), -1, 0])
def test_invalid_index_price_is_unavailable(price: float) -> None:
    payload = json.loads(build_chart_payload())
    payload["chart"]["result"][0]["meta"]["regularMarketPrice"] = price
    provider = _index_provider(lambda *_args, **_kwargs: FakeResponse(json.dumps(payload).encode()))
    assert all(index["value"] is None for index in provider.get_market_indices(MarketCode.US))


def test_real_indices_without_configuration_do_not_return_mock_values() -> None:
    provider = RealMarketDataProvider(Settings(DATA_PROVIDER="real", REAL_PROVIDER_BASE_URL=None, _env_file=None))
    indices = provider.get_market_indices(MarketCode.US)
    assert all(index["value"] is None and index["data_status"] == DataStatus.UNAVAILABLE for index in indices)


def test_real_provider_marks_breadth_and_sectors_as_mock_fallback() -> None:
    provider = _index_provider(lambda *_args, **_kwargs: FakeResponse(build_chart_payload()))

    breadth = provider.get_market_breadth(MarketCode.US)
    sectors = provider.get_sector_performance(MarketCode.US)

    assert breadth["source"] == "mock_fallback"
    assert breadth["data_status"] == DataStatus.UNAVAILABLE
    assert breadth["timestamp"] is None
    assert all(sector["source"] == "mock_fallback" for sector in sectors)
    assert all(sector["data_status"] == DataStatus.UNAVAILABLE for sector in sectors)


def test_market_service_keeps_each_index_status_instead_of_global_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def opener(request: Request, **_kwargs: object) -> FakeResponse:
        if "^NDX" in unquote(request.full_url):
            raise TimeoutError("timeout")
        return FakeResponse(build_chart_payload())

    provider = _index_provider(opener)
    monkeypatch.setattr("app.services.mock_market_service.get_market_data_provider", lambda: provider)
    response = get_mock_market_overview(MarketCode.US)

    assert response.data_status == DataStatus.DELAYED
    assert response.indices[0].timestamp == datetime(2024, 1, 3, tzinfo=timezone.utc)
    assert response.indices[0].source == "yahoo_finance"
    assert response.indices[1].status == DataStatus.UNAVAILABLE
    assert response.indices[1].value is None
    assert any("NDX" in event.title and "不可用" in event.title for event in response.events)
    assert response.events[0].origin == "system"
    assert any(event.origin == "mock_sample" for event in response.events)


@pytest.mark.parametrize("market", list(MarketCode))
def test_yahoo_overview_starts_indices_and_bars_without_serial_wait(market: MarketCode) -> None:
    """用双向事件证明两组请求重叠，不以机器运行速度断言优化效果。"""

    indices_started = Event()
    bars_started = Event()
    calls: list[str] = []
    lock = Lock()

    def opener(request: Request, **_kwargs: object) -> FakeResponse:
        kind = "bars" if parse_qs(urlparse(request.full_url).query).get("range") == ["3mo"] else "quote"
        with lock:
            calls.append(kind)
        if kind == "bars":
            bars_started.set()
            assert indices_started.wait(3), "index request did not start concurrently"
        else:
            indices_started.set()
            assert bars_started.wait(3), "bars request waited for index requests to finish"
        return FakeResponse(build_chart_payload())

    symbol = {MarketCode.US: "^GSPC", MarketCode.HK: "^HSI", MarketCode.CN: "000300.SS"}[market]
    result = _index_provider(opener).get_market_overview_data(market, symbol)

    assert len(result["indices"]) == 3
    assert len(result["bars"]) == 3
    assert calls.count("bars") == 1
    assert calls.count("quote") == (1 if market == MarketCode.HK else 3)
    assert [index["symbol"] for index in result["indices"]] == [index["symbol"] for index in MockMarketDataProvider().get_market_indices(market)]
    assert all(bar["source"] == "yahoo_finance" and bar["data_status"] == DataStatus.DELAYED for bar in result["bars"])
    assert result["bars"][0]["timestamp"] == "2024-01-01T00:00:00+00:00"


@pytest.mark.parametrize("failed_kind", ["bars", "index"])
def test_parallel_overview_keeps_existing_partial_failure_rules(failed_kind: str) -> None:
    def opener(request: Request, **_kwargs: object) -> FakeResponse:
        is_bars = parse_qs(urlparse(request.full_url).query).get("range") == ["3mo"]
        if (failed_kind == "bars" and is_bars) or (failed_kind == "index" and "^NDX" in unquote(request.full_url)):
            raise TimeoutError("upstream timeout")
        return FakeResponse(build_chart_payload())

    result = _index_provider(opener).get_market_overview_data(MarketCode.US, "^GSPC")
    assert result["indices"][0]["value"] == 183.75
    assert result["indices"][2]["value"] == 183.75
    if failed_kind == "bars":
        assert all(bar["source"] == "mock_fallback" and bar["data_status"] == DataStatus.UNAVAILABLE for bar in result["bars"])
    else:
        assert result["indices"][1]["value"] is None
        assert result["indices"][1]["data_status"] == DataStatus.UNAVAILABLE
        assert all(bar["source"] == "yahoo_finance" for bar in result["bars"])


@pytest.mark.parametrize("market", list(MarketCode))
def test_mock_overview_group_is_equivalent_to_existing_reads(market: MarketCode) -> None:
    provider = MockMarketDataProvider()
    symbol = provider.get_default_stock_symbol(market)
    result = provider.get_market_overview_data(market, symbol, count=12)
    assert result["indices"] == provider.get_market_indices(market)
    assert result["bars"] == provider.get_bars(market, symbol, count=12)


@pytest.mark.parametrize("provider_name,base_url", [("DemoProvider", "https://example.test"), ("YahooFinance", None)])
def test_unverified_or_unconfigured_provider_overview_stays_sequential(provider_name: str, base_url: str | None) -> None:
    provider = RealMarketDataProvider(Settings(DATA_PROVIDER="real", REAL_PROVIDER_NAME=provider_name, REAL_PROVIDER_BASE_URL=base_url, _env_file=None))
    calls: list[str] = []
    provider.get_market_indices = Mock(side_effect=lambda *_args: calls.append("indices") or [])
    provider.get_bars = Mock(side_effect=lambda *_args, **_kwargs: calls.append("bars") or [])
    assert provider.get_market_overview_data(MarketCode.US, "SPX") == {"indices": [], "bars": []}
    assert calls == ["indices", "bars"]


def test_market_service_uses_one_group_read_without_duplicate_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _index_provider(lambda *_args, **_kwargs: FakeResponse(build_chart_payload()))
    group_read = Mock(wraps=provider.get_market_overview_data)
    bars_read = Mock(wraps=provider.get_bars)
    provider.get_market_overview_data = group_read
    provider.get_bars = bars_read
    monkeypatch.setattr("app.services.mock_market_service.get_market_data_provider", lambda: provider)

    response = get_mock_market_overview(MarketCode.US)

    group_read.assert_called_once_with(MarketCode.US, "^GSPC", interval="1d", count=30)
    bars_read.assert_called_once_with(MarketCode.US, "^GSPC", interval="1d", count=30)
    assert len(response.indices) == 3
    assert len(response.chart_bars) == 3
    assert response.chart_bars[0].timestamp == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert all(bar.source == "yahoo_finance" for bar in response.chart_bars)

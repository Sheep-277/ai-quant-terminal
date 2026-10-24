from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, create_autospec

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from app.api.v1.monitor import get_monitor_calculated_signals, parse_monitor_signal_query, router
from app.core.exceptions import ProviderUnavailableError
from app.core.market import MarketCode
from app.providers.base import MarketDataProvider, ProviderBar
from app.schemas.market import DataStatus


def _provider() -> MagicMock:
    """固定公开来源输入，路由测试不访问网络、数据库或真实账户。"""

    provider = create_autospec(MarketDataProvider, instance=True)
    provider.get_provider_status.return_value = {
        "provider_name": "YahooFinance", "mode": "real", "ready": True,
        "fallback_active": False, "fallback_reason": None,
        "active_source": "yahoo_finance", "data_status": DataStatus.DELAYED,
    }
    end = datetime(2026, 1, 1, tzinfo=timezone.utc)
    provider.get_bars.return_value = [ProviderBar(
        offset=30 - index, timestamp=end - timedelta(days=30 - index),
        open=100 + index, high=102 + index, low=99 + index, close=101 + index,
        volume=1000, source="yahoo_finance", data_status=DataStatus.DELAYED,
    ) for index in range(31)]
    return provider


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    result = _provider()
    monkeypatch.setattr("app.api.v1.monitor.get_market_data_provider", lambda: result)
    return result


@pytest.mark.parametrize("market, symbol, currency", [
    (MarketCode.US, " nvda ", "USD"),
    (MarketCode.HK, "00700.HK", "HKD"),
    (MarketCode.CN, "300750.SZ", "CNY"),
])
def test_calculation_route_preserves_input_provenance(provider: MagicMock, market: MarketCode, symbol: str, currency: str) -> None:
    query = parse_monitor_signal_query(market=market, symbol=symbol)
    payload = get_monitor_calculated_signals(query).model_dump(mode="json")
    assert payload["market"] == market.value
    assert payload["symbol"] == symbol.strip().upper()
    assert payload["currency"] == currency
    assert payload["source"] == "yahoo_finance"
    assert payload["data_status"] == "delayed"
    assert payload["timestamp"] == "2026-01-01T00:00:00Z"
    assert payload["bar_count"] == 31
    assert payload["calculation_scope"] == "price_only"
    assert payload["signals"]
    assert all(set(signal) == {"code", "title", "direction", "severity", "score", "evidence"} for signal in payload["signals"])
    assert "stream" not in payload and "events" not in payload
    provider.get_bars.assert_called_once_with(market, query.symbol, interval="1d", count=40)
    provider.get_financials.assert_not_called()


@pytest.mark.parametrize("symbol", ["", "  ", "bad/symbol", "A" * 33])
def test_invalid_symbol_is_a_query_validation_error(symbol: str) -> None:
    with pytest.raises(RequestValidationError) as error:
        parse_monitor_signal_query(market=MarketCode.US, symbol=symbol)
    assert error.value.errors()[0]["loc"] == ("query", "symbol")


def test_openapi_requires_market_and_symbol_without_changing_stream() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    paths = app.openapi()["paths"]
    parameters = paths["/api/v1/monitor/signals"]["get"]["parameters"]
    assert {item["name"] for item in parameters if item["required"]} == {"market", "symbol"}
    assert paths["/api/v1/monitor/stream"]["get"]["parameters"][0]["required"] is False


@pytest.mark.parametrize("error", [
    ValueError("secret provider url"),
    ProviderUnavailableError("secret API key"),
    TimeoutError("secret timeout url"),
])
def test_data_errors_return_503_without_leaking_provider_details(provider: MagicMock, error: Exception) -> None:
    provider.get_bars.side_effect = error
    with pytest.raises(HTTPException) as raised:
        get_monitor_calculated_signals(parse_monitor_signal_query(market=MarketCode.US, symbol="NVDA"))
    assert raised.value.status_code == 503
    assert raised.value.detail["code"] == "monitor_public_data_unavailable"
    assert "secret" not in str(raised.value.detail)


def test_mock_fallback_cannot_be_returned_as_calculated_public_signals(provider: MagicMock) -> None:
    provider.get_bars.return_value[-1]["source"] = "mock_fallback"
    with pytest.raises(HTTPException) as error:
        get_monitor_calculated_signals(parse_monitor_signal_query(market=MarketCode.US, symbol="NVDA"))
    assert error.value.status_code == 503


def test_empty_signals_remain_successful_without_replacement(provider: MagicMock) -> None:
    for bar in provider.get_bars.return_value:
        bar.update(open=100, high=100, low=100, close=100)
    payload = get_monitor_calculated_signals(parse_monitor_signal_query(market=MarketCode.US, symbol="NVDA"))
    assert payload.signals == []
    assert payload.timestamp == datetime(2026, 1, 1, tzinfo=timezone.utc)

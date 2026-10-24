from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, create_autospec, patch

import pytest

from app.core.market import MarketCode
from app.providers.base import MarketDataProvider, ProviderBar
from app.quant.pipeline import QuantPipelineInput, run_quant_pipeline
from app.schemas.market import DataStatus
from app.services.monitor_signal_service import calculate_monitor_signals


OBSERVED_AT = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)


def _bars() -> list[ProviderBar]:
    """构造带明确时间和来源的测试行情，不请求网络。"""

    return [ProviderBar(
        offset=30 - index,
        timestamp=OBSERVED_AT - timedelta(days=31 - index),
        source="yahoo_finance",
        data_status=DataStatus.DELAYED,
        open=100.0 + index,
        high=102.0 + index,
        low=99.0 + index,
        close=101.0 + index,
        volume=1000,
    ) for index in range(31)]


def _provider() -> MagicMock:
    """模拟抽象 Provider，阻止测试意外调用真实网络。"""

    provider = create_autospec(MarketDataProvider, instance=True)
    provider.get_provider_status.return_value = {
        "provider_name": "YahooFinance", "mode": "real", "ready": True,
        "data_status": DataStatus.DELAYED, "fallback_active": False,
        "fallback_reason": None, "active_source": "yahoo_finance",
    }
    provider.get_bars.return_value = _bars()
    return provider


@pytest.mark.parametrize("market, symbol, currency", [
    (MarketCode.US, " nvda ", "USD"),
    (MarketCode.HK, "00700.HK", "HKD"),
    (MarketCode.CN, "300750.SZ", "CNY"),
])
def test_monitor_signal_calculation_uses_explicit_market_and_public_prices(market: MarketCode, symbol: str, currency: str) -> None:
    provider = _provider()
    original = deepcopy(provider.get_bars.return_value)
    snapshot = calculate_monitor_signals(market, symbol, provider=provider, observed_at=OBSERVED_AT)
    expected = run_quant_pipeline(QuantPipelineInput(symbol=symbol.strip().upper(), closes=[bar["close"] for bar in original]))
    assert snapshot.result == expected
    assert snapshot.market == market
    assert snapshot.currency == currency
    assert snapshot.source == "yahoo_finance"
    assert snapshot.data_status == DataStatus.DELAYED
    assert snapshot.timestamp == original[-1]["timestamp"]
    assert snapshot.bar_count == 31
    assert snapshot.result.factors.quality_score is None
    provider.get_bars.assert_called_once_with(market, symbol.strip().upper(), interval="1d", count=40)
    provider.get_quote.assert_not_called()
    provider.get_financials.assert_not_called()
    assert provider.get_bars.return_value == original
    assert calculate_monitor_signals(market, symbol, provider=provider, observed_at=OBSERVED_AT) == snapshot


@pytest.mark.parametrize("update", [
    {"mode": "mock"}, {"ready": False}, {"fallback_active": True},
    {"active_source": "demo_provider"}, {"active_source": "mock_fallback"},
])
def test_unverified_provider_is_rejected_before_request(update: dict[str, object]) -> None:
    provider = _provider()
    provider.get_provider_status.return_value.update(update)
    with pytest.raises(ValueError):
        calculate_monitor_signals(MarketCode.US, "NVDA", provider=provider, observed_at=OBSERVED_AT)
    provider.get_bars.assert_not_called()


@pytest.mark.parametrize("change", [
    {"source": "mock_fallback"}, {"source": "mock_seed"}, {"source": "demo_provider"},
    {"data_status": DataStatus.UNAVAILABLE}, {"data_status": None},
    {"timestamp": None}, {"timestamp": OBSERVED_AT.replace(tzinfo=None)},
    {"timestamp": OBSERVED_AT + timedelta(days=1)},
    {"close": float("nan")}, {"high": 1.0}, {"volume": -1},
])
def test_invalid_bars_do_not_reach_quant_pipeline(change: dict[str, object]) -> None:
    provider = _provider()
    provider.get_bars.return_value[-1].update(change)
    with patch("app.services.monitor_signal_service.run_quant_pipeline") as pipeline:
        with pytest.raises(ValueError):
            calculate_monitor_signals(MarketCode.US, "NVDA", provider=provider, observed_at=OBSERVED_AT)
        pipeline.assert_not_called()


@pytest.mark.parametrize("bars", [[], _bars()[:20], list(reversed(_bars())), [*_bars(), _bars()[-1]]])
def test_short_or_unordered_series_is_not_repaired(bars: list[ProviderBar]) -> None:
    provider = _provider()
    provider.get_bars.return_value = bars
    with pytest.raises(ValueError):
        calculate_monitor_signals(MarketCode.US, "NVDA", provider=provider, observed_at=OBSERVED_AT)


def test_twenty_one_bars_are_sufficient_without_fundamentals() -> None:
    provider = _provider()
    provider.get_bars.return_value = _bars()[:21]
    snapshot = calculate_monitor_signals(MarketCode.US, "NVDA", provider=provider, observed_at=OBSERVED_AT)
    assert snapshot.result.factors.momentum_20d is not None
    assert snapshot.result.factors.volatility_20d is not None
    assert snapshot.result.factors.quality_score is None


def test_no_signals_is_a_valid_result_not_a_mock_substitution() -> None:
    provider = _provider()
    for bar in provider.get_bars.return_value:
        bar.update(open=100, high=100, low=100, close=100)
    snapshot = calculate_monitor_signals(MarketCode.US, "NVDA", provider=provider, observed_at=OBSERVED_AT)
    assert snapshot.result.signals == []


def test_provider_error_propagates_without_mock_substitution() -> None:
    provider = _provider()
    provider.get_bars.side_effect = RuntimeError("provider timeout")
    with pytest.raises(RuntimeError, match="provider timeout"):
        calculate_monitor_signals(MarketCode.US, "NVDA", provider=provider, observed_at=OBSERVED_AT)


@pytest.mark.parametrize("symbol, observed_at", [(" ", OBSERVED_AT), ("bad/symbol", OBSERVED_AT), ("NVDA", OBSERVED_AT.replace(tzinfo=None))])
def test_invalid_request_does_not_fetch_prices(symbol: str, observed_at: datetime) -> None:
    provider = _provider()
    with pytest.raises(ValueError):
        calculate_monitor_signals(MarketCode.US, symbol, provider=provider, observed_at=observed_at)
    provider.get_bars.assert_not_called()


@pytest.mark.parametrize("field", ["timestamp", "source", "data_status"])
def test_missing_bar_metadata_is_not_guessed(field: str) -> None:
    provider = _provider()
    provider.get_bars.return_value[-1].pop(field)
    with pytest.raises(ValueError):
        calculate_monitor_signals(MarketCode.US, "NVDA", provider=provider, observed_at=OBSERVED_AT)


def test_delayed_bar_prevents_claiming_realtime_series() -> None:
    provider = _provider()
    for bar in provider.get_bars.return_value:
        bar["data_status"] = DataStatus.REALTIME
    provider.get_bars.return_value[0]["data_status"] = DataStatus.DELAYED
    snapshot = calculate_monitor_signals(MarketCode.US, "NVDA", provider=provider, observed_at=OBSERVED_AT)
    assert snapshot.data_status == DataStatus.DELAYED

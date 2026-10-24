"""报价和 K 线可独立失败，来源及派生状态必须跟随实际 K 线。"""

from datetime import datetime, timezone

import pytest

from app.core.config import Settings
from app.core.market import MarketCode
from app.providers.base import ProviderBar
from app.providers.market_data import MockMarketDataProvider
from app.providers.real_market_data import RealMarketDataProvider
from app.schemas.market import DataStatus
from app.services.kline_read_service import KLineReadSnapshot
from app.services.mock_stock_service import get_mock_stock_research


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> RealMarketDataProvider:
    """只替换网络读取边界，仍执行真实 Provider 的归一化和失败回退。"""

    instance = RealMarketDataProvider(settings=Settings(
        DATA_PROVIDER="real", REAL_PROVIDER_NAME="YahooFinance",
        REAL_PROVIDER_BASE_URL="https://provider.example.test",
        REAL_PROVIDER_API_KEY_ENV="", _env_file=None,
    ))
    monkeypatch.setattr("app.services.mock_stock_service.get_market_data_provider", lambda: instance)
    return instance


def _raw_bars() -> list[ProviderBar]:
    """构造有足够样本计算指标的本地 K 线，不发起网络请求。"""

    return MockMarketDataProvider().get_bars(MarketCode.US, "NVDA", count=40)


def _raw_quote() -> dict[str, object]:
    return {
        **MockMarketDataProvider().get_quote(MarketCode.US, "NVDA"),
        "timestamp": datetime(2026, 10, 16, 20, tzinfo=timezone.utc),
    }


@pytest.mark.parametrize("market", list(MarketCode))
@pytest.mark.parametrize(("quote_ok", "bars_ok"), [(True, False), (False, True), (True, True), (False, False)])
def test_quote_and_kline_fail_independently(
    monkeypatch: pytest.MonkeyPatch,
    provider: RealMarketDataProvider,
    market: MarketCode,
    quote_ok: bool,
    bars_ok: bool,
) -> None:
    """真实报价不能掩盖 K 线回退，报价失败也不能污染成功的 K 线。"""

    monkeypatch.setattr(provider, "_fetch_quote_response", lambda request: _raw_quote() if quote_ok else None)
    monkeypatch.setattr(provider, "_fetch_bars_response", lambda request: _raw_bars() if bars_ok else None)
    response = get_mock_stock_research(market, provider.get_default_stock_symbol(market))
    expected_status = DataStatus.DELAYED if bars_ok else DataStatus.UNAVAILABLE

    assert response.quote_data_source.source == ("yahoo_finance" if quote_ok else "mock_fallback")
    assert response.quote_data_source.fallback_active is (not quote_ok)
    assert response.kline_data_source.source == ("yahoo_finance" if bars_ok else "mock_provider")
    assert response.kline_data_source.fallback_active is (not bars_ok)
    assert response.kline.data_status == expected_status
    assert response.kline_data_source.data_status == expected_status
    assert len(response.kline.bars) == 30
    for source in (response.technical_data_source, response.summary_data_source):
        assert source.source == "quant_pipeline"
        assert source.fallback_active is (not bars_ok)
        assert source.data_status == expected_status
    assert any("K 线读取已回退" in flag for flag in response.risk_flags) is (not bars_ok)


def test_database_kline_keeps_its_own_status(
    monkeypatch: pytest.MonkeyPatch, provider: RealMarketDataProvider,
) -> None:
    """数据库 K 线优先，不因 Provider 报价失败而变成 Mock 回退。"""

    monkeypatch.setattr(provider, "_fetch_quote_response", lambda request: None)
    monkeypatch.setattr(provider, "_fetch_bars_response", lambda request: _raw_bars())
    baseline = get_mock_stock_research(MarketCode.US, "NVDA")
    snapshot = KLineReadSnapshot(kline=baseline.kline, source="database")

    def unexpected_bars_read(*args, **kwargs):
        raise AssertionError("数据库 K 线已存在，不应读取 Provider K 线")

    monkeypatch.setattr(provider, "get_bars", unexpected_bars_read)
    response = get_mock_stock_research(MarketCode.US, "NVDA", kline_read_snapshot=snapshot)
    assert response.kline_data_source.source == "database"
    assert response.kline_data_source.fallback_active is False
    assert response.kline.data_status == DataStatus.DELAYED
    assert response.summary_data_source.fallback_active is False


@pytest.mark.parametrize("missing_field", ["source", "data_status"])
def test_missing_real_bar_metadata_is_not_assumed_successful(
    monkeypatch: pytest.MonkeyPatch,
    provider: RealMarketDataProvider,
    missing_field: str,
) -> None:
    """元数据缺失时标记不可用，不根据正常报价宣称 K 线可用。"""

    monkeypatch.setattr(provider, "_fetch_quote_response", lambda request: _raw_quote())
    bars = [{**bar, "source": "yahoo_finance", "data_status": DataStatus.DELAYED} for bar in _raw_bars()]
    bars[-1].pop(missing_field)
    monkeypatch.setattr(provider, "get_bars", lambda *args, **kwargs: bars)
    response = get_mock_stock_research(MarketCode.US, "NVDA")
    assert response.kline.data_status == DataStatus.UNAVAILABLE
    assert response.summary_data_source.data_status == DataStatus.UNAVAILABLE
    assert response.quote_data_source.data_status == DataStatus.DELAYED


@pytest.mark.parametrize(("fallback_index", "expected_fallback"), [(0, False), (-1, True)])
def test_only_displayed_bars_determine_fallback_state(
    monkeypatch: pytest.MonkeyPatch,
    provider: RealMarketDataProvider,
    fallback_index: int,
    expected_fallback: bool,
) -> None:
    """只检查图中最近 30 根，图外旧样例不能污染当前来源；图内回退不能被掩盖。"""

    monkeypatch.setattr(provider, "_fetch_quote_response", lambda request: _raw_quote())
    bars = [{**bar, "source": "yahoo_finance", "data_status": DataStatus.DELAYED} for bar in _raw_bars()]
    bars[fallback_index].update(source="mock_fallback", data_status=DataStatus.UNAVAILABLE)
    monkeypatch.setattr(provider, "get_bars", lambda *args, **kwargs: bars)
    response = get_mock_stock_research(MarketCode.US, "NVDA")
    assert response.kline_data_source.fallback_active is expected_fallback
    assert response.technical_data_source.fallback_active is expected_fallback

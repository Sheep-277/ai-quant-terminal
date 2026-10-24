"""个股风险提示只使用当前量化证据和数据状态。"""

import pytest

from app.core.market import MarketCode
from app.providers.market_data import MockMarketDataProvider
from app.schemas.market import DataStatus
from app.services.mock_stock_service import get_mock_stock_research
from app.services.stock_fundamental_read_service import StockFundamentalReadSnapshot


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> MockMarketDataProvider:
    """隔离本地运行配置，不读取真实供应商或数据库。"""

    mock = MockMarketDataProvider()
    monkeypatch.setattr("app.services.mock_stock_service.get_market_data_provider", lambda: mock)
    return mock


@pytest.mark.parametrize("market", list(MarketCode))
def test_risks_exclude_fixture_opinions_but_keep_sample_boundaries(
    provider: MockMarketDataProvider, market: MarketCode,
) -> None:
    """样例估值、行业评语不应作为当前风险证据。"""

    symbol = provider.get_default_stock_symbol(market)
    response = get_mock_stock_research(market, symbol)
    fixture_flags = provider.get_research_notes(market, symbol)["risk_flags"]
    assert all(flag not in response.risk_flags for flag in fixture_flags)
    assert "最新行情为样例数据，不能作为真实交易依据。" in response.risk_flags
    assert "K 线为样例数据，不能作为真实交易依据。" in response.risk_flags
    assert any("基本面为 Mock 样例" in flag for flag in response.risk_flags)


@pytest.mark.parametrize(
    ("closes", "expected_title"),
    [
        ([100.0 - index for index in range(40)], "20 日动量转弱"),
        ([100.0, 160.0] * 20, "20 日年化波动率升高"),
        ([100.0 + index for index in range(40)], None),
        ([100.0] * 40, None),
    ],
)
def test_current_signals_control_risks_and_preserve_numeric_evidence(
    monkeypatch: pytest.MonkeyPatch,
    provider: MockMarketDataProvider,
    closes: list[float],
    expected_title: str | None,
) -> None:
    """价格走弱或高波动时才出现对应提示，不改变原有信号阈值。"""

    bars = [
        {"offset": len(closes) - index - 1, "open": close, "high": close + 1,
         "low": close - 1, "close": close, "volume": 1000}
        for index, close in enumerate(closes)
    ]
    monkeypatch.setattr(provider, "get_bars", lambda *args, **kwargs: bars)
    response = get_mock_stock_research(MarketCode.US, "NVDA")
    adverse_signals = [signal for signal in response.quant_signals if signal.direction.value in ("negative", "warning")]
    expected_flags = [f"{signal.title}：{'；'.join(signal.evidence)}" for signal in adverse_signals]
    assert response.risk_flags[3:] == expected_flags
    if expected_title:
        assert any(flag.startswith(expected_title + "：") for flag in expected_flags)
    else:
        assert expected_flags == []


@pytest.mark.parametrize("status", [DataStatus.DELAYED, DataStatus.UNAVAILABLE])
def test_public_quote_delay_and_fallback_remain_visible(
    monkeypatch: pytest.MonkeyPatch,
    provider: MockMarketDataProvider,
    status: DataStatus,
) -> None:
    """去掉样例评语不能去掉公开行情延迟或回退警告。"""

    quote = {**provider.get_quote(MarketCode.US, "NVDA"), "data_status": status}
    monkeypatch.setattr(provider, "get_quote", lambda *args: quote)
    monkeypatch.setattr(provider, "get_provider_status", lambda: {
        "provider_name": "YahooFinance", "mode": "real", "ready": True,
        "data_status": status, "fallback_active": False, "fallback_reason": None,
        "source_type": "yahoo_finance", "active_source": "yahoo_finance",
    })
    response = get_mock_stock_research(MarketCode.US, "NVDA")
    expected = "最新行情存在延迟，不代表实时行情。" if status == DataStatus.DELAYED else "最新行情读取已回退到样例数据，不能作为真实交易依据。"
    assert expected in response.risk_flags
    assert "估值处于高位" not in response.risk_flags


def test_unknown_symbol_keeps_fallback_explanation(provider: MockMarketDataProvider) -> None:
    """保留标的回退提示，且不带入默认标的的行业判断。"""

    response = get_mock_stock_research(MarketCode.HK, "09988.HK")
    assert "09988.HK 暂未覆盖 Mock 数据" in response.risk_flags[0]
    assert "互联网板块受政策和流动性影响较大" not in response.risk_flags


def test_partial_fundamentals_get_a_missing_data_warning(provider: MockMarketDataProvider) -> None:
    """不完整的数据库基本面不能继续被标为完整实值分析。"""

    baseline = get_mock_stock_research(MarketCode.US, "NVDA")
    snapshot = StockFundamentalReadSnapshot(
        valuation=baseline.valuation, profitability=baseline.profitability,
        cash_flow=baseline.cash_flow, source="database", completeness="partial",
        available_sections=("profitability", "cash_flow"), missing_sections=("valuation",),
    )
    response = get_mock_stock_research(MarketCode.US, "NVDA", fundamental_read_snapshot=snapshot)
    assert any("基本面数据不完整" in flag for flag in response.risk_flags)
    assert not any("基本面为 Mock 样例" in flag for flag in response.risk_flags)

"""个股摘要必须跟随实际计算输入，不能混入固定样例结论。"""

import pytest

from app.core.market import MarketCode
from app.providers.market_data import MockMarketDataProvider
from app.quant.pipeline import QuantPipelineInput, run_quant_pipeline
from app.services.mock_stock_service import get_mock_stock_research


@pytest.mark.parametrize("step", [-1.0, 0.0, 1.0])
def test_summary_uses_current_bars_without_fixture_opinions(
    monkeypatch: pytest.MonkeyPatch, step: float,
) -> None:
    """上涨、下跌及横盘输入都只能产生与当前计算一致的摘要。"""

    provider = MockMarketDataProvider()
    closes = [100.0 + step * index for index in range(40)]
    bars = [
        {
            "offset": len(closes) - index - 1,
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1000,
        }
        for index, close in enumerate(closes)
    ]
    monkeypatch.setattr(provider, "get_bars", lambda *args, **kwargs: bars)
    monkeypatch.setattr(
        "app.services.mock_stock_service.get_market_data_provider", lambda: provider,
    )

    response = get_mock_stock_research(MarketCode.US, "NVDA")
    expected = run_quant_pipeline(QuantPipelineInput(symbol="NVDA", closes=closes[-30:]))

    assert expected.factors.momentum_20d is not None
    assert expected.factors.trend_strength is not None
    assert response.factor_snapshot.composite_score is not None
    assert response.factor_snapshot.quality_score is not None
    assert response.summary_points == [
        f"20 日动量为 {expected.factors.momentum_20d * 100:.2f}%，"
        f"趋势强度为 {expected.factors.trend_strength * 100:.2f}%。",
        f"综合因子评分为 {response.factor_snapshot.composite_score:.2f}，"
        f"质量评分为 {response.factor_snapshot.quality_score:.2f}。",
    ]
    assert response.summary_data_source.source == "quant_pipeline"


def test_summary_keeps_unknown_symbol_warning_without_fixture_opinions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """移除样例评语时不能一并删除跨标的回退说明。"""

    provider = MockMarketDataProvider()
    monkeypatch.setattr(
        "app.services.mock_stock_service.get_market_data_provider", lambda: provider,
    )

    response = get_mock_stock_research(MarketCode.HK, "09988.HK")

    assert len(response.summary_points) == 3
    assert "使用 00700.HK 的示例数据" in response.summary_points[2]
    fixture_points = provider.get_research_notes(MarketCode.HK, "09988.HK")["summary_points"]
    assert all(point not in response.summary_points for point in fixture_points)

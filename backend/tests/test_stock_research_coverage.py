"""历史行情不足时，个股研究必须说明计算覆盖范围。"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.market import MarketCode
from app.providers.market_data import MockMarketDataProvider
from app.schemas.market import DataStatus, Direction
from app.schemas.stock import KLineBar, KLineInterval, KLineSeries
from app.services.kline_read_service import KLineReadSnapshot
from app.services.mock_stock_service import get_mock_stock_research


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> MockMarketDataProvider:
    """隔离外部行情和本地环境配置。"""

    mock = MockMarketDataProvider()
    monkeypatch.setattr("app.services.mock_stock_service.get_market_data_provider", lambda: mock)
    return mock


@pytest.mark.parametrize("market", list(MarketCode))
@pytest.mark.parametrize("count", [0, 1, 19, 20, 21, 30])
def test_price_factor_coverage_is_visible_and_recovers(
    provider: MockMarketDataProvider, market: MarketCode, count: int,
) -> None:
    """空行情、窗口边界和充分样本都保留真实计算值与相应说明。"""

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = [
        KLineBar(
            timestamp=start + timedelta(days=index), open=100 + index,
            high=102 + index, low=99 + index, close=101 + index, volume=1000,
        )
        for index in range(count)
    ]
    snapshot = KLineReadSnapshot(
        kline=KLineSeries(
            interval=KLineInterval.ONE_DAY,
            data_status=DataStatus.DELAYED if bars else DataStatus.UNAVAILABLE,
            bars=bars,
        ),
        source="database",
    )
    symbol = provider.get_default_stock_symbol(market)
    response = get_mock_stock_research(market, symbol, kline_read_snapshot=snapshot)
    incomplete = count <= 20
    warnings = [point for point in response.summary_points if "不代表完整趋势分析" in point]
    assert bool(warnings) is incomplete
    assert response.factor_snapshot.quality_score is not None
    assert (response.factor_snapshot.momentum_20d is None) is incomplete
    assert (response.factor_snapshot.trend_strength is None) is (count < 20)
    if incomplete:
        assert warnings[0] in response.risk_flags
        for signal in response.quant_signals:
            assert warnings[0] in signal.evidence
            assert any("=" in item for item in signal.evidence)
    else:
        assert not any("不代表完整趋势分析" in flag for flag in response.risk_flags)
        assert all(not any("不代表完整趋势分析" in item for item in signal.evidence) for signal in response.quant_signals)
    assert response.quote.price > 0
    assert len(snapshot.kline.bars) == count


@pytest.mark.parametrize("fixture_direction", [Direction.POSITIVE, Direction.NEGATIVE])
def test_no_signal_does_not_inherit_fixture_direction(
    monkeypatch: pytest.MonkeyPatch, provider: MockMarketDataProvider,
    fixture_direction: Direction,
) -> None:
    """价格和财务均无计算输入时，预置多空判断不能代替量化证据。"""

    financials = provider.get_financials(MarketCode.US, "NVDA")
    notes = provider.get_research_notes(MarketCode.US, "NVDA")
    monkeypatch.setattr(provider, "get_financials", lambda *args: dict.fromkeys(financials))
    monkeypatch.setattr(provider, "get_research_notes", lambda *args: {**notes, "direction": fixture_direction})
    snapshot = KLineReadSnapshot(
        kline=KLineSeries(interval=KLineInterval.ONE_DAY, data_status=DataStatus.UNAVAILABLE, bars=[]),
        source="database",
    )
    response = get_mock_stock_research(MarketCode.US, "NVDA", kline_read_snapshot=snapshot)
    assert response.quant_signals == []
    assert response.direction == Direction.NEUTRAL
    assert response.factor_snapshot.composite_score is None
    assert any("不代表完整趋势分析" in point for point in response.summary_points)

import json
from unittest.mock import Mock

import pytest

from app.core.config import Settings
from app.core.exceptions import ProviderResponseError
from app.core.market import MarketCode
from app.providers.real_market_data import RealMarketDataProvider
from app.providers.tencent_index_adapter import TencentIndexAdapter
from app.schemas.market import DataStatus


ROWS = [
    ["2026-10-23", "4000", "4020", "4030", "3990", "1000"],
    ["2026-10-26", "4020", "4100", "4110", "4010", "2000"],
]


def adapter_for(rows: object, *, code: int = 0) -> tuple[TencentIndexAdapter, Mock]:
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = json.dumps({"code": code, "data": {"sh000300": {"day": rows}}}).encode()
    opener = Mock(return_value=response)
    return TencentIndexAdapter(opener=opener), opener


def test_tencent_daily_mapping_preserves_trading_date_and_source() -> None:
    adapter, opener = adapter_for(list(reversed(ROWS)))
    bars = adapter.fetch_bars(MarketCode.CN, "000300.SH", count=2)
    assert len(bars) == 2
    assert bars[0]["open"] == 4000
    assert bars[0]["close"] == 4020
    assert bars[0]["high"] == 4030
    assert bars[0]["low"] == 3990
    assert bars[0]["volume"] == 1000
    assert bars[0]["timestamp"].isoformat() == "2026-10-23T00:00:00+08:00"
    assert [bar["offset"] for bar in bars] == [1, 0]
    assert all(bar["source"] == "tencent_finance" and bar["data_status"] == DataStatus.DELAYED for bar in bars)
    opener.assert_called_once()
    assert "sh000300" in opener.call_args.args[0].full_url


@pytest.mark.parametrize("rows", [[], ROWS[:1], ROWS * 2, None,
    [["invalid", "1", "2", "3", "1", "0"]],
    [ROWS[0], ["2026-10-26", "4020", "4100", "4000", "4010", "2000"]],
    [ROWS[0], ["2026-10-26", "4020", "nan", "4110", "4010", "2000"]],
    [ROWS[0], ["2026-10-26", "4020", "4100", "4110", "4010", "-1"]],
    [ROWS[0], ["2026-10-26", "4020", "4100", "4110", "4010", "2.5"]],
    [ROWS[0], ["2026-10-26", True, "4100", "4110", "4010", "2000"]],
])
def test_invalid_tencent_history_is_rejected_without_retry(rows: object) -> None:
    adapter, opener = adapter_for(rows)
    with pytest.raises(ProviderResponseError):
        adapter.fetch_bars(MarketCode.CN, "000300.SH")
    opener.assert_called_once()


def test_network_error_does_not_retry() -> None:
    adapter, opener = adapter_for(ROWS)
    opener.side_effect = TimeoutError()
    with pytest.raises(ProviderResponseError):
        adapter.fetch_bars(MarketCode.CN, "000300.SH")
    opener.assert_called_once()


@pytest.mark.parametrize("market,symbol", [(MarketCode.HK, "000300.SH"), (MarketCode.US, "NVDA"), (MarketCode.CN, "600519.SH")])
def test_only_explicit_cn_csi300_is_allowed(market: MarketCode, symbol: str) -> None:
    adapter, opener = adapter_for(ROWS)
    with pytest.raises(ValueError):
        adapter.fetch_bars(market, symbol)
    opener.assert_not_called()


@pytest.mark.parametrize("market,symbol,interval,points,failed,expected", [
    (MarketCode.CN, "000300.SH", "1d", 1, False, True),
    (MarketCode.CN, "000300.SS", "1d", 1, False, True),
    (MarketCode.CN, "000300.SH", "1d", 1, True, True),
    (MarketCode.CN, "000300.SH", "1d", 2, False, False),
    (MarketCode.HK, "HSI", "1d", 1, False, False),
    (MarketCode.US, "^GSPC", "1d", 1, False, False),
    (MarketCode.CN, "600519.SH", "1d", 1, False, False),
    (MarketCode.CN, "000300.SH", "1h", 1, False, False),
])
def test_overview_uses_backup_only_for_insufficient_cn_index(
    market: MarketCode, symbol: str, interval: str, points: int, failed: bool, expected: bool,
) -> None:
    backup = Mock(spec=TencentIndexAdapter)
    replacement, _ = adapter_for(ROWS)
    backup.fetch_bars.return_value = replacement.fetch_bars(MarketCode.CN, "000300.SH")
    if failed:
        backup.fetch_bars.side_effect = ProviderResponseError("unavailable")
    provider = RealMarketDataProvider(
        Settings(DATA_PROVIDER="real", REAL_PROVIDER_NAME="YahooFinance", REAL_PROVIDER_BASE_URL="https://query1.finance.yahoo.com", _env_file=None),
        index_history_adapter=backup,
    )
    original = [
        {"offset": index, "timestamp": f"2026-10-{23 + index}T00:00:00+08:00", "open": 100.0,
         "high": 100.0, "low": 100.0, "close": 100.0, "volume": 1000,
         "source": "yahoo_finance", "data_status": DataStatus.DELAYED}
        for index in range(points)
    ]
    provider.get_bars = Mock(return_value=original)
    provider.get_market_indices = Mock(return_value=[])
    result = provider.get_market_overview_data(market, symbol, interval=interval)
    if expected:
        backup.fetch_bars.assert_called_once_with(market, "000300.SH", count=30)
    else:
        backup.fetch_bars.assert_not_called()
    assert result["bars"] == (backup.fetch_bars.return_value if expected and not failed else original)

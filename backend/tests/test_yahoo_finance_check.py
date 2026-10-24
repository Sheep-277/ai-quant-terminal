import json
from unittest.mock import Mock

import pytest

from app.core.exceptions import ProviderResponseError
from app.core.market import MarketCode
from app.providers import yahoo_finance_check as check
from app.providers.yahoo_finance_adapter import YahooFinanceAdapter


@pytest.fixture
def adapter(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """内存响应替代网络，不访问数据库或读取密钥。"""

    fake = Mock(spec=YahooFinanceAdapter)
    monkeypatch.setattr(check, "YahooFinanceAdapter", lambda: fake)
    return fake


@pytest.mark.parametrize("market,symbol", [(MarketCode.US, " nvda "), (MarketCode.HK, "00700.HK"), (MarketCode.CN, "600519.SH")])
def test_quote_check_keeps_market_and_normalizes_symbol(adapter: Mock, monkeypatch: pytest.MonkeyPatch, market: MarketCode, symbol: str) -> None:
    adapter.fetch_quote.return_value = {"price": 123.0}
    ticks = iter([10.0, 10.25])
    monkeypatch.setattr(check, "perf_counter", lambda: next(ticks))
    report = check.check_yahoo_finance(market=market, symbol=symbol, kind="quote")
    assert report == {"market": market.value, "symbol": symbol.strip().upper(), "kind": "quote", "ok": True, "elapsed_ms": 250.0, "item_count": 1, "error_type": None}
    adapter.fetch_quote.assert_called_once()
    request = adapter.fetch_quote.call_args.args[0]
    assert request["market"] == market.value
    assert request["symbol"] == symbol.strip().upper()
    assert request["api_key_configured"] is False
    adapter.fetch_json.assert_not_called()


def test_bars_check_does_not_print_payload(adapter: Mock) -> None:
    adapter.fetch_json.return_value = [{"timestamp": "private-payload"}, {}]
    report = check.check_yahoo_finance(market=MarketCode.US, symbol="NVDA", kind="bars")
    assert report["ok"] is True
    assert report["item_count"] == 2
    assert "private-payload" not in json.dumps(report)
    adapter.fetch_json.assert_called_once()
    adapter.fetch_quote.assert_not_called()


@pytest.mark.parametrize("error", [ProviderResponseError("private-detail"), TimeoutError("private-detail"), UnicodeError("private-detail"), ValueError("private-detail")])
def test_failure_does_not_retry_or_print_raw_error(adapter: Mock, error: Exception) -> None:
    adapter.fetch_quote.side_effect = error
    report = check.check_yahoo_finance(market=MarketCode.US, symbol="NVDA", kind="quote")
    assert report["ok"] is False
    assert report["item_count"] == 0
    assert report["error_type"] == type(error).__name__
    assert "private-detail" not in json.dumps(report)
    adapter.fetch_quote.assert_called_once()


@pytest.mark.parametrize("kind,payload", [("quote", None), ("bars", []), ("bars", None)])
def test_missing_data_is_not_success(adapter: Mock, kind: check.ReadKind, payload: object) -> None:
    adapter.fetch_quote.return_value = payload
    adapter.fetch_json.return_value = payload
    report = check.check_yahoo_finance(market=MarketCode.US, symbol="NVDA", kind=kind)
    assert report["ok"] is False
    assert report["item_count"] == 0


@pytest.mark.parametrize("symbol", ["", "  ", "NVDA?token=secret", "A" * 33])
def test_invalid_symbol_does_not_call_network(adapter: Mock, symbol: str) -> None:
    with pytest.raises(ValueError):
        check.check_yahoo_finance(market=MarketCode.US, symbol=symbol, kind="quote")
    adapter.fetch_quote.assert_not_called()
    adapter.fetch_json.assert_not_called()


@pytest.mark.parametrize("ok,exit_code", [(True, 0), (False, 1)])
def test_cli_exit_status(adapter: Mock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], ok: bool, exit_code: int) -> None:
    monkeypatch.setattr(check.logging, "basicConfig", lambda **_kwargs: None)
    adapter.fetch_quote.return_value = {"price": 123.0} if ok else None
    assert check.main(["--market", "HK", "--symbol", "00700.HK", "--kind", "quote"]) == exit_code
    assert json.loads(capsys.readouterr().out)["ok"] is ok


@pytest.mark.parametrize("args", [[], ["--market", "JP", "--symbol", "NVDA", "--kind", "quote"], ["--market", "US", "--symbol", "", "--kind", "quote"]])
def test_cli_rejects_invalid_arguments(adapter: Mock, monkeypatch: pytest.MonkeyPatch, args: list[str]) -> None:
    monkeypatch.setattr(check.logging, "basicConfig", lambda **_kwargs: None)
    with pytest.raises(SystemExit) as caught:
        check.main(args)
    assert caught.value.code == 2
    adapter.fetch_quote.assert_not_called()
    adapter.fetch_json.assert_not_called()

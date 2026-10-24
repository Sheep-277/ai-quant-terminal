import argparse
from collections.abc import Sequence
import json
import logging
from time import perf_counter
from typing import Literal

from app.core.exceptions import ProviderError
from app.core.market import MarketCode
from app.providers.http_quote_fetcher import RealProviderReadRequest
from app.providers.yahoo_finance_adapter import YahooFinanceAdapter
from app.schemas.stock import StockResearchQuery


ReadKind = Literal["quote", "bars"]


def check_yahoo_finance(*, market: MarketCode, symbol: str, kind: ReadKind) -> dict[str, object]:
    """单次直读公开行情并计时；只诊断 Adapter，不代表业务接口或数据质量验收。"""

    query = StockResearchQuery(market=market, symbol=symbol)
    if query.symbol is None or kind not in ("quote", "bars"):
        raise ValueError("Explicit symbol and valid read kind are required.")
    request: RealProviderReadRequest = {
        "provider_name": "YahooFinance",
        "method": "GET",
        "url": "",
        "market": query.market.value,
        "symbol": query.symbol,
        "api_key_env": None,
        "api_key_configured": False,
        "missing_configuration": [],
    }
    adapter = YahooFinanceAdapter()
    started_at = perf_counter()
    ok = False
    item_count = 0
    error_type: str | None = None
    try:
        if kind == "quote":
            quote = adapter.fetch_quote(request)
            ok = quote is not None
            item_count = int(ok)
        else:
            bars = adapter.fetch_json(request)
            ok = isinstance(bars, list) and len(bars) > 0
            item_count = len(bars) if isinstance(bars, list) else 0
    except (ProviderError, OSError, UnicodeError, ValueError) as exc:
        # 原始异常可能携带代理地址或响应内容，报告仅输出类型。
        error_type = type(exc).__name__

    return {
        "market": query.market.value,
        "symbol": query.symbol,
        "kind": kind,
        "ok": ok,
        "elapsed_ms": round((perf_counter() - started_at) * 1000, 1),
        "item_count": item_count,
        "error_type": error_type,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """报告到 stdout，分阶段日志到 stderr；失败返回非零退出码。"""

    parser = argparse.ArgumentParser(description="Diagnose one YahooFinance public quote or bars request.")
    parser.add_argument("--market", choices=[market.value for market in MarketCode], required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--kind", choices=("quote", "bars"), required=True)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        report = check_yahoo_finance(market=MarketCode(args.market), symbol=args.symbol, kind=args.kind)
    except ValueError:
        parser.error("Invalid market, symbol or read kind.")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

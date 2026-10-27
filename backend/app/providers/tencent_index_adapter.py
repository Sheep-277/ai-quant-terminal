from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
import json
from math import isfinite
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.exceptions import ProviderResponseError
from app.core.market import MarketCode
from app.providers.base import ProviderBar
from app.schemas.market import DataStatus


class TencentIndexAdapter:
    """仅读取沪深300公开日线，作为总览历史不足时的真实备用来源。"""

    def __init__(self, *, opener: Callable[..., Any] = urlopen, timeout_seconds: float = 8.0) -> None:
        self._opener = opener
        self._timeout_seconds = timeout_seconds

    def fetch_bars(self, market: MarketCode, symbol: str, *, count: int = 30) -> list[ProviderBar]:
        """把腾讯的日期、开收高低和成交量顺序转换成项目 K 线结构。"""
        if market != MarketCode.CN or symbol != "000300.SH" or not 2 <= count <= 500:
            raise ValueError("Tencent index history only accepts CN 000300.SH and count 2..500.")
        query = urlencode({"param": f"sh000300,day,,,{count},qfq"})
        request = Request(
            f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?{query}",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        )
        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict) or payload.get("code") != 0:
                raise ValueError("Invalid Tencent result code.")
            data = payload.get("data")
            item = data.get("sh000300") if isinstance(data, dict) else None
            # 指数没有股票除权需求；只接受原始 day，不混入股票复权序列。
            rows = item.get("day") if isinstance(item, dict) else None
            if not isinstance(rows, list):
                raise ValueError("Missing Tencent index daily series.")
            bars: dict[date, ProviderBar] = {}
            for row in rows:
                if not isinstance(row, list) or len(row) < 6 or not isinstance(row[0], str):
                    raise ValueError("Invalid Tencent daily row.")
                trading_date = date.fromisoformat(row[0])
                if any(isinstance(value, bool) for value in row[1:6]):
                    raise ValueError("Invalid Tencent numeric value.")
                open_price, close, high, low, volume = (float(value) for value in row[1:6])
                if not all(isfinite(value) for value in (open_price, close, high, low, volume)):
                    raise ValueError("Non-finite Tencent daily value.")
                if low <= 0 or low > min(open_price, close) or high < max(open_price, close) or volume < 0 or not volume.is_integer():
                    raise ValueError("Invalid Tencent OHLCV values.")
                if trading_date in bars:
                    raise ValueError("Duplicate Tencent trading date.")
                # 日期是交易日标签，午夜并非成交时间；不能伪造请求时间或收盘时刻。
                bars[trading_date] = {
                    "offset": 0,
                    "timestamp": datetime.combine(trading_date, time(), timezone(timedelta(hours=8))),
                    "open": open_price, "close": close, "high": high, "low": low,
                    "volume": int(volume), "source": "tencent_finance", "data_status": DataStatus.DELAYED,
                }
            ordered = [bars[day] for day in sorted(bars)][-count:]
            if len(ordered) < 2:
                raise ValueError("Insufficient Tencent history.")
            return [{**bar, "offset": len(ordered) - index - 1} for index, bar in enumerate(ordered)]
        except (OSError, UnicodeError, ValueError, TypeError, OverflowError) as exc:
            raise ProviderResponseError("腾讯沪深300日线读取失败。", provider_name="TencentFinance", retryable=True) from exc

from datetime import date, datetime, timedelta, timezone
import json
import logging
from collections.abc import Callable, Sequence
from math import isfinite
from time import perf_counter
from typing import Any, Mapping, TypedDict
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from app.core.exceptions import ProviderResponseError
from app.providers.http_quote_fetcher import JsonPayload, RealProviderReadRequest


logger = logging.getLogger(__name__)


class YahooHistoryCoverage(TypedDict):
    """仅描述有效历史点与时间边界，不承诺覆盖全部交易日或回测区间。"""

    valid_point_count: int
    trend_available: bool
    first_timestamp: str | None
    last_timestamp: str | None


class YahooFinanceAdapter:
    """Yahoo Finance 无 Key 行情 Adapter，用于本地演示真实行情最小闭环。"""

    _BASE_URL = "https://query1.finance.yahoo.com"

    def __init__(
        self,
        *,
        timeout_seconds: float = 8.0,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        """允许测试注入 opener；生产运行默认使用标准库 urlopen 发起 GET。"""

        self._timeout_seconds = timeout_seconds
        self._opener = opener

    def fetch_quote(self, request: RealProviderReadRequest) -> Mapping[str, object] | None:
        """读取 Yahoo chart 元数据和最近收盘价，转换成通用 Quote 原始字段。"""

        chart = self._fetch_chart_payload(request, range_value="5d", interval="1d")
        result = self._read_chart_result(chart, provider_name=request["provider_name"])
        meta = self._read_mapping(result, "meta", provider_name=request["provider_name"])
        quote_data = self._read_latest_quote_data(result, provider_name=request["provider_name"])

        price = self._read_float_from_mapping(meta, ("regularMarketPrice",))
        if price is None:
            price = quote_data["close"]

        # chartPreviousClose 是整个请求窗口的前收，不能当作当日涨跌幅的分母。
        previous_close = self._read_float_from_mapping(meta, ("previousClose",))
        if previous_close is None:
            previous_close = quote_data["previous_close"]

        change = price - previous_close if previous_close else 0.0
        change_percent = change / previous_close if previous_close else 0.0
        volume = int(quote_data["volume"])

        return {
            "price": price,
            "change": change,
            "change_percent": change_percent,
            "volume": volume,
            "turnover": price * volume,
            "timestamp": self._format_unix_timestamp(meta["regularMarketTime"])
            if meta.get("regularMarketTime") is not None
            else self._latest_quote_timestamp(result),
        }

    def _latest_quote_timestamp(self, result: Mapping[str, object]) -> str:
        """元数据没有行情时间时，取最后一个有效收盘价对应的时间，不使用请求时间。"""

        timestamps = result.get("timestamp")
        indicators = self._read_mapping(result, "indicators", provider_name="YahooFinance")
        quote_list = indicators.get("quote")
        if isinstance(timestamps, list) and isinstance(quote_list, list) and quote_list:
            quote_data = quote_list[0]
            if isinstance(quote_data, Mapping):
                closes = quote_data.get("close")
                if isinstance(closes, list):
                    for index in range(min(len(timestamps), len(closes)) - 1, -1, -1):
                        if closes[index] is not None and timestamps[index] is not None:
                            return self._format_unix_timestamp(timestamps[index])
        raise ProviderResponseError("Yahoo Finance 行情缺少有效时间。", provider_name="YahooFinance")

    def fetch_json(
        self,
        request: RealProviderReadRequest,
        *,
        wrapper_keys: tuple[str, ...] = (),
        require_wrapped_object: bool = False,
    ) -> JsonPayload | None:
        """读取 Yahoo chart K 线，并返回 RealMarketDataProvider 可归一化的数组。"""

        chart = self._fetch_chart_payload(
            request,
            range_value="3mo",
            interval=str(request.get("interval") or "1d"),
            use_request_period=True,
        )
        result = self._read_chart_result(chart, provider_name=request["provider_name"])
        timestamps = result.get("timestamp")
        indicators = self._read_mapping(result, "indicators", provider_name=request["provider_name"])
        quote_list = indicators.get("quote")
        if not isinstance(timestamps, list) or not isinstance(quote_list, list) or not quote_list:
            raise ProviderResponseError(
                "Yahoo Finance K 线响应缺少 timestamp 或 quote 数组。",
                provider_name=request["provider_name"],
                retryable=True,
            )

        quote_data = quote_list[0]
        if not isinstance(quote_data, Mapping):
            raise ProviderResponseError(
                "Yahoo Finance K 线 quote 必须是对象。",
                provider_name=request["provider_name"],
                retryable=True,
            )

        bars: list[dict[str, object]] = []
        for index, timestamp in enumerate(timestamps):
            bar = self._read_bar_at_index(quote_data, index, timestamp)
            if bar is not None:
                bars.append(bar)

        if not bars:
            raise ProviderResponseError(
                "Yahoo Finance K 线响应没有可用 OHLCV 数据。",
                provider_name=request["provider_name"],
                retryable=True,
            )

        coverage = self.assess_history_coverage(bars)
        if not coverage["trend_available"]:
            # 不抛异常触发 Mock 替换，真实单点继续交给页面显示历史不足。
            logger.warning(
                "yahoo_history_coverage market=%s symbol=%s valid_point_count=%s trend_available=false",
                request["market"], request["symbol"], coverage["valid_point_count"],
            )
        return bars

    @staticmethod
    def assess_history_coverage(bars: Sequence[Mapping[str, object]]) -> YahooHistoryCoverage:
        """以有限正收盘价和不同的带时区时间点判定能否绘图，不借用最新报价补点。"""

        timestamps: set[datetime] = set()
        for bar in bars:
            close = bar.get("close")
            timestamp = bar.get("timestamp")
            if isinstance(close, bool) or not isinstance(close, (int, float, str)) or not isinstance(timestamp, str):
                continue
            try:
                value = float(close)
                instant = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except (ValueError, OverflowError):
                continue
            if not isfinite(value) or value <= 0 or instant.utcoffset() is None:
                continue
            timestamps.add(instant.astimezone(timezone.utc))

        return {
            "valid_point_count": len(timestamps),
            "trend_available": len(timestamps) >= 2,
            "first_timestamp": min(timestamps).isoformat() if timestamps else None,
            "last_timestamp": max(timestamps).isoformat() if timestamps else None,
        }

    def _fetch_chart_payload(
        self,
        request: RealProviderReadRequest,
        *,
        range_value: str,
        interval: str,
        use_request_period: bool = False,
    ) -> Mapping[str, object]:
        """请求 Yahoo chart 接口；该接口不需要 API Key。"""

        yahoo_symbol = self._to_yahoo_symbol(request["market"], request["symbol"])
        query = urlencode(self._build_chart_query(request, range_value=range_value, interval=interval, use_request_period=use_request_period))
        url = f"{self._BASE_URL}/v8/finance/chart/{quote(yahoo_symbol)}?{query}"
        http_request = Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json,text/plain,*/*",
                "Cache-Control": "no-cache",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                ),
            },
        )

        started_at = perf_counter()
        phase = "connect"
        outcome = "failed"
        connect_ms: float | None = None
        read_ms: float | None = None
        try:
            try:
                with self._opener(http_request, timeout=self._timeout_seconds) as response:
                    connected_at = perf_counter()
                    connect_ms = round((connected_at - started_at) * 1000, 1)
                    phase = "read"
                    raw_payload = response.read()
                    read_ms = round((perf_counter() - connected_at) * 1000, 1)
                    phase = "decode"
                    payload = raw_payload.decode("utf-8")
            except OSError as exc:
                raise ProviderResponseError(
                    "Yahoo Finance 行情请求失败。",
                    provider_name=request["provider_name"],
                    retryable=True,
                ) from exc

            phase = "parse"
            try:
                data = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ProviderResponseError(
                    "Yahoo Finance 返回了无效 JSON。",
                    provider_name=request["provider_name"],
                    retryable=True,
                ) from exc

            phase = "validate"
            if not isinstance(data, Mapping):
                raise ProviderResponseError(
                    "Yahoo Finance JSON 顶层必须是对象。",
                    provider_name=request["provider_name"],
                    retryable=True,
                )

            phase = "complete"
            outcome = "success"
            return data
        finally:
            # 单调时钟不受系统校时影响；只记录诊断字段，不写 URL、响应或原始异常。
            elapsed_seconds = perf_counter() - started_at
            logger.log(
                logging.WARNING
                if outcome == "failed" or elapsed_seconds >= self._timeout_seconds
                else logging.INFO,
                "yahoo_chart_request market=%s symbol=%s interval=%s outcome=%s "
                "phase=%s elapsed_ms=%.1f connect_ms=%s read_ms=%s io_timeout_seconds=%s",
                request["market"], request["symbol"], interval, outcome, phase,
                elapsed_seconds * 1000, connect_ms, read_ms, self._timeout_seconds,
            )

    def _build_chart_query(
        self,
        request: RealProviderReadRequest,
        *,
        range_value: str,
        interval: str,
        use_request_period: bool,
    ) -> dict[str, str]:
        """构造 Yahoo chart 查询参数；回测 K 线优先使用明确起止日期。"""

        start = request.get("start")
        end = request.get("end")
        if use_request_period and start and end:
            return {
                "period1": str(_date_to_unix_timestamp(start)),
                "period2": str(_date_to_unix_timestamp(end, include_full_day=True)),
                "interval": interval,
            }

        return {"range": range_value, "interval": interval}

    def _read_chart_result(
        self,
        payload: Mapping[str, object],
        *,
        provider_name: str,
    ) -> Mapping[str, object]:
        """提取 chart.result[0]，并把 Yahoo error 转换为统一 Provider 异常。"""

        chart = self._read_mapping(payload, "chart", provider_name=provider_name)
        error = chart.get("error")
        if error is not None:
            raise ProviderResponseError(
                f"Yahoo Finance 返回错误：{error}。",
                provider_name=provider_name,
                retryable=True,
            )

        result = chart.get("result")
        if not isinstance(result, list) or not result or not isinstance(result[0], Mapping):
            raise ProviderResponseError(
                "Yahoo Finance 响应缺少 chart.result[0]。",
                provider_name=provider_name,
                retryable=True,
            )

        return result[0]

    def _read_latest_quote_data(
        self,
        result: Mapping[str, object],
        *,
        provider_name: str,
    ) -> dict[str, float]:
        """从 Yahoo K 线数组末尾读取最近可用 close、前收和 volume。"""

        indicators = self._read_mapping(result, "indicators", provider_name=provider_name)
        quote_list = indicators.get("quote")
        if not isinstance(quote_list, list) or not quote_list or not isinstance(quote_list[0], Mapping):
            raise ProviderResponseError(
                "Yahoo Finance Quote 响应缺少 indicators.quote。",
                provider_name=provider_name,
                retryable=True,
            )

        quote_data = quote_list[0]
        closes = quote_data.get("close")
        volumes = quote_data.get("volume")
        if not isinstance(closes, list) or not isinstance(volumes, list):
            raise ProviderResponseError(
                "Yahoo Finance Quote 响应缺少 close 或 volume 数组。",
                provider_name=provider_name,
                retryable=True,
            )

        available_closes = [float(value) for value in closes if value is not None]
        available_volumes = [int(value) for value in volumes if value is not None]
        if not available_closes:
            raise ProviderResponseError(
                "Yahoo Finance Quote 响应没有可用 close。",
                provider_name=provider_name,
                retryable=True,
            )

        latest_close = available_closes[-1]
        previous_close = available_closes[-2] if len(available_closes) >= 2 else latest_close
        latest_volume = available_volumes[-1] if available_volumes else 0
        return {
            "close": latest_close,
            "previous_close": previous_close,
            "volume": float(latest_volume),
        }

    def _read_bar_at_index(
        self,
        quote_data: Mapping[str, object],
        index: int,
        timestamp: object,
    ) -> dict[str, object] | None:
        """读取单根 K 线；Yahoo 偶尔返回 None，遇到缺字段时跳过该日。"""

        open_price = self._read_series_value(quote_data, "open", index)
        high_price = self._read_series_value(quote_data, "high", index)
        low_price = self._read_series_value(quote_data, "low", index)
        close_price = self._read_series_value(quote_data, "close", index)
        volume = self._read_series_value(quote_data, "volume", index)
        if None in {open_price, high_price, low_price, close_price, volume}:
            return None

        return {
            "timestamp": self._format_unix_timestamp(timestamp),
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume,
        }

    def _format_unix_timestamp(self, timestamp: object) -> str:
        """把 Yahoo 秒级时间戳转换为 ISO 字符串，供后续 K 线图使用真实日期。"""

        try:
            unix_timestamp = int(timestamp)
        except (TypeError, ValueError) as exc:
            raise ProviderResponseError(
                "Yahoo Finance K 线 timestamp 不是有效整数。",
                provider_name="YahooFinance",
                retryable=True,
            ) from exc

        return datetime.fromtimestamp(unix_timestamp, tz=timezone.utc).isoformat()

    def _read_series_value(
        self,
        quote_data: Mapping[str, object],
        key: str,
        index: int,
    ) -> object | None:
        """读取 Yahoo OHLCV 数组中的单个值。"""

        series = quote_data.get(key)
        if not isinstance(series, list) or index >= len(series):
            return None
        return series[index]

    def _read_mapping(
        self,
        payload: Mapping[str, object],
        key: str,
        *,
        provider_name: str,
    ) -> Mapping[str, object]:
        """从响应中读取对象字段。"""

        value = payload.get(key)
        if not isinstance(value, Mapping):
            raise ProviderResponseError(
                f"Yahoo Finance 响应字段 {key} 必须是对象。",
                provider_name=provider_name,
                retryable=True,
            )
        return value

    def _read_float_from_mapping(
        self,
        payload: Mapping[str, object],
        keys: tuple[str, ...],
    ) -> float | None:
        """按候选字段读取浮点数，字段缺失时返回 None。"""

        for key in keys:
            value = payload.get(key)
            if value is not None:
                return float(value)
        return None

    def _to_yahoo_symbol(self, market: str, symbol: str) -> str:
        """把项目内部市场代码转换为 Yahoo Finance 标的代码。"""

        normalized_symbol = symbol.strip().upper()
        index_symbols = {
            "US": {"SPX": "^GSPC", "NDX": "^NDX", "VIX": "^VIX"},
            "HK": {"HSI": "^HSI"},
        }
        if normalized_symbol in index_symbols.get(market, {}):
            return index_symbols[market][normalized_symbol]
        if market == "HK" and normalized_symbol.endswith(".HK"):
            symbol_body = normalized_symbol[:-3]
            if symbol_body.isdigit() and len(symbol_body) == 5 and symbol_body.startswith("0"):
                return f"{symbol_body[1:]}.HK"
            return normalized_symbol
        if market == "CN" and normalized_symbol.endswith(".SH"):
            return f"{normalized_symbol[:-3]}.SS"
        if market == "CN" and normalized_symbol.endswith(".SZ"):
            return normalized_symbol
        return normalized_symbol


def _date_to_unix_timestamp(value: str, *, include_full_day: bool = False) -> int:
    """把 YYYY-MM-DD 转为 UTC 秒级时间戳；结束日期按包含当天处理。"""

    parsed_date = date.fromisoformat(value)
    if include_full_day:
        parsed_date = parsed_date + timedelta(days=1)
    return int(datetime.combine(parsed_date, datetime.min.time(), tzinfo=timezone.utc).timestamp())

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from math import isfinite
import os
from typing import Mapping, TypedDict

from app.core.config import Settings
from app.core.exceptions import ProviderResponseError, ProviderUnavailableError
from app.core.market import MarketCode
from app.providers.base import (
    MarketDataProvider,
    ProviderAssetProfile,
    ProviderBar,
    ProviderFinancials,
    ProviderMarketBreadth,
    ProviderMarketEvent,
    ProviderMarketIndex,
    ProviderMarketOverviewData,
    ProviderQuote,
    ProviderResearchNotes,
    ProviderSectorPerformance,
    ProviderStatus,
)
from app.providers.http_quote_fetcher import ProviderJsonFetcher, RealProviderReadRequest
from app.providers.field_mapping import ProviderFieldMapping, get_provider_field_mapping
from app.providers.market_data import MockMarketDataProvider
from app.providers.request_mapping import ProviderRequestMapping, get_provider_request_mapping
from app.schemas.market import DataStatus, MarketEventOrigin


class ProviderFallbackSnapshot(TypedDict):
    """真实 Provider 回退到 Mock 时的统一状态快照。"""

    fallback_reason: str | None
    active_source: str
    source_type: str
    data_status: DataStatus
    missing_configuration: list[str]
    next_action: str
    event_title: str


class RealMarketDataProvider:
    """真实行情 Provider 占位实现；未接入外部数据源时显式回退到 Mock 数据。"""

    MIN_BAR_COUNT = 1
    MAX_BAR_COUNT = 500

    def __init__(
        self,
        settings: Settings,
        fallback_provider: MarketDataProvider | None = None,
        quote_fetcher: ProviderJsonFetcher | None = None,
        field_mapping: ProviderFieldMapping | None = None,
        request_mapping: ProviderRequestMapping | None = None,
    ) -> None:
        """保留配置、Mock 回退和可注入 fetcher，让真实源接入不影响 service。"""

        self._settings = settings
        self._fallback_provider = fallback_provider or MockMarketDataProvider()
        self._quote_fetcher = quote_fetcher
        self._field_mapping = field_mapping or get_provider_field_mapping(settings.real_provider_name)
        self._request_mapping = request_mapping or get_provider_request_mapping(settings.real_provider_name)

    def _missing_configuration_items(self) -> list[str]:
        """检查真实 Provider 所需的最小配置项，不在这里读取或调用外部行情。"""

        missing_items: list[str] = []

        if not self._settings.real_provider_base_url:
            missing_items.append("REAL_PROVIDER_BASE_URL")
        if self._is_demo_provider():
            return missing_items

        if not self._requires_api_key():
            return missing_items

        if not self._settings.real_provider_api_key_env:
            missing_items.append("REAL_PROVIDER_API_KEY_ENV")
        elif not os.getenv(self._settings.real_provider_api_key_env):
            missing_items.append(self._settings.real_provider_api_key_env)

        return missing_items

    def _is_demo_provider(self) -> bool:
        """DemoProvider 只使用本地样例数据，不需要真实供应商 API Key。"""

        return self._settings.real_provider_name.strip().lower() == "demoprovider"

    def _is_yahoo_finance_provider(self) -> bool:
        """YahooFinance 使用公开 chart 接口，不需要 API Key。"""

        return self._settings.real_provider_name.strip().lower() == "yahoofinance"

    def _requires_api_key(self) -> bool:
        """判断当前真实 Provider 是否需要 API Key。"""

        return not (self._is_demo_provider() or self._is_yahoo_finance_provider())

    def get_fallback_snapshot(self) -> ProviderFallbackSnapshot:
        """生成统一回退快照，供状态接口、行情回退和事件提示复用。"""

        missing_items = self._missing_configuration_items()
        if missing_items:
            reason = f"真实行情 Provider 缺少配置：{', '.join(missing_items)}，当前使用 Mock 数据回退。"
            next_action = f"补全配置项：{', '.join(missing_items)}。"
            event_title = "真实行情 Provider 缺少配置，当前使用 Mock 回退数据"
            source_type = "real_placeholder"
            data_status = DataStatus.UNAVAILABLE
            active_source = "mock_fallback"
        elif self._is_demo_provider():
            reason = None
            next_action = "当前使用本地 DemoProvider 样例行情；接真实行情时请替换 Provider 配置。"
            event_title = "本地 DemoProvider 已启用，当前展示样例行情数据"
            source_type = "demo_provider"
            data_status = DataStatus.DELAYED
            active_source = "demo_provider"
        elif self._is_yahoo_finance_provider():
            reason = None
            next_action = "当前使用 Yahoo Finance 无 Key 公开行情；仅用于课程演示和开发验证。"
            event_title = "Yahoo Finance 无 Key 行情已启用，当前展示延迟真实行情"
            source_type = "yahoo_finance"
            data_status = DataStatus.DELAYED
            active_source = "yahoo_finance"
        else:
            reason = "真实行情 Provider 配置完整，Quote HTTP 读取边界已启用；未验证具体供应商响应前仍保留 Mock 回退。"
            next_action = "调用个股 Quote 接口验证真实 Provider 响应字段，再逐步关闭 Mock 回退。"
            event_title = "真实行情 Provider 配置完整，等待 Quote 响应验证"
            source_type = "real_http_configured"
            data_status = DataStatus.DELAYED
            active_source = "mock_fallback"

        return {
            "fallback_reason": reason,
            "active_source": active_source,
            "source_type": source_type,
            "data_status": data_status,
            "missing_configuration": missing_items,
            "next_action": next_action,
            "event_title": event_title,
        }

    def validate_configuration(self) -> None:
        """校验真实 Provider 最小配置，缺失时抛出统一不可用异常。"""

        missing_items = self._missing_configuration_items()
        if missing_items:
            raise ProviderUnavailableError(
                f"真实行情 Provider 缺少配置：{', '.join(missing_items)}。",
                provider_name=self._settings.real_provider_name,
                retryable=False,
            )

    def build_quote_request(self, market: MarketCode, symbol: str) -> RealProviderReadRequest:
        """构造未来真实 Quote 行情请求，不读取密钥明文，也不发起外部网络访问。"""

        normalized_symbol = symbol.strip().upper()
        base_url = self._settings.real_provider_base_url.rstrip("/") if self._settings.real_provider_base_url else None
        api_key_env = self._settings.real_provider_api_key_env

        return {
            "provider_name": self._settings.real_provider_name,
            "method": "GET",
            "url": self._request_mapping.build_quote_url(base_url, market, normalized_symbol) if base_url else None,
            "market": market.value,
            "symbol": normalized_symbol,
            "api_key_env": api_key_env,
            "api_key_configured": bool(api_key_env and os.getenv(api_key_env)),
            "missing_configuration": self._missing_configuration_items(),
        }

    def build_bars_request(
        self,
        market: MarketCode,
        symbol: str,
        *,
        interval: str = "1d",
        count: int = 30,
        start: date | None = None,
        end: date | None = None,
    ) -> RealProviderReadRequest:
        """构造未来真实历史 K 线请求描述，不访问网络也不暴露密钥明文。"""

        normalized_interval, normalized_count = self._normalize_bars_request_params(
            interval=interval,
            count=count,
            start=start,
            end=end,
        )
        normalized_symbol = symbol.strip().upper()
        base_url = self._settings.real_provider_base_url.rstrip("/") if self._settings.real_provider_base_url else None
        api_key_env = self._settings.real_provider_api_key_env

        return {
            "provider_name": self._settings.real_provider_name,
            "method": "GET",
            "url": self._request_mapping.build_bars_url(
                base_url,
                market,
                normalized_symbol,
                interval=normalized_interval,
                count=normalized_count,
                start=start,
                end=end,
            )
            if base_url
            else None,
            "market": market.value,
            "symbol": normalized_symbol,
            "api_key_env": api_key_env,
            "api_key_configured": bool(api_key_env and os.getenv(api_key_env)),
            "missing_configuration": self._missing_configuration_items(),
            "interval": normalized_interval,
            "count": normalized_count,
            "start": start.isoformat() if start is not None else None,
            "end": end.isoformat() if end is not None else None,
        }

    def _normalize_bars_request_params(
        self,
        *,
        interval: str,
        count: int,
        start: date | None,
        end: date | None,
    ) -> tuple[str, int]:
        """校验并规范 K 线请求参数，避免把无效边界传给真实供应商。"""

        normalized_interval = interval.strip().lower()
        if not normalized_interval:
            raise ProviderResponseError(
                "真实行情 Provider K 线 interval 不能为空。",
                provider_name=self._settings.real_provider_name,
                retryable=False,
            )
        if count < self.MIN_BAR_COUNT or count > self.MAX_BAR_COUNT:
            raise ProviderResponseError(
                f"真实行情 Provider K 线 count 必须在 {self.MIN_BAR_COUNT} 到 {self.MAX_BAR_COUNT} 之间。",
                provider_name=self._settings.real_provider_name,
                retryable=False,
            )
        if start is not None and end is not None and start > end:
            raise ProviderResponseError(
                "真实行情 Provider K 线 start 不能晚于 end。",
                provider_name=self._settings.real_provider_name,
                retryable=False,
            )

        return normalized_interval, count

    def _fetch_quote_response(self, request: RealProviderReadRequest) -> Mapping[str, object] | None:
        """通过注入的 fetcher 获取 Quote；未注入时不访问网络并返回空。"""

        if self._quote_fetcher is not None:
            return self._quote_fetcher.fetch_quote(request)
        return None

    def _fetch_bars_response(self, request: RealProviderReadRequest) -> list[Mapping[str, object]] | None:
        """通过可复用 fetcher 预留历史 K 线读取入口；未接入时返回空。"""

        if self._quote_fetcher is None:
            return None

        fetch_json = getattr(self._quote_fetcher, "fetch_json", None)
        if not callable(fetch_json):
            return None

        payload = fetch_json(
            request,
            wrapper_keys=("data", "bars", "result"),
            require_wrapped_object=False,
        )
        if payload is None:
            return None
        raw_bars = self._extract_bars_payload(payload)

        bars: list[Mapping[str, object]] = []
        for item in raw_bars:
            if not isinstance(item, dict):
                raise ProviderResponseError(
                    "真实行情 Provider K 线数组元素必须是对象。",
                    provider_name=self._settings.real_provider_name,
                    retryable=False,
                )
            bars.append(item)

        return bars

    def _extract_bars_payload(self, payload: object) -> list[object]:
        """从供应商 JSON 中提取 K 线数组，兼容 data/bars/items 等常见包装层。"""

        if isinstance(payload, list):
            return payload

        if not isinstance(payload, Mapping):
            raise ProviderResponseError(
                "真实行情 Provider K 线 JSON 必须是数组或对象。",
                provider_name=self._settings.real_provider_name,
                retryable=False,
            )

        # 很多真实 API 会返回 {"data": {"bars": [...]}} 或 {"result": {"items": [...]}}。
        for key in ("bars", "items", "candles", "klines", "data", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, Mapping):
                return self._extract_bars_payload(value)
            if value is not None:
                raise ProviderResponseError(
                    f"真实行情 Provider K 线字段 {key} 必须是数组或对象。",
                    provider_name=self._settings.real_provider_name,
                    retryable=False,
                )

        raise ProviderResponseError(
            "真实行情 Provider K 线 JSON 未找到 bars/items/candles/klines 数组。",
            provider_name=self._settings.real_provider_name,
            retryable=False,
        )

    def normalize_quote_response(
        self,
        raw_quote: Mapping[str, object],
        *,
        data_status: DataStatus = DataStatus.DELAYED,
    ) -> ProviderQuote:
        """把供应商原始 Quote 字段转换成项目内部统一行情结构。"""

        price = self._read_float(raw_quote, self._field_mapping.quote["price"])
        change = self._read_float(raw_quote, self._field_mapping.quote["change"])
        change_percent = self._normalize_change_percent(
            self._read_float(raw_quote, self._field_mapping.quote["change_percent"])
        )
        volume = self._read_int(raw_quote, self._field_mapping.quote["volume"])
        turnover = self._read_float(raw_quote, self._field_mapping.quote["turnover"])

        quote: ProviderQuote = {
            "price": price,
            "change": change,
            "change_percent": change_percent,
            "volume": volume,
            "turnover": turnover,
            "data_status": data_status,
        }
        # 无时间字段的旧样例保持兼容；供应商提供时间时不得改写为读取时间。
        raw_timestamp = raw_quote.get("timestamp")
        if raw_timestamp is not None:
            try:
                if isinstance(raw_timestamp, datetime):
                    timestamp = raw_timestamp
                elif isinstance(raw_timestamp, str):
                    timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
                else:
                    raise ValueError("unsupported quote timestamp type")
                if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                    raise ValueError("quote timestamp must include timezone")
            except ValueError as error:
                raise ProviderResponseError(
                    "真实行情 Provider 报价时间无效或缺少时区。",
                    provider_name=self._settings.real_provider_name,
                    retryable=False,
                ) from error
            quote["timestamp"] = timestamp
        return quote

    def normalize_bars_response(self, raw_bars: list[Mapping[str, object]]) -> list[ProviderBar]:
        """把供应商原始 K 线数组转换成项目统一 ProviderBar 序列。"""

        if not raw_bars:
            raise ProviderResponseError(
                "真实行情 Provider K 线响应不能为空数组。",
                provider_name=self._settings.real_provider_name,
                retryable=False,
            )

        normalized_bars: list[ProviderBar] = []
        total_count = len(raw_bars)
        for index, raw_bar in enumerate(raw_bars):
            open_price = self._read_float(raw_bar, self._field_mapping.bars["open"], field_group="open", payload_name="K 线")
            high_price = self._read_float(raw_bar, self._field_mapping.bars["high"], field_group="high", payload_name="K 线")
            low_price = self._read_float(raw_bar, self._field_mapping.bars["low"], field_group="low", payload_name="K 线")
            close_price = self._read_float(raw_bar, self._field_mapping.bars["close"], field_group="close", payload_name="K 线")
            volume = self._read_int(raw_bar, self._field_mapping.bars["volume"], field_group="volume", payload_name="K 线")
            self._validate_bar_prices(open_price=open_price, high_price=high_price, low_price=low_price, close_price=close_price)
            self._validate_bar_volume(volume)

            normalized_bars.append(
                {
                    "offset": total_count - 1 - index,
                    **({"timestamp": raw_bar["timestamp"]} if raw_bar.get("timestamp") is not None else {}),
                    "data_status": DataStatus.DELAYED,
                    "source": self.get_fallback_snapshot()["active_source"],
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,
                }
            )

        return normalized_bars

    def _validate_bar_prices(
        self,
        *,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
    ) -> None:
        """校验单根 K 线 OHLC 基本关系，防止明显脏数据进入图表和指标计算。"""

        if high_price < max(open_price, close_price):
            raise ProviderResponseError(
                "K 线字段 high 不能低于 open 或 close。",
                provider_name=self._settings.real_provider_name,
                retryable=False,
            )
        if low_price > min(open_price, close_price):
            raise ProviderResponseError(
                "K 线字段 low 不能高于 open 或 close。",
                provider_name=self._settings.real_provider_name,
                retryable=False,
            )

    def _validate_bar_volume(self, volume: int) -> None:
        """校验单根 K 线成交量，成交量不能为负数。"""

        if volume < 0:
            raise ProviderResponseError(
                "K 线字段 volume 不能为负数。",
                provider_name=self._settings.real_provider_name,
                retryable=False,
            )

    def _read_float(
        self,
        raw_quote: Mapping[str, object],
        keys: tuple[str, ...],
        *,
        field_group: str | None = None,
        payload_name: str = "Quote",
    ) -> float:
        """按候选字段读取浮点数，适配不同供应商的字段命名。"""

        value = self._read_required_value(raw_quote, keys, payload_name=payload_name)
        field_name = field_group or keys[0]

        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ProviderResponseError(
                f"{self._format_field_error_prefix(payload_name)} {field_name} 不是有效数字。",
                provider_name=self._settings.real_provider_name,
            ) from exc

    def _read_int(
        self,
        raw_quote: Mapping[str, object],
        keys: tuple[str, ...],
        *,
        field_group: str | None = None,
        payload_name: str = "Quote",
    ) -> int:
        """按候选字段读取整数，当前主要用于成交量字段。"""

        value = self._read_required_value(raw_quote, keys, payload_name=payload_name)
        field_name = field_group or keys[0]

        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ProviderResponseError(
                f"{self._format_field_error_prefix(payload_name)} {field_name} 不是有效整数。",
                provider_name=self._settings.real_provider_name,
            ) from exc

    def _read_required_value(
        self,
        raw_quote: Mapping[str, object],
        keys: tuple[str, ...],
        *,
        payload_name: str = "Quote",
    ) -> object:
        """按候选字段读取必填值，缺失时直接暴露供应商响应不完整。"""

        for key in keys:
            value = raw_quote.get(key)
            if value is not None:
                return value

        raise ProviderResponseError(
            f"{self._format_response_error_prefix(payload_name)}缺少必填字段：{'/'.join(keys)}。",
            provider_name=self._settings.real_provider_name,
        )

    def _format_field_error_prefix(self, payload_name: str) -> str:
        """生成字段错误前缀，兼顾英文 Quote 和中文 K 线的空格习惯。"""

        return "Quote 字段" if payload_name == "Quote" else f"{payload_name}字段"

    def _format_response_error_prefix(self, payload_name: str) -> str:
        """生成响应错误前缀，避免 K 线错误信息误写成 Quote 响应。"""

        return "Quote 响应" if payload_name == "Quote" else f"{payload_name}响应"

    def _normalize_change_percent(self, value: float) -> float:
        """统一涨跌幅为小数表达，例如 1.23 表示供应商百分比点时转换为 0.0123。"""

        if abs(value) > 1:
            return round(value / 100, 6)

        return value

    def get_provider_status(self) -> ProviderStatus:
        """返回真实 Provider 占位状态，明确当前配置情况和回退原因。"""

        fallback_snapshot = self.get_fallback_snapshot()
        provider_ready = fallback_snapshot["active_source"] in {"demo_provider", "yahoo_finance"} and not fallback_snapshot["missing_configuration"]

        return {
            "provider_name": self._settings.real_provider_name,
            "mode": "real",
            "ready": provider_ready,
            "data_status": fallback_snapshot["data_status"],
            "fallback_active": fallback_snapshot["active_source"] == "mock_fallback",
            "fallback_reason": fallback_snapshot["fallback_reason"],
            "source_type": fallback_snapshot["source_type"],
            "active_source": fallback_snapshot["active_source"],
            "missing_configuration": fallback_snapshot["missing_configuration"],
            "next_action": fallback_snapshot["next_action"],
        }

    def get_default_stock_symbol(self, market: MarketCode) -> str:
        """真实股票池未配置前，沿用 Mock Provider 的默认标的。"""

        return self._fallback_provider.get_default_stock_symbol(market)

    def supports_symbol(self, market: MarketCode, symbol: str) -> bool:
        """真实覆盖范围未配置前，沿用 Mock Provider 的覆盖判断。"""

        return self._fallback_provider.supports_symbol(market, symbol)

    def get_quote(self, market: MarketCode, symbol: str) -> ProviderQuote:
        """尝试走真实 Quote 流程；真实源不可用或响应异常时使用 Mock 回退。"""

        raw_quote: Mapping[str, object] | None = None
        try:
            self.validate_configuration()
            quote_request = self.build_quote_request(market, symbol)
            raw_quote = self._fetch_quote_response(quote_request)
            if raw_quote is not None:
                return self.normalize_quote_response(raw_quote, data_status=DataStatus.DELAYED)
        except (ProviderUnavailableError, ProviderResponseError):
            raw_quote = None

        quote = self._fallback_provider.get_quote(market, symbol)
        return {
            **quote,
            "data_status": DataStatus.UNAVAILABLE,
        }

    def get_asset_profile(self, market: MarketCode, symbol: str) -> ProviderAssetProfile:
        """真实资料源未配置前，沿用 Mock Provider 的标的资料。"""

        return self._fallback_provider.get_asset_profile(market, symbol)

    def get_bars(
        self,
        market: MarketCode,
        symbol: str,
        *,
        interval: str = "1d",
        count: int = 30,
        start: date | None = None,
        end: date | None = None,
    ) -> list[ProviderBar]:
        """尝试走真实 K 线流程；未接入或响应异常时使用 Mock 回退。"""

        raw_bars: list[Mapping[str, object]] | None = None
        try:
            self.validate_configuration()
            bars_request = self.build_bars_request(
                market,
                symbol,
                interval=interval,
                count=count,
                start=start,
                end=end,
            )
            raw_bars = self._fetch_bars_response(bars_request)
            if raw_bars is not None:
                return self.normalize_bars_response(raw_bars)
        except (ProviderUnavailableError, ProviderResponseError):
            raw_bars = None

        fallback_bars = self._fallback_provider.get_bars(
            market,
            symbol,
            interval=interval,
            count=count,
            start=start,
            end=end,
        )
        return [
            {
                **bar,
                "data_status": DataStatus.UNAVAILABLE,
                "source": "mock_fallback",
            }
            for bar in fallback_bars
        ]

    def get_financials(self, market: MarketCode, symbol: str) -> ProviderFinancials:
        """真实财务数据未配置前，沿用 Mock Provider 的财务指标。"""

        return self._fallback_provider.get_financials(market, symbol)

    def get_research_notes(self, market: MarketCode, symbol: str) -> ProviderResearchNotes:
        """在研究说明中追加真实 Provider 未配置的可见提示。"""

        notes = self._fallback_provider.get_research_notes(market, symbol)
        if self._is_yahoo_finance_provider():
            return {
                **notes,
                "risk_flags": ["当前行情来自 Yahoo Finance 公开接口，可能存在延迟或访问限制，不能作为真实交易依据。"] + notes["risk_flags"],
                "summary_points": ["当前 DATA_PROVIDER=real，Quote 和 K 线优先读取 Yahoo Finance 无 Key 公开行情。"] + notes["summary_points"],
            }
        if self._is_demo_provider():
            return {
                **notes,
                "risk_flags": ["当前行情来自本地 DemoProvider 样例数据，不能作为真实投资依据。"] + notes["risk_flags"],
                "summary_points": ["当前 DATA_PROVIDER=real，行情链路使用本地 DemoProvider 样例数据。"] + notes["summary_points"],
            }

        return {
            **notes,
            "risk_flags": ["真实行情 Provider 尚未配置，当前页面显示 Mock 回退数据。"] + notes["risk_flags"],
            "summary_points": ["当前 DATA_PROVIDER=real，但真实数据源尚未接入，页面暂用 Mock 数据占位。"] + notes["summary_points"],
        }

    def get_market_data_status(self, market: MarketCode) -> DataStatus:
        """真实市场数据未配置时，市场总览显示 unavailable 状态。"""

        if (self._is_demo_provider() or self._is_yahoo_finance_provider()) and not self._missing_configuration_items():
            return DataStatus.DELAYED

        return DataStatus.UNAVAILABLE

    def get_market_overview_data(
        self,
        market: MarketCode,
        chart_symbol: str,
        *,
        interval: str = "1d",
        count: int = 30,
    ) -> ProviderMarketOverviewData:
        """仅对已配置的 Yahoo 并行读取指数和 K 线，不向未知 Adapter 假设线程安全。"""

        if not self._is_yahoo_finance_provider() or self._missing_configuration_items():
            return {
                "indices": self.get_market_indices(market),
                "bars": self.get_bars(market, chart_symbol, interval=interval, count=count),
            }

        # 指数内部最多三个请求，另一路只读图表；不在线程间共享数据库 Session。
        with ThreadPoolExecutor(max_workers=2) as executor:
            indices = executor.submit(self.get_market_indices, market)
            bars = executor.submit(self.get_bars, market, chart_symbol, interval=interval, count=count)
            return {"indices": indices.result(), "bars": bars.result()}

    def get_market_indices(self, market: MarketCode) -> list[ProviderMarketIndex]:
        """逐项读取公开指数报价；缺失项保留名称但不填入 Mock 点位。"""

        templates = self._fallback_provider.get_market_indices(market)
        # 三项指数并行读取，单个接口超时不会把等待时间累加到三倍。
        with ThreadPoolExecutor(max_workers=3) as executor:
            return list(executor.map(lambda index: self._read_market_index(market, index), templates))

    def _read_market_index(self, market: MarketCode, index: ProviderMarketIndex) -> ProviderMarketIndex:
        """指数读取独立于个股的 Mock 回退路径，失败时显式返回 unavailable。"""

        unavailable: ProviderMarketIndex = {
            **index,
            "value": None,
            "change_percent": None,
            "data_status": DataStatus.UNAVAILABLE,
            "source": "yahoo_finance" if self._is_yahoo_finance_provider() else "mock_provider",
            "timestamp": None,
        }
        # Yahoo 当前仅确认恒生指数代码，不把未知港股指数映射为 ETF 或个股。
        if not self._is_yahoo_finance_provider() or (market == MarketCode.HK and index["symbol"] != "HSI"):
            return unavailable
        try:
            self.validate_configuration()
            raw_quote = self._fetch_quote_response(self.build_quote_request(market, index["symbol"]))
            if raw_quote is None:
                return unavailable
            value = float(raw_quote["price"])
            change_percent = float(raw_quote["change_percent"])
            timestamp = datetime.fromisoformat(str(raw_quote["timestamp"]).replace("Z", "+00:00"))
            if not isfinite(value) or value <= 0 or not isfinite(change_percent) or timestamp.tzinfo is None:
                return unavailable
            return {
                **index,
                "value": value,
                "change_percent": change_percent,
                "data_status": DataStatus.DELAYED,
                "source": "yahoo_finance",
                "timestamp": timestamp,
            }
        except (ProviderUnavailableError, ProviderResponseError, KeyError, TypeError, ValueError, OverflowError):
            return unavailable

    def get_market_breadth(self, market: MarketCode) -> ProviderMarketBreadth:
        """真实市场宽度未配置前返回显式标记的 Mock 回退数据。"""

        return {
            **self._fallback_provider.get_market_breadth(market),
            "source": "mock_fallback",
            "data_status": DataStatus.UNAVAILABLE,
            "timestamp": None,
        }

    def get_sector_performance(self, market: MarketCode) -> list[ProviderSectorPerformance]:
        """真实行业表现未配置前返回显式标记的 Mock 回退数据。"""

        return [
            {
                **sector,
                "source": "mock_fallback",
                "data_status": DataStatus.UNAVAILABLE,
                "timestamp": None,
            }
            for sector in self._fallback_provider.get_sector_performance(market)
        ]

    def get_market_events(self, market: MarketCode) -> list[ProviderMarketEvent]:
        """市场事件中追加真实 Provider 未配置提示。"""

        fallback_snapshot = self.get_fallback_snapshot()

        return [
            {
                "source": "PROVIDER",
                "origin": MarketEventOrigin.SYSTEM,
                "title": fallback_snapshot["event_title"],
                "impact": "数据状态提示",
                "confidence": 1.0,
            },
            *self._fallback_provider.get_market_events(market),
        ]

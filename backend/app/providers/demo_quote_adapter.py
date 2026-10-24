from typing import Mapping

from app.providers.http_quote_fetcher import RealProviderReadRequest


class DemoQuoteAdapter:
    """最小供应商 Adapter 示例；只返回内存样例数据，不访问网络或读取密钥。"""

    _SAMPLE_QUOTES: dict[tuple[str, str], Mapping[str, object]] = {
        ("US", "NVDA"): {
            "lastPrice": "182.50",
            "priceChange": "1.50",
            "changeRate": "0.00829",
            "tradeVolume": "1000",
            "turnoverValue": "182500",
        },
        ("HK", "00700.HK"): {
            "lastPrice": "384.20",
            "priceChange": "-2.40",
            "changeRate": "-0.00621",
            "tradeVolume": "2400000",
            "turnoverValue": "922080000",
        },
        ("CN", "600519.SH"): {
            "lastPrice": "1688.00",
            "priceChange": "12.30",
            "changeRate": "0.00734",
            "tradeVolume": "180000",
            "turnoverValue": "303840000",
        },
    }

    _SAMPLE_BARS: dict[tuple[str, str], list[Mapping[str, object]]] = {
        ("US", "NVDA"): [
            {"o": "180.00", "h": "183.00", "l": "179.50", "c": "182.50", "v": "1000"},
            {"o": "182.50", "h": "184.20", "l": "181.80", "c": "183.75", "v": "1200"},
        ],
        ("HK", "00700.HK"): [
            {"o": "380.00", "h": "386.00", "l": "378.80", "c": "384.20", "v": "2400000"},
            {"o": "384.20", "h": "388.40", "l": "382.10", "c": "386.80", "v": "2600000"},
        ],
        ("CN", "600519.SH"): [
            {"o": "1672.00", "h": "1692.00", "l": "1668.50", "c": "1688.00", "v": "180000"},
            {"o": "1688.00", "h": "1705.00", "l": "1682.40", "c": "1698.60", "v": "196000"},
        ],
    }

    def fetch_quote(self, request: RealProviderReadRequest) -> Mapping[str, object] | None:
        """按 market 和 symbol 返回 demo Quote；未知标的返回 None 触发 Mock 回退。"""

        key = (request["market"], request["symbol"])
        return self._SAMPLE_QUOTES.get(key)

    def fetch_json(
        self,
        request: RealProviderReadRequest,
        *,
        wrapper_keys: tuple[str, ...] = (),
        require_wrapped_object: bool = False,
    ) -> Mapping[str, object] | None:
        """按 market 和 symbol 返回 demo K 线；响应结构刻意模拟真实供应商的包装层。"""

        if request["url"] is None or "/bars/" not in request["url"]:
            return None

        key = (request["market"], request["symbol"])
        bars = self._SAMPLE_BARS.get(key)
        if bars is None:
            return None

        # 真实行情 API 常把业务数组包在 data/bars/result 等字段中，demo 也保持这种形态。
        return {
            "data": {
                "bars": bars,
            }
        }

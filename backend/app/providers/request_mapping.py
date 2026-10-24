from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Mapping
from urllib.parse import urlencode

from app.core.market import MarketCode


@dataclass(frozen=True)
class ProviderRequestMapping:
    """描述一个行情供应商的只读请求路径模板。"""

    quote_path_template: str
    bars_path_template: str

    def build_quote_url(self, base_url: str, market: MarketCode, symbol: str) -> str:
        """根据供应商 Quote 路径模板生成完整请求 URL。"""

        return self._join_base_url(
            base_url,
            self.quote_path_template.format(market=market.value, symbol=symbol),
        )

    def build_bars_url(
        self,
        base_url: str,
        market: MarketCode,
        symbol: str,
        *,
        interval: str,
        count: int,
        start: date | None = None,
        end: date | None = None,
    ) -> str:
        """根据供应商 K 线路径模板和查询参数生成完整请求 URL。"""

        query_params = {
            "interval": interval,
            "count": str(count),
        }
        if start is not None:
            query_params["start"] = start.isoformat()
        if end is not None:
            query_params["end"] = end.isoformat()

        path = self.bars_path_template.format(market=market.value, symbol=symbol)
        return f"{self._join_base_url(base_url, path)}?{urlencode(query_params)}"

    def _join_base_url(self, base_url: str, path: str) -> str:
        """拼接 base URL 与路径模板，避免供应商配置中的斜杠影响结果。"""

        return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


DEFAULT_REQUEST_MAPPING = ProviderRequestMapping(
    quote_path_template="/quotes/{market}/{symbol}",
    bars_path_template="/bars/{market}/{symbol}",
)

# 供应商名称统一按小写保存。后续真实供应商路径差异优先在这里补充。
PROVIDER_REQUEST_MAPPINGS: Mapping[str, ProviderRequestMapping] = MappingProxyType(
    {
        "default": DEFAULT_REQUEST_MAPPING,
        "demoprovider": DEFAULT_REQUEST_MAPPING,
    }
)


def get_provider_request_mapping(provider_name: str) -> ProviderRequestMapping:
    """按供应商名称返回请求路径映射，未知供应商先使用通用路径。"""

    normalized_name = provider_name.strip().lower()
    return PROVIDER_REQUEST_MAPPINGS.get(normalized_name, DEFAULT_REQUEST_MAPPING)

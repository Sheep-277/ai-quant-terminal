from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


FieldAliases = Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class ProviderFieldMapping:
    """描述一个行情供应商的原始字段到项目标准字段的映射。"""

    quote: FieldAliases
    bars: FieldAliases


DEFAULT_QUOTE_FIELD_ALIASES: FieldAliases = MappingProxyType(
    {
        "price": ("price", "last", "last_price", "lastPrice", "latestPrice", "close"),
        "change": ("change", "change_amount", "changeAmount", "priceChange"),
        "change_percent": ("change_percent", "change_pct", "changePercent", "changeRate", "pctChange"),
        "volume": ("volume", "vol", "tradeVolume"),
        "turnover": ("turnover", "amount", "notional", "turnoverValue", "tradeValue"),
    }
)

DEFAULT_BAR_FIELD_ALIASES: FieldAliases = MappingProxyType(
    {
        "open": ("open", "o", "openPrice"),
        "high": ("high", "h", "highPrice"),
        "low": ("low", "l", "lowPrice"),
        "close": ("close", "c", "closePrice"),
        "volume": ("volume", "vol", "v", "tradeVolume"),
    }
)

DEFAULT_FIELD_MAPPING = ProviderFieldMapping(
    quote=DEFAULT_QUOTE_FIELD_ALIASES,
    bars=DEFAULT_BAR_FIELD_ALIASES,
)

# 供应商名称统一按小写保存。后续接入真实供应商时优先在这里添加专属映射。
PROVIDER_FIELD_MAPPINGS: Mapping[str, ProviderFieldMapping] = MappingProxyType(
    {
        "default": DEFAULT_FIELD_MAPPING,
        "demoprovider": DEFAULT_FIELD_MAPPING,
    }
)


def get_provider_field_mapping(provider_name: str) -> ProviderFieldMapping:
    """按供应商名称返回字段映射，未知供应商先使用通用映射。"""

    normalized_name = provider_name.strip().lower()
    return PROVIDER_FIELD_MAPPINGS.get(normalized_name, DEFAULT_FIELD_MAPPING)

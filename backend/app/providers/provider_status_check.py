import argparse
import json
from typing import Any

from app.core.config import DataProviderMode, Settings, get_settings
from app.core.market import MarketCode
from app.providers.factory import get_market_data_provider
from app.providers.real_market_data import RealMarketDataProvider


def build_provider_status_report(settings: Settings | None = None) -> dict[str, Any]:
    """生成本地 Provider 状态检查报告，供开发者在不启动 HTTP 服务时确认数据源模式。"""

    resolved_settings = settings or get_settings()
    provider = get_market_data_provider(resolved_settings)
    status = _normalize_provider_status(provider.get_provider_status())

    return {
        "summary": _build_summary(status),
        "recommended_action": _build_recommended_action(status),
        "quick_checks": _build_quick_checks(resolved_settings, status),
        "request_diagnostics": _build_request_diagnostics(provider, status),
        "settings": {
            "data_provider": resolved_settings.data_provider.value,
            "real_provider_name": resolved_settings.real_provider_name,
            "real_provider_base_url_configured": bool(resolved_settings.real_provider_base_url),
            "real_provider_api_key_env": resolved_settings.real_provider_api_key_env or None,
            "real_provider_api_key_header": resolved_settings.real_provider_api_key_header,
        },
        "provider_status": status,
    }


def _normalize_provider_status(status: dict[str, Any]) -> dict[str, Any]:
    """补齐 HTTP Schema 默认字段，使命令行输出和 /provider/status 响应保持一致。"""

    normalized_status = dict(status)
    normalized_status.setdefault("source_type", "mock")
    normalized_status.setdefault("active_source", "provider")
    normalized_status.setdefault("missing_configuration", [])
    normalized_status.setdefault("next_action", None)
    return normalized_status


def _build_summary(status: dict[str, Any]) -> str:
    """把 Provider 状态压缩成一行可读说明，便于终端快速判断当前数据来源。"""

    source_type = status.get("source_type")
    if status.get("mode") == DataProviderMode.MOCK.value:
        return "当前使用 Mock Provider，本地演示数据可用。"
    if source_type == "demo_provider":
        return "当前使用 DemoProvider，本地样例 Adapter 已跑通 real 模式链路。"
    if source_type == "yahoo_finance":
        return "当前使用 Yahoo Finance 无 Key 公开行情，Quote 和 K 线优先展示延迟真实行情。"
    if source_type == "real_http_configured":
        return "真实 HTTP Provider 配置已填写，但仍处于供应商响应验证阶段，当前保留 Mock 回退。"
    if source_type == "real_placeholder":
        return "真实 Provider 配置不完整，当前只能使用 Mock 回退。"
    return "Provider 状态未知，请检查 DATA_PROVIDER 和 REAL_PROVIDER_NAME 配置。"


def _build_recommended_action(status: dict[str, Any]) -> str:
    """根据状态给出下一步开发动作，不读取或展示任何真实密钥。"""

    next_action = status.get("next_action")
    if isinstance(next_action, str) and next_action:
        return next_action
    if status.get("source_type") == "demo_provider":
        return "可继续用个股研究页验证 Demo Quote 与 K 线；接真实供应商时替换 REAL_PROVIDER_NAME。"
    if status.get("source_type") == "yahoo_finance":
        return "启动后端后检查 US/NVDA、HK/00700.HK、CN/600519.SH 和 CN/300750.SZ 的 Quote 与 K 线来源标签。"
    if status.get("mode") == DataProviderMode.MOCK.value:
        return "如需验证 real 模式，可设置 DATA_PROVIDER=real 且 REAL_PROVIDER_NAME=DemoProvider。"
    return "查看 provider_status.missing_configuration、fallback_reason 和 data_status。"


def _build_quick_checks(settings: Settings, status: dict[str, Any]) -> list[dict[str, str]]:
    """生成启动后端后可直接访问的检查路径，帮助确认页面实际数据源。"""

    api_prefix = settings.api_prefix.rstrip("/")
    checks = [
        {
            "name": "Provider status",
            "path": f"{api_prefix}/provider/status",
            "expected": str(status.get("source_type", "unknown")),
        },
        {
            "name": "US market overview",
            "path": f"{api_prefix}/market/overview?market=US",
            "expected": "market data status should match provider mode or database switch",
        },
    ]

    symbols = [("US", "NVDA")]
    if status.get("source_type") == "demo_provider":
        symbols = [("US", "NVDA"), ("HK", "00700.HK"), ("CN", "600519.SH")]
    if status.get("source_type") == "yahoo_finance":
        symbols = [("US", "NVDA"), ("HK", "00700.HK"), ("CN", "600519.SH"), ("CN", "300750.SZ")]

    for market, symbol in symbols:
        checks.append(
            {
                "name": f"{market} stock research {symbol}",
                "path": f"{api_prefix}/stock/research?market={market}&symbol={symbol}",
                "expected": "quote_data_source and kline_data_source should match current provider status",
            }
        )

    return checks


def _build_request_diagnostics(
    provider: object,
    status: dict[str, Any],
) -> list[dict[str, Any]]:
    """生成真实 Provider 请求预览，不访问外网，也不展示真实 API Key。"""

    if not isinstance(provider, RealMarketDataProvider):
        return []

    symbols = [(MarketCode.US, "NVDA")]
    if status.get("source_type") == "demo_provider":
        symbols = [
            (MarketCode.US, "NVDA"),
            (MarketCode.HK, "00700.HK"),
            (MarketCode.CN, "600519.SH"),
        ]
    if status.get("source_type") == "yahoo_finance":
        symbols = [
            (MarketCode.US, "NVDA"),
            (MarketCode.HK, "00700.HK"),
            (MarketCode.CN, "600519.SH"),
            (MarketCode.CN, "300750.SZ"),
        ]

    diagnostics: list[dict[str, Any]] = []
    for market, symbol in symbols:
        quote_request = provider.build_quote_request(market, symbol)
        bars_request = provider.build_bars_request(market, symbol)
        diagnostics.extend(
            [
                _summarize_request("quote", quote_request),
                _summarize_request("bars", bars_request),
            ]
        )

    return diagnostics


def _summarize_request(kind: str, request: dict[str, Any]) -> dict[str, Any]:
    """压缩请求描述，只保留诊断所需字段，避免输出密钥明文。"""

    return {
        "kind": kind,
        "provider_name": request["provider_name"],
        "method": request["method"],
        "url": request["url"],
        "market": request["market"],
        "symbol": request["symbol"],
        "api_key_env": request["api_key_env"],
        "api_key_configured": request["api_key_configured"],
        "missing_configuration": request["missing_configuration"],
    }


def dumps_provider_status_report(report: dict[str, Any], *, ascii_only: bool = False) -> str:
    """序列化检查报告；ascii_only 用于兼容 Windows 终端中文编码异常。"""

    return json.dumps(report, ensure_ascii=ascii_only, indent=2, default=str)


def parse_args() -> argparse.Namespace:
    """解析命令行参数，保持默认中文输出，同时提供 ASCII 兜底模式。"""

    parser = argparse.ArgumentParser(description="Check current AI Quant Terminal market data provider status.")
    parser.add_argument(
        "--ascii",
        action="store_true",
        help="escape non-ASCII characters for terminals that cannot render Chinese output correctly",
    )
    return parser.parse_args()


def main() -> None:
    """命令行入口：python -m app.providers.provider_status_check。"""

    args = parse_args()
    print(dumps_provider_status_report(build_provider_status_report(), ascii_only=args.ascii))


if __name__ == "__main__":
    main()

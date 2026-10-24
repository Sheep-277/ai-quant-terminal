import argparse
import json
from pathlib import Path
from typing import Any, Literal, Mapping

from app.core.config import Settings, get_settings
from app.core.exceptions import ProviderResponseError
from app.providers.real_market_data import RealMarketDataProvider
from app.schemas.market import DataStatus


FixtureKind = Literal["quote", "bars"]


def validate_provider_fixture(
    payload: object,
    *,
    kind: FixtureKind,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """验证供应商 JSON 样例能否被当前 Provider 映射归一化。"""

    resolved_settings = settings or get_settings()
    provider = RealMarketDataProvider(settings=resolved_settings)

    try:
        normalized_data = _normalize_fixture(provider, payload, kind=kind)
    except ProviderResponseError as exc:
        return {
            "ok": False,
            "kind": kind,
            "provider_name": resolved_settings.real_provider_name,
            "error": str(exc),
            "retryable": exc.retryable,
        }

    return {
        "ok": True,
        "kind": kind,
        "provider_name": resolved_settings.real_provider_name,
        "normalized_data": normalized_data,
    }


def _normalize_fixture(
    provider: RealMarketDataProvider,
    payload: object,
    *,
    kind: FixtureKind,
) -> Any:
    """根据样例类型选择 Quote 或 K 线归一化流程。"""

    if kind == "quote":
        quote_payload = _extract_quote_payload(payload, provider_name=provider.get_provider_status()["provider_name"])
        return provider.normalize_quote_response(quote_payload, data_status=DataStatus.DELAYED)

    raw_bars = provider._extract_bars_payload(payload)
    bars: list[Mapping[str, object]] = []
    for item in raw_bars:
        if not isinstance(item, dict):
            raise ProviderResponseError(
                "真实行情 Provider K 线数组元素必须是对象。",
                provider_name=provider.get_provider_status()["provider_name"],
                retryable=False,
            )
        bars.append(item)
    return provider.normalize_bars_response(bars)


def _extract_quote_payload(payload: object, *, provider_name: str) -> Mapping[str, object]:
    """提取 Quote 对象，兼容 data/quote/result 常见包装层。"""

    if not isinstance(payload, dict):
        raise ProviderResponseError(
            "真实行情 Provider Quote JSON 必须是对象。",
            provider_name=provider_name,
            retryable=False,
        )

    for key in ("data", "quote", "result"):
        wrapped_payload = payload.get(key)
        if isinstance(wrapped_payload, dict):
            return wrapped_payload
        if wrapped_payload is not None:
            raise ProviderResponseError(
                f"真实行情 Provider 字段 {key} 必须是对象。",
                provider_name=provider_name,
                retryable=False,
            )

    return payload


def load_fixture_payload(path: Path) -> object:
    """从本地 JSON 文件读取供应商样例响应。"""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProviderResponseError(
            "供应商样例文件不是有效 JSON。",
            provider_name="ProviderFixtureCheck",
            retryable=False,
        ) from exc


def dumps_fixture_report(report: dict[str, Any], *, ascii_only: bool = False) -> str:
    """序列化样例验证报告；ascii_only 用于兼容 Windows 终端中文编码异常。"""

    return json.dumps(report, ensure_ascii=ascii_only, indent=2, default=str)


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(description="Validate a provider JSON fixture against current field mapping.")
    parser.add_argument("--kind", choices=("quote", "bars"), required=True, help="fixture payload type")
    parser.add_argument("--file", required=True, help="path to provider JSON fixture")
    parser.add_argument(
        "--ascii",
        action="store_true",
        help="escape non-ASCII characters for terminals that cannot render Chinese output correctly",
    )
    return parser.parse_args()


def main() -> None:
    """命令行入口：python -m app.providers.provider_fixture_check。"""

    args = parse_args()
    payload = load_fixture_payload(Path(args.file))
    report = validate_provider_fixture(payload, kind=args.kind)
    print(dumps_fixture_report(report, ascii_only=args.ascii))


if __name__ == "__main__":
    main()

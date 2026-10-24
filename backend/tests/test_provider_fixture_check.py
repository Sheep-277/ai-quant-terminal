from app.core.config import Settings
from app.providers.provider_fixture_check import (
    dumps_fixture_report,
    load_fixture_payload,
    validate_provider_fixture,
)


def test_provider_fixture_check_validates_quote_payload() -> None:
    # 供应商 Quote 样例可以先离线验证字段映射，再接入 HTTP 请求。
    report = validate_provider_fixture(
        {
            "data": {
                "lastPrice": "182.50",
                "priceChange": "1.50",
                "changeRate": "0.00829",
                "tradeVolume": "1000",
                "turnoverValue": "182500",
            }
        },
        kind="quote",
        settings=Settings(DATA_PROVIDER="real", REAL_PROVIDER_NAME="VendorHttpProvider", _env_file=None),
    )

    assert report == {
        "ok": True,
        "kind": "quote",
        "provider_name": "VendorHttpProvider",
        "normalized_data": {
            "price": 182.5,
            "change": 1.5,
            "change_percent": 0.00829,
            "volume": 1000,
            "turnover": 182500.0,
            "data_status": "delayed",
        },
    }


def test_provider_fixture_check_validates_bars_payload() -> None:
    # K 线样例验证会经过包装层提取、字段映射和 OHLC 合法性校验。
    report = validate_provider_fixture(
        {
            "result": {
                "items": [
                    {"o": "180.00", "h": "183.00", "l": "179.50", "c": "182.50", "v": "1000"},
                    {"o": "182.50", "h": "184.20", "l": "181.80", "c": "183.75", "v": "1200"},
                ]
            }
        },
        kind="bars",
        settings=Settings(DATA_PROVIDER="real", REAL_PROVIDER_NAME="VendorHttpProvider", _env_file=None),
    )

    assert report == {
        "ok": True,
        "kind": "bars",
        "provider_name": "VendorHttpProvider",
        "normalized_data": [
            {
                "offset": 1,
                "open": 180.0,
                "high": 183.0,
                "low": 179.5,
                "close": 182.5,
                "volume": 1000,
            },
            {
                "offset": 0,
                "open": 182.5,
                "high": 184.2,
                "low": 181.8,
                "close": 183.75,
                "volume": 1200,
            },
        ],
    }


def test_provider_fixture_check_reports_invalid_quote_payload() -> None:
    # 缺少必填字段时返回失败报告，不抛到命令行导致堆栈干扰学习调试。
    report = validate_provider_fixture(
        {"data": {"lastPrice": "182.50"}},
        kind="quote",
        settings=Settings(DATA_PROVIDER="real", REAL_PROVIDER_NAME="VendorHttpProvider", _env_file=None),
    )

    assert report["ok"] is False
    assert report["kind"] == "quote"
    assert report["provider_name"] == "VendorHttpProvider"
    assert "Quote 响应缺少必填字段" in report["error"]
    assert report["retryable"] is False


def test_provider_fixture_check_loads_json_file_and_dumps_ascii() -> None:
    # 命令行入口使用同一套读取与序列化逻辑；ASCII 输出用于兼容 Windows 终端。
    from pathlib import Path

    fixture_path = Path("tests/fixtures/provider_quote_fixture.json")

    payload = load_fixture_payload(fixture_path)
    report = validate_provider_fixture(
        payload,
        kind="quote",
        settings=Settings(DATA_PROVIDER="real", REAL_PROVIDER_NAME="VendorHttpProvider", _env_file=None),
    )
    serialized = dumps_fixture_report(report, ascii_only=True)

    assert '"ok": true' in serialized
    assert '"provider_name": "VendorHttpProvider"' in serialized
    assert '"data_status": "delayed"' in serialized


def test_provider_fixture_check_loads_bars_json_file() -> None:
    # 仓库内保留一份 K 线样例，方便开发者直接运行命令验证 bars 归一化。
    from pathlib import Path

    fixture_path = Path("tests/fixtures/provider_bars_fixture.json")

    payload = load_fixture_payload(fixture_path)
    report = validate_provider_fixture(
        payload,
        kind="bars",
        settings=Settings(DATA_PROVIDER="real", REAL_PROVIDER_NAME="VendorHttpProvider", _env_file=None),
    )

    assert report["ok"] is True
    assert report["kind"] == "bars"
    assert report["provider_name"] == "VendorHttpProvider"
    assert report["normalized_data"][-1] == {
        "offset": 0,
        "open": 182.5,
        "high": 184.2,
        "low": 181.8,
        "close": 183.75,
        "volume": 1200,
    }

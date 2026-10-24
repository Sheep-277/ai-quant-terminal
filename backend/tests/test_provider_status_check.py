from app.core.config import Settings
from app.providers.provider_status_check import build_provider_status_report, dumps_provider_status_report


def test_provider_status_check_reports_mock_mode() -> None:
    # 本地默认模式应明确提示 Mock Provider，避免开发者误以为已经接入真实行情。
    report = build_provider_status_report(Settings(DATA_PROVIDER="mock", _env_file=None))

    assert report["summary"] == "当前使用 Mock Provider，本地演示数据可用。"
    assert report["settings"]["data_provider"] == "mock"
    assert report["provider_status"]["source_type"] == "mock"
    assert report["quick_checks"][0]["path"] == "/api/v1/provider/status"
    assert report["quick_checks"][-1]["path"] == "/api/v1/stock/research?market=US&symbol=NVDA"
    assert report["request_diagnostics"] == []
    assert "DATA_PROVIDER=real" in report["recommended_action"]


def test_provider_status_check_reports_demo_provider() -> None:
    # DemoProvider 是 real 模式下的本地样例 Adapter，应和真实 HTTP 待验证状态区分开。
    report = build_provider_status_report(
        Settings(
            DATA_PROVIDER="real",
            REAL_PROVIDER_NAME="DemoProvider",
            REAL_PROVIDER_BASE_URL="https://provider.example.test",
            REAL_PROVIDER_API_KEY_ENV="",
            _env_file=None,
        )
    )

    assert report["summary"] == "当前使用 DemoProvider，本地样例 Adapter 已跑通 real 模式链路。"
    assert report["settings"]["data_provider"] == "real"
    assert report["settings"]["real_provider_base_url_configured"] is True
    assert report["provider_status"]["ready"] is True
    assert report["provider_status"]["source_type"] == "demo_provider"
    assert [check["path"] for check in report["quick_checks"][-3:]] == [
        "/api/v1/stock/research?market=US&symbol=NVDA",
        "/api/v1/stock/research?market=HK&symbol=00700.HK",
        "/api/v1/stock/research?market=CN&symbol=600519.SH",
    ]
    assert [request["url"] for request in report["request_diagnostics"]] == [
        "https://provider.example.test/quotes/US/NVDA",
        "https://provider.example.test/bars/US/NVDA?interval=1d&count=30",
        "https://provider.example.test/quotes/HK/00700.HK",
        "https://provider.example.test/bars/HK/00700.HK?interval=1d&count=30",
        "https://provider.example.test/quotes/CN/600519.SH",
        "https://provider.example.test/bars/CN/600519.SH?interval=1d&count=30",
    ]
    assert all(request["api_key_configured"] is False for request in report["request_diagnostics"])


def test_provider_status_check_reports_yahoo_finance_provider() -> None:
    # YahooFinance 是无 Key 公开行情路径，检查报告应直接列出三市场验收标的。
    report = build_provider_status_report(
        Settings(
            DATA_PROVIDER="real",
            REAL_PROVIDER_NAME="YahooFinance",
            REAL_PROVIDER_BASE_URL="https://query1.finance.yahoo.com",
            REAL_PROVIDER_API_KEY_ENV="",
            _env_file=None,
        )
    )

    assert report["summary"] == "当前使用 Yahoo Finance 无 Key 公开行情，Quote 和 K 线优先展示延迟真实行情。"
    assert report["provider_status"]["ready"] is True
    assert report["provider_status"]["source_type"] == "yahoo_finance"
    assert report["provider_status"]["active_source"] == "yahoo_finance"
    assert [check["path"] for check in report["quick_checks"][-4:]] == [
        "/api/v1/stock/research?market=US&symbol=NVDA",
        "/api/v1/stock/research?market=HK&symbol=00700.HK",
        "/api/v1/stock/research?market=CN&symbol=600519.SH",
        "/api/v1/stock/research?market=CN&symbol=300750.SZ",
    ]
    assert [request["symbol"] for request in report["request_diagnostics"]] == [
        "NVDA",
        "NVDA",
        "00700.HK",
        "00700.HK",
        "600519.SH",
        "600519.SH",
        "300750.SZ",
        "300750.SZ",
    ]
    assert all(request["api_key_configured"] is False for request in report["request_diagnostics"])
    assert all(request["missing_configuration"] == [] for request in report["request_diagnostics"])


def test_provider_status_check_reports_real_http_pending(monkeypatch) -> None:
    # 非 Demo 真实 Provider 配置齐全时，仍应提示处于供应商响应验证阶段。
    monkeypatch.setenv("VENDOR_API_KEY", "test-token")

    report = build_provider_status_report(
        Settings(
            DATA_PROVIDER="real",
            REAL_PROVIDER_NAME="VendorHttpProvider",
            REAL_PROVIDER_BASE_URL="https://provider.example.test",
            REAL_PROVIDER_API_KEY_ENV="VENDOR_API_KEY",
            _env_file=None,
        )
    )

    assert report["summary"] == "真实 HTTP Provider 配置已填写，但仍处于供应商响应验证阶段，当前保留 Mock 回退。"
    assert report["settings"]["real_provider_api_key_env"] == "VENDOR_API_KEY"
    assert "test-token" not in str(report)
    assert report["provider_status"]["source_type"] == "real_http_configured"
    assert report["provider_status"]["fallback_active"] is True
    assert report["quick_checks"][0]["expected"] == "real_http_configured"
    assert report["request_diagnostics"] == [
        {
            "kind": "quote",
            "provider_name": "VendorHttpProvider",
            "method": "GET",
            "url": "https://provider.example.test/quotes/US/NVDA",
            "market": "US",
            "symbol": "NVDA",
            "api_key_env": "VENDOR_API_KEY",
            "api_key_configured": True,
            "missing_configuration": [],
        },
        {
            "kind": "bars",
            "provider_name": "VendorHttpProvider",
            "method": "GET",
            "url": "https://provider.example.test/bars/US/NVDA?interval=1d&count=30",
            "market": "US",
            "symbol": "NVDA",
            "api_key_env": "VENDOR_API_KEY",
            "api_key_configured": True,
            "missing_configuration": [],
        },
    ]


def test_provider_status_check_can_dump_ascii_json() -> None:
    # Windows 终端中文编码异常时，可以使用 ASCII escaped JSON 读取同一份报告。
    report = build_provider_status_report(Settings(DATA_PROVIDER="mock", _env_file=None))

    payload = dumps_provider_status_report(report, ascii_only=True)

    assert "\\u5f53\\u524d\\u4f7f\\u7528 Mock Provider" in payload
    assert '"source_type": "mock"' in payload


def test_provider_status_check_reports_missing_real_request_configuration() -> None:
    # 缺配置状态也输出请求诊断，开发者可以直接看到 URL 为 None 且缺哪些环境变量。
    report = build_provider_status_report(Settings(DATA_PROVIDER="real", _env_file=None))

    assert report["provider_status"]["source_type"] == "real_placeholder"
    assert report["request_diagnostics"] == [
        {
            "kind": "quote",
            "provider_name": "RealMarketDataProvider",
            "method": "GET",
            "url": None,
            "market": "US",
            "symbol": "NVDA",
            "api_key_env": None,
            "api_key_configured": False,
            "missing_configuration": ["REAL_PROVIDER_BASE_URL", "REAL_PROVIDER_API_KEY_ENV"],
        },
        {
            "kind": "bars",
            "provider_name": "RealMarketDataProvider",
            "method": "GET",
            "url": None,
            "market": "US",
            "symbol": "NVDA",
            "api_key_env": None,
            "api_key_configured": False,
            "missing_configuration": ["REAL_PROVIDER_BASE_URL", "REAL_PROVIDER_API_KEY_ENV"],
        },
    ]

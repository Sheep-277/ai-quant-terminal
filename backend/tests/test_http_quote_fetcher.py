import os
from urllib.error import URLError
from urllib.request import Request

import pytest

from app.core.exceptions import ProviderResponseError
from app.providers.http_quote_fetcher import HttpQuoteFetcher, RealProviderReadRequest


def build_request(**overrides: object) -> RealProviderReadRequest:
    request: RealProviderReadRequest = {
        "provider_name": "DemoProvider",
        "method": "GET",
        "url": "https://provider.example.test/quotes/US/NVDA",
        "market": "US",
        "symbol": "NVDA",
        "api_key_env": "DEMO_PROVIDER_API_KEY",
        "api_key_configured": True,
        "missing_configuration": [],
    }
    request.update(overrides)
    return request


def test_http_quote_fetcher_returns_none_when_configuration_is_missing() -> None:
    # 配置不完整时不发外部请求，让 RealMarketDataProvider 继续走 Mock 回退。
    request = build_request(missing_configuration=["REAL_PROVIDER_BASE_URL"], url=None)
    fetcher = HttpQuoteFetcher()

    assert fetcher.fetch_quote(request) is None


def test_http_quote_fetcher_reads_json_with_authorization_header(monkeypatch: pytest.MonkeyPatch) -> None:
    # 测试通过注入 opener 完成，不访问真实网络。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    captured_request: Request | None = None

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"last": "182.50", "change": "1.50"}'

    def fake_opener(http_request: Request, *, timeout: float) -> FakeResponse:
        nonlocal captured_request
        captured_request = http_request
        assert timeout == 3.0
        return FakeResponse()

    fetcher = HttpQuoteFetcher(timeout_seconds=3.0, opener=fake_opener)

    payload = fetcher.fetch_quote(build_request())

    assert payload == {"last": "182.50", "change": "1.50"}
    assert captured_request is not None
    assert captured_request.full_url == "https://provider.example.test/quotes/US/NVDA"
    assert captured_request.get_method() == "GET"
    assert captured_request.get_header("Authorization") == "Bearer test-token"


def test_http_quote_fetcher_reads_json_with_custom_api_key_header(monkeypatch: pytest.MonkeyPatch) -> None:
    # 部分供应商不用 Authorization Bearer，而是要求 X-API-Key 这类自定义请求头。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    captured_request: Request | None = None

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"last": "182.50", "change": "1.50"}'

    def fake_opener(http_request: Request, *, timeout: float) -> FakeResponse:
        nonlocal captured_request
        captured_request = http_request
        return FakeResponse()

    fetcher = HttpQuoteFetcher(api_key_header="X-API-Key", opener=fake_opener)

    payload = fetcher.fetch_quote(build_request())

    assert payload == {"last": "182.50", "change": "1.50"}
    assert captured_request is not None
    assert captured_request.get_header("X-api-key") == "test-token"
    assert captured_request.get_header("Authorization") is None


def test_http_quote_fetcher_fetch_json_allows_future_bar_array_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 历史 K 线供应商常返回数组；通用 fetch_json 只负责读取 JSON，不强行套用 Quote 对象约束。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'[{"open": "180.0", "high": "183.0", "low": "179.5", "close": "182.5"}]'

    fetcher = HttpQuoteFetcher(opener=lambda *_args, **_kwargs: FakeResponse())

    payload = fetcher.fetch_json(build_request(url="https://provider.example.test/bars/US/NVDA"))

    assert payload == [{"open": "180.0", "high": "183.0", "low": "179.5", "close": "182.5"}]


@pytest.mark.parametrize("wrapper_key", ["data", "bars", "result"])
def test_http_quote_fetcher_fetch_json_unwraps_bar_array_payloads(
    monkeypatch: pytest.MonkeyPatch,
    wrapper_key: str,
) -> None:
    # K 线读取允许供应商把数组包在 data、bars 或 result 下，由 Provider 层再继续提取业务字段。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return f'{{"{wrapper_key}": [{{"open": "180.0", "high": "183.0"}}]}}'.encode("utf-8")

    fetcher = HttpQuoteFetcher(opener=lambda *_args, **_kwargs: FakeResponse())

    payload = fetcher.fetch_json(
        build_request(url="https://provider.example.test/bars/US/NVDA"),
        wrapper_keys=("data", "bars", "result"),
        require_wrapped_object=False,
    )

    assert payload == [{"open": "180.0", "high": "183.0"}]


def test_http_quote_fetcher_fetch_json_rejects_wrapped_array_when_object_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Quote 读取要求包装层下必须是对象；这个规则不能被 K 线数组兼容逻辑放宽。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"data": [{"last": "182.50"}]}'

    fetcher = HttpQuoteFetcher(opener=lambda *_args, **_kwargs: FakeResponse())

    with pytest.raises(ProviderResponseError, match="字段 data 必须是对象") as error:
        fetcher.fetch_json(
            build_request(),
            wrapper_keys=("data", "quote", "result"),
            require_wrapped_object=True,
        )

    assert error.value.provider_name == "DemoProvider"
    assert error.value.retryable is False


@pytest.mark.parametrize("wrapper_key", ["data", "quote", "result"])
def test_http_quote_fetcher_unwraps_common_quote_payloads(
    monkeypatch: pytest.MonkeyPatch,
    wrapper_key: str,
) -> None:
    # 不同供应商常把 Quote 对象放在 data、quote 或 result 字段下，fetcher 先做一层兼容解包。
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return f'{{"{wrapper_key}": {{"last": "182.50", "change": "1.50"}}}}'.encode("utf-8")

    fetcher = HttpQuoteFetcher(opener=lambda *_args, **_kwargs: FakeResponse())

    assert fetcher.fetch_quote(build_request()) == {"last": "182.50", "change": "1.50"}


def test_http_quote_fetcher_does_not_store_secret_in_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")
    request = build_request()

    assert os.getenv("DEMO_PROVIDER_API_KEY") == "test-token"
    assert "test-token" not in str(request)


def test_http_quote_fetcher_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"not-json"

    fetcher = HttpQuoteFetcher(opener=lambda *_args, **_kwargs: FakeResponse())

    with pytest.raises(ProviderResponseError, match="无效 JSON") as error:
        fetcher.fetch_quote(build_request())

    assert error.value.provider_name == "DemoProvider"
    assert error.value.retryable is True


def test_http_quote_fetcher_rejects_non_object_quote_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"data": []}'

    fetcher = HttpQuoteFetcher(opener=lambda *_args, **_kwargs: FakeResponse())

    with pytest.raises(ProviderResponseError, match="字段 data 必须是对象") as error:
        fetcher.fetch_quote(build_request())

    assert error.value.provider_name == "DemoProvider"
    assert error.value.retryable is False


def test_http_quote_fetcher_wraps_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_PROVIDER_API_KEY", "test-token")

    def fake_opener(*_args: object, **_kwargs: object) -> object:
        raise URLError("connection refused")

    fetcher = HttpQuoteFetcher(opener=fake_opener)

    with pytest.raises(ProviderResponseError, match="请求失败") as error:
        fetcher.fetch_quote(build_request())

    assert error.value.provider_name == "DemoProvider"
    assert error.value.retryable is True

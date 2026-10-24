import json
import os
from collections.abc import Callable
from typing import Any, Literal, Mapping, NotRequired, Protocol, TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.exceptions import ProviderResponseError

JsonPayload = Mapping[str, object] | list[object]


class RealProviderReadRequest(TypedDict):
    """真实 Provider 只读请求描述；Quote 和历史 K 线 HTTP 读取可复用该结构。"""

    provider_name: str
    method: Literal["GET"]
    url: str | None
    market: str
    symbol: str
    api_key_env: str | None
    api_key_configured: bool
    missing_configuration: list[str]
    interval: NotRequired[str]
    count: NotRequired[int]
    start: NotRequired[str | None]
    end: NotRequired[str | None]


class ProviderJsonFetcher(Protocol):
    """真实 Provider JSON 获取接口；Quote 和历史 K 线 Adapter 后续实现该协议。"""

    def fetch_quote(self, request: RealProviderReadRequest) -> Mapping[str, object] | None:
        """根据标准请求描述返回供应商原始 Quote，不应在这里泄露密钥明文。"""

    def fetch_json(
        self,
        request: RealProviderReadRequest,
        *,
        wrapper_keys: tuple[str, ...] = (),
        require_wrapped_object: bool = False,
    ) -> JsonPayload | None:
        """根据标准请求描述返回供应商原始 JSON，允许对象或数组 payload。"""


class QuoteFetcher(ProviderJsonFetcher, Protocol):
    """兼容旧命名的 Provider fetcher 协议，后续可逐步迁移到 ProviderJsonFetcher。"""


class HttpQuoteFetcher:
    """HTTP Provider 获取器；负责读取供应商原始 JSON，不做行情字段归一化。"""

    _QUOTE_WRAPPER_KEYS = ("data", "quote", "result")

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        api_key_header: str = "Authorization",
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        """允许测试注入 opener，生产环境默认使用标准库 urlopen 发起 GET 请求。"""

        self._timeout_seconds = timeout_seconds
        self._api_key_header = api_key_header
        self._opener = opener

    def fetch_quote(self, request: RealProviderReadRequest) -> Mapping[str, object] | None:
        """读取真实 Quote JSON；配置不完整时返回 None，让上层继续走 Mock 回退。"""

        payload = self.fetch_json(
            request,
            wrapper_keys=self._QUOTE_WRAPPER_KEYS,
            require_wrapped_object=True,
        )
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise ProviderResponseError(
                "真实行情 Provider Quote JSON 必须是对象。",
                provider_name=request["provider_name"],
                retryable=False,
            )

        return payload

    def fetch_json(
        self,
        request: RealProviderReadRequest,
        *,
        wrapper_keys: tuple[str, ...] = (),
        require_wrapped_object: bool = False,
    ) -> JsonPayload | None:
        """读取真实 Provider JSON，供 Quote 和后续历史 K 线 HTTP 请求复用。"""

        if request["missing_configuration"] or request["url"] is None:
            return None

        api_key = self._read_api_key(request)
        if api_key is None:
            return None

        http_request = Request(
            request["url"],
            method=request["method"],
            headers=self._build_headers(api_key),
        )

        try:
            with self._opener(http_request, timeout=self._timeout_seconds) as response:
                payload = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise ProviderResponseError(
                "真实行情 Provider 请求失败。",
                provider_name=request["provider_name"],
                retryable=True,
            ) from exc

        return self._parse_json_payload(
            payload,
            provider_name=request["provider_name"],
            wrapper_keys=wrapper_keys,
            require_wrapped_object=require_wrapped_object,
        )

    def _read_api_key(self, request: RealProviderReadRequest) -> str | None:
        """只根据环境变量名读取密钥，不把密钥写入请求描述或日志结构。"""

        api_key_env = request["api_key_env"]
        if api_key_env is None:
            return None

        return os.getenv(api_key_env)

    def _build_headers(self, api_key: str) -> dict[str, str]:
        """构造供应商请求头，默认使用 Bearer，也允许配置 X-API-Key 等自定义头。"""

        headers = {"Accept": "application/json"}
        if self._api_key_header.lower() == "authorization":
            headers["Authorization"] = f"Bearer {api_key}"
            return headers

        headers[self._api_key_header] = api_key
        return headers

    def _parse_json_payload(
        self,
        payload: str,
        *,
        provider_name: str,
        wrapper_keys: tuple[str, ...],
        require_wrapped_object: bool,
    ) -> JsonPayload:
        """解析供应商 JSON 响应；Quote 要求对象，K 线后续可复用数组 payload。"""

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ProviderResponseError(
                "真实行情 Provider 返回了无效 JSON。",
                provider_name=provider_name,
                retryable=True,
            ) from exc

        if not isinstance(data, dict):
            if not wrapper_keys and isinstance(data, list):
                return data
            raise ProviderResponseError(
                "真实行情 Provider JSON 顶层必须是对象。",
                provider_name=provider_name,
                retryable=False,
            )

        if not wrapper_keys:
            return data

        return self._unwrap_payload(
            data,
            provider_name=provider_name,
            wrapper_keys=wrapper_keys,
            require_wrapped_object=require_wrapped_object,
        )

    def _unwrap_payload(
        self,
        data: Mapping[str, object],
        *,
        provider_name: str,
        wrapper_keys: tuple[str, ...],
        require_wrapped_object: bool,
    ) -> JsonPayload:
        """兼容常见供应商包装结构，例如 data、quote、result 包住真正业务 payload。"""

        for key in wrapper_keys:
            wrapped_data = data.get(key)
            if isinstance(wrapped_data, dict):
                return wrapped_data
            if isinstance(wrapped_data, list) and not require_wrapped_object:
                return wrapped_data
            if wrapped_data is not None:
                raise ProviderResponseError(
                    f"真实行情 Provider 字段 {key} 必须是对象。",
                    provider_name=provider_name,
                    retryable=False,
                )

        return data

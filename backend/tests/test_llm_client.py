import json
from io import BytesIO
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from app.agents.llm_client import BailianLLMClient, LLMClientError
from app.core.config import Settings
from app.core.market import MarketCode


class FakeResponse:
    """测试用 HTTP 响应对象，模拟 urllib 返回的上下文管理器。"""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def test_bailian_client_normalizes_compatible_mode_base_url() -> None:
    settings = Settings(
        BAILIAN_API_KEY="test-token",
        BAILIAN_BASE_URL="dashscope.aliyuncs.com/compatible-mode/v1",
        _env_file=None,
    )
    client = BailianLLMClient(settings)

    assert client._chat_completions_url() == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


def test_bailian_client_keeps_full_chat_completions_url() -> None:
    settings = Settings(
        BAILIAN_API_KEY="test-token",
        BAILIAN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        _env_file=None,
    )
    client = BailianLLMClient(settings)

    assert client._chat_completions_url() == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


def test_bailian_client_sends_openai_compatible_request() -> None:
    captured_request: dict[str, Any] = {}

    def fake_opener(request: Request, *, timeout: float) -> FakeResponse:
        captured_request["url"] = request.full_url
        captured_request["timeout"] = timeout
        captured_request["headers"] = dict(request.header_items())
        captured_request["body"] = request.data.decode("utf-8") if request.data else ""
        return FakeResponse(b'{"choices":[{"message":{"content":"LLM summary"}}]}')

    settings = Settings(
        BAILIAN_API_KEY="test-token",
        BAILIAN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1",
        BAILIAN_MODEL="qwen-plus",
        BAILIAN_TIMEOUT_SECONDS=31,
        BAILIAN_SUMMARY_MAX_TOKENS=256,
        _env_file=None,
    )
    client = BailianLLMClient(settings, opener=fake_opener)

    summary = client.summarize_research(
        market=MarketCode.US,
        query="分析 NVDA",
        symbol="NVDA",
        factors={"momentum_20d": 0.1},
        signals=[],
        strategy={"entry_matched": True, "exit_matched": False},
    )

    assert summary == "LLM summary"
    assert captured_request["url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert captured_request["timeout"] == 31
    assert captured_request["headers"]["Authorization"] == "Bearer test-token"
    request_body = json.loads(captured_request["body"])
    user_payload = json.loads(request_body["messages"][1]["content"])
    assert request_body["model"] == "qwen-plus"
    assert request_body["max_tokens"] == 256
    assert user_payload["symbol"] == "NVDA"


def test_bailian_client_reports_http_error_body() -> None:
    def fake_opener(_request: Request, *, timeout: float) -> FakeResponse:
        raise HTTPError(
            url="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=BytesIO(b'{"message":"invalid api key"}'),
        )

    settings = Settings(
        BAILIAN_API_KEY="bad-token",
        BAILIAN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1",
        _env_file=None,
    )
    client = BailianLLMClient(settings, opener=fake_opener)

    with pytest.raises(LLMClientError, match='Bailian LLM HTTP 401: \\{"message":"invalid api key"\\}'):
        client.summarize_research(
            market=MarketCode.US,
            query="分析 NVDA",
            symbol="NVDA",
            factors={},
            signals=[],
            strategy={},
        )


def test_bailian_client_check_connection_uses_minimal_prompt() -> None:
    captured_request: dict[str, Any] = {}

    def fake_opener(request: Request, *, timeout: float) -> FakeResponse:
        captured_request["url"] = request.full_url
        captured_request["timeout"] = timeout
        captured_request["body"] = request.data.decode("utf-8") if request.data else ""
        return FakeResponse(b'{"choices":[{"message":{"content":"ok"}}]}')

    settings = Settings(
        BAILIAN_API_KEY="test-token",
        BAILIAN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1",
        BAILIAN_MODEL="qwen-plus",
        _env_file=None,
    )
    client = BailianLLMClient(settings, timeout_seconds=2.0, opener=fake_opener)

    result = client.check_connection()

    request_body = json.loads(captured_request["body"])
    assert result == "ok"
    assert captured_request["url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert captured_request["timeout"] == 2.0
    assert request_body["model"] == "qwen-plus"
    assert request_body["messages"][1]["content"] == "ping"
    assert request_body["max_tokens"] == 8


def test_bailian_client_rejects_blank_configuration() -> None:
    settings = Settings(
        BAILIAN_API_KEY=" ",
        BAILIAN_BASE_URL=" ",
        _env_file=None,
    )
    client = BailianLLMClient(settings)

    assert client.is_configured() is False
    with pytest.raises(LLMClientError, match="not configured"):
        client.summarize_research(
            market=MarketCode.US,
            query="分析 NVDA",
            symbol="NVDA",
            factors={},
            signals=[],
            strategy={},
        )

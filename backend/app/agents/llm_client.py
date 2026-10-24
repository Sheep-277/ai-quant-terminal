from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import Settings
from app.core.market import MarketCode


class LLMResearchClient(Protocol):
    """AI Research 使用的大模型解释接口，只负责文本解释，不参与量化计算。"""

    def summarize_research(
        self,
        *,
        market: MarketCode,
        query: str,
        symbol: str,
        factors: dict[str, float | None],
        signals: list[dict[str, Any]],
        strategy: dict[str, Any],
    ) -> str:
        """根据已计算好的结构化证据生成摘要。"""


class LLMClientError(RuntimeError):
    """大模型客户端调用失败，错误信息可安全展示给前端排查配置问题。"""


class BailianLLMClient:
    """百炼 OpenAI-compatible Chat Completions 客户端。"""

    def __init__(
        self,
        settings: Settings,
        *,
        timeout_seconds: float | None = None,
        opener=urlopen,
    ) -> None:
        self._api_key = settings.bailian_api_key
        self._base_url = settings.bailian_base_url
        self._model = settings.bailian_model
        self._timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.bailian_timeout_seconds
        self._summary_max_tokens = settings.bailian_summary_max_tokens
        self._opener = opener

    def is_configured(self) -> bool:
        """检查是否具备调用百炼所需的最小配置。"""

        return bool(self._api_key and self._api_key.strip() and self._base_url and self._base_url.strip())

    def summarize_research(
        self,
        *,
        market: MarketCode,
        query: str,
        symbol: str,
        factors: dict[str, float | None],
        signals: list[dict[str, Any]],
        strategy: dict[str, Any],
    ) -> str:
        """调用百炼生成研究摘要；输入只包含公开结构化证据。"""

        if not self.is_configured():
            raise LLMClientError("Bailian LLM is not configured")

        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 AI Quant Terminal 的研究解释助手。"
                        "只能解释用户提供的结构化量化证据，不要编造实时新闻、财报或未给出的数据。"
                        "不要给买卖建议，不要声称可以保证收益。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "market": market.value,
                            "query": query,
                            "symbol": symbol,
                            "factors": factors,
                            "signals": signals,
                            "strategy": strategy,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0.2,
            "max_tokens": self._summary_max_tokens,
        }
        data = self._request_chat_completion(payload)
        return self._extract_message_content(data)

    def check_connection(self) -> str:
        """发送最小化请求检查百炼配置是否可用，不承载业务研究逻辑。"""

        if not self.is_configured():
            raise LLMClientError("Bailian LLM is not configured")

        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是连通性检查助手。只回复 ok，不要输出额外解释。",
                },
                {
                    "role": "user",
                    "content": "ping",
                },
            ],
            "temperature": 0,
            "max_tokens": 8,
        }
        data = self._request_chat_completion(payload)
        return self._extract_message_content(data)

    def _request_chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        """执行 Chat Completions 请求，并把网络和响应格式错误转换为统一异常。"""

        request = Request(
            self._chat_completions_url(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                raw_payload = response.read().decode("utf-8")
        except HTTPError as exc:
            raise LLMClientError(
                f"Bailian LLM HTTP {exc.code}: {self._read_http_error_body(exc)}"
            ) from exc
        except URLError as exc:
            raise LLMClientError(
                f"Bailian LLM network error: {self._compact_error_text(str(exc.reason))}"
            ) from exc
        except OSError as exc:
            raise LLMClientError(
                f"Bailian LLM network error: {self._compact_error_text(str(exc))}"
            ) from exc

        try:
            data = json.loads(raw_payload)
        except JSONDecodeError as exc:
            raise LLMClientError("Bailian LLM returned invalid JSON") from exc

        if not isinstance(data, dict):
            raise LLMClientError("Bailian LLM returned non-object JSON")

        return data

    def _extract_message_content(self, data: dict[str, Any]) -> str:
        """从 OpenAI-compatible 响应中提取 assistant 文本内容。"""

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMClientError("Bailian LLM response missing choices")

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise LLMClientError("Bailian LLM response missing message content")

        return content.strip()

    def _chat_completions_url(self) -> str:
        """把用户配置的 Base URL 规范化为 Chat Completions endpoint。"""

        assert self._base_url is not None
        base_url = self._base_url.strip().rstrip("/")
        if not base_url:
            raise LLMClientError("Bailian LLM base URL is empty")
        if not base_url.startswith(("http://", "https://")):
            base_url = f"https://{base_url}"
        if base_url.endswith("/chat/completions"):
            return base_url
        if base_url.endswith("/compatible-mode/v1"):
            return f"{base_url}/chat/completions"
        if base_url.endswith("/v1"):
            return f"{base_url}/chat/completions"
        return f"{base_url}/compatible-mode/v1/chat/completions"

    def _read_http_error_body(self, exc: HTTPError) -> str:
        """读取百炼 HTTP 错误正文，只保留短文本，避免前端显示过长报文。"""

        body = exc.read().decode("utf-8", errors="replace")
        if not body.strip():
            return self._compact_error_text(str(exc.reason))
        return self._compact_error_text(body)

    def _compact_error_text(self, value: str, *, max_length: int = 600) -> str:
        """压缩错误文本中的换行和多余空格，便于前端表格展示。"""

        compacted = " ".join(value.split())
        if len(compacted) <= max_length:
            return compacted
        return f"{compacted[:max_length]}..."

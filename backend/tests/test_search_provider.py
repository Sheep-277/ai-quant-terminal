import json
from typing import Any
from urllib.request import Request

import pytest

from app.core.config import SearchProviderMode, Settings
from app.providers.search_provider import (
    MockSearchProvider,
    SearchProviderError,
    SerpApiSearchProvider,
    TavilySearchProvider,
    build_news_search_provider,
)


class FakeResponse:
    """测试用 HTTP 响应对象，只实现 Provider 需要的上下文管理和 read。"""

    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_settings_reads_search_provider_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    # 搜索源配置统一从 Settings 读取，避免业务层直接读取环境变量。
    monkeypatch.setenv("SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("SEARCH_API_KEY", "test-search-token")
    monkeypatch.setenv("SEARCH_RESULT_LIMIT", "3")
    monkeypatch.setenv("SEARCH_TIMEOUT_SECONDS", "4")

    settings = Settings(_env_file=None)

    assert settings.search_provider == SearchProviderMode.TAVILY
    assert settings.search_api_key == "test-search-token"
    assert settings.search_result_limit == 3
    assert settings.search_timeout_seconds == 4


def test_build_news_search_provider_returns_configured_provider() -> None:
    # Provider 工厂根据 SEARCH_PROVIDER 返回具体实现，后续 service 不需要关心供应商分支。
    mock_settings = Settings(SEARCH_PROVIDER="mock", _env_file=None)
    tavily_settings = Settings(SEARCH_PROVIDER="tavily", SEARCH_API_KEY="test-token", _env_file=None)
    serpapi_settings = Settings(SEARCH_PROVIDER="serpapi", SEARCH_API_KEY="test-token", _env_file=None)

    assert isinstance(build_news_search_provider(mock_settings), MockSearchProvider)
    assert isinstance(build_news_search_provider(tavily_settings), TavilySearchProvider)
    assert isinstance(build_news_search_provider(serpapi_settings), SerpApiSearchProvider)


def test_tavily_search_normalizes_results_without_exposing_key() -> None:
    # 不访问真实网络，只验证请求结构和 Tavily 结果归一化。
    captured: dict[str, Any] = {}

    def fake_opener(request: Request, *, timeout: float) -> FakeResponse:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads((request.data or b"{}").decode("utf-8"))
        return FakeResponse(
            {
                "results": [
                    {
                        "title": "AI chip demand lifts Nasdaq",
                        "url": "https://example.test/news/ai-chip",
                        "content": "Semiconductor shares rose after new AI demand data.",
                        "published_date": "2026-10-12",
                    }
                ]
            }
        )

    settings = Settings(
        SEARCH_PROVIDER="tavily",
        SEARCH_API_KEY="test-token",
        SEARCH_RESULT_LIMIT=2,
        SEARCH_TIMEOUT_SECONDS=6,
        _env_file=None,
    )
    provider = TavilySearchProvider(settings, opener=fake_opener)

    results = provider.search("NVDA earnings", limit=1)

    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["timeout"] == 6
    assert captured["body"]["max_results"] == 1
    assert results == [
        {
            "title": "AI chip demand lifts Nasdaq",
            "url": "https://example.test/news/ai-chip",
            "snippet": "Semiconductor shares rose after new AI demand data.",
            "source": "Tavily",
            "published_at": "2026-10-12",
        }
    ]
    assert "test-token" not in str(results)


def test_serpapi_search_normalizes_results() -> None:
    # 不访问真实网络，只验证 SerpAPI organic_results 可转换为统一搜索结果。
    captured: dict[str, Any] = {}

    def fake_opener(request: Request, *, timeout: float) -> FakeResponse:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "organic_results": [
                    {
                        "title": "Hong Kong market rebounds",
                        "link": "https://example.test/news/hk",
                        "snippet": "Hong Kong equities recovered in afternoon trading.",
                        "date": "Oct 12, 2026",
                    }
                ]
            }
        )

    settings = Settings(
        SEARCH_PROVIDER="serpapi",
        SEARCH_API_KEY="test-token",
        SEARCH_RESULT_LIMIT=4,
        SEARCH_TIMEOUT_SECONDS=7,
        _env_file=None,
    )
    provider = SerpApiSearchProvider(settings, opener=fake_opener)

    results = provider.search("HK market", limit=2)

    assert captured["timeout"] == 7
    assert "engine=google" in captured["url"]
    assert "q=HK+market" in captured["url"]
    assert results == [
        {
            "title": "Hong Kong market rebounds",
            "url": "https://example.test/news/hk",
            "snippet": "Hong Kong equities recovered in afternoon trading.",
            "source": "SerpAPI",
            "published_at": "Oct 12, 2026",
        }
    ]


def test_real_search_provider_rejects_missing_key() -> None:
    # 真实搜索源缺少 Key 时要明确失败，不能悄悄伪装成真实新闻。
    settings = Settings(SEARCH_PROVIDER="tavily", SEARCH_API_KEY="", _env_file=None)
    provider = TavilySearchProvider(settings)

    assert provider.is_configured() is False
    with pytest.raises(SearchProviderError, match="SEARCH_API_KEY"):
        provider.search("NVDA")

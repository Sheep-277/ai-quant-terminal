from collections.abc import Callable
import json
from typing import Any, Mapping, Protocol, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import SearchProviderMode, Settings


class SearchResult(TypedDict):
    """标准搜索结果，AI Research 只消费这个结构，不直接依赖供应商字段。"""

    title: str
    url: str
    snippet: str
    source: str
    published_at: str | None


class NewsSearchProvider(Protocol):
    """新闻/网页搜索 Provider 合同，用于隔离业务层和具体搜索供应商。"""

    def is_configured(self) -> bool:
        """返回当前 Provider 是否具备最小可用配置。"""

    def search(self, query: str, *, limit: int | None = None) -> list[SearchResult]:
        """按关键词返回标准搜索结果。"""


class SearchProviderError(RuntimeError):
    """搜索 Provider 请求失败、响应异常或配置不可用时抛出的统一异常。"""


class MockSearchProvider:
    """本地 Mock 搜索源，用于未配置真实搜索 Key 时保持 AI Research 可运行。"""

    def is_configured(self) -> bool:
        """Mock Provider 总是可用，但结果只代表本地演示数据。"""

        return True

    def search(self, query: str, *, limit: int | None = None) -> list[SearchResult]:
        """返回固定结构的演示结果，避免无 Key 环境下页面空白。"""

        size = max(1, limit or 3)
        return [
            {
                "title": f"Mock news signal for {query}",
                "url": "mock://search/local-news-signal",
                "snippet": "本地 Mock 新闻线索，仅用于演示 AI Research 证据链结构。",
                "source": "MockSearch",
                "published_at": None,
            }
            for _ in range(size)
        ]


class TavilySearchProvider:
    """Tavily 搜索 Adapter，适合读取公开网页和新闻线索。"""

    _ENDPOINT = "https://api.tavily.com/search"

    def __init__(
        self,
        settings: Settings,
        *,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        """保存配置并允许测试注入 opener，生产默认使用标准库 HTTP。"""

        self._api_key = settings.search_api_key
        self._result_limit = settings.search_result_limit
        self._timeout_seconds = settings.search_timeout_seconds
        self._opener = opener

    def is_configured(self) -> bool:
        """Tavily 至少需要 SEARCH_API_KEY。"""

        return bool((self._api_key or "").strip())

    def search(self, query: str, *, limit: int | None = None) -> list[SearchResult]:
        """调用 Tavily Search API，并归一化 results 数组。"""

        self._validate_query_and_key(query)
        payload = {
            "api_key": self._api_key,
            "query": query.strip(),
            "search_depth": "basic",
            "max_results": self._normalize_limit(limit),
        }
        request = Request(
            self._ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        data = self._request_json(request, provider_name="Tavily")
        results = data.get("results")
        if not isinstance(results, list):
            raise SearchProviderError("Tavily 响应缺少 results 数组。")

        return [self._normalize_result(item) for item in results if isinstance(item, Mapping)]

    def _normalize_result(self, item: Mapping[str, object]) -> SearchResult:
        """把 Tavily 单条结果转换成项目标准 SearchResult。"""

        return {
            "title": str(item.get("title") or "Untitled"),
            "url": str(item.get("url") or ""),
            "snippet": str(item.get("content") or item.get("snippet") or ""),
            "source": "Tavily",
            "published_at": str(item["published_date"]) if item.get("published_date") else None,
        }

    def _validate_query_and_key(self, query: str) -> None:
        """搜索词和 Key 缺失时直接失败，错误信息不包含密钥值。"""

        if not query.strip():
            raise SearchProviderError("搜索关键词不能为空。")
        if not self.is_configured():
            raise SearchProviderError("Tavily 搜索源缺少 SEARCH_API_KEY。")

    def _normalize_limit(self, limit: int | None) -> int:
        """限制单次搜索结果数量，防止页面证据区过载。"""

        return min(max(1, limit or self._result_limit), 10)

    def _request_json(self, request: Request, *, provider_name: str) -> Mapping[str, object]:
        """发送 HTTP 请求并把响应解析为 JSON 对象。"""

        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            raise SearchProviderError(f"{provider_name} 搜索请求失败，HTTP {exc.code}。") from exc
        except (OSError, URLError) as exc:
            raise SearchProviderError(f"{provider_name} 搜索请求失败：{exc}。") from exc

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise SearchProviderError(f"{provider_name} 返回了无效 JSON。") from exc

        if not isinstance(data, Mapping):
            raise SearchProviderError(f"{provider_name} JSON 顶层必须是对象。")
        return data


class SerpApiSearchProvider:
    """SerpAPI 搜索 Adapter，作为另一类常见公开搜索源入口。"""

    _ENDPOINT = "https://serpapi.com/search.json"

    def __init__(
        self,
        settings: Settings,
        *,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        """保存配置并允许测试注入 opener。"""

        self._api_key = settings.search_api_key
        self._result_limit = settings.search_result_limit
        self._timeout_seconds = settings.search_timeout_seconds
        self._opener = opener

    def is_configured(self) -> bool:
        """SerpAPI 至少需要 SEARCH_API_KEY。"""

        return bool((self._api_key or "").strip())

    def search(self, query: str, *, limit: int | None = None) -> list[SearchResult]:
        """调用 SerpAPI，并归一化 organic_results 数组。"""

        if not query.strip():
            raise SearchProviderError("搜索关键词不能为空。")
        if not self.is_configured():
            raise SearchProviderError("SerpAPI 搜索源缺少 SEARCH_API_KEY。")

        query_string = urlencode(
            {
                "engine": "google",
                "q": query.strip(),
                "api_key": self._api_key,
                "num": min(max(1, limit or self._result_limit), 10),
            }
        )
        request = Request(f"{self._ENDPOINT}?{query_string}", method="GET", headers={"Accept": "application/json"})
        data = self._request_json(request)
        results = data.get("organic_results")
        if not isinstance(results, list):
            raise SearchProviderError("SerpAPI 响应缺少 organic_results 数组。")

        return [self._normalize_result(item) for item in results if isinstance(item, Mapping)]

    def _normalize_result(self, item: Mapping[str, object]) -> SearchResult:
        """把 SerpAPI 单条结果转换成项目标准 SearchResult。"""

        return {
            "title": str(item.get("title") or "Untitled"),
            "url": str(item.get("link") or ""),
            "snippet": str(item.get("snippet") or ""),
            "source": "SerpAPI",
            "published_at": str(item["date"]) if item.get("date") else None,
        }

    def _request_json(self, request: Request) -> Mapping[str, object]:
        """发送 SerpAPI HTTP 请求并解析 JSON。"""

        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            raise SearchProviderError(f"SerpAPI 搜索请求失败，HTTP {exc.code}。") from exc
        except (OSError, URLError) as exc:
            raise SearchProviderError(f"SerpAPI 搜索请求失败：{exc}。") from exc

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise SearchProviderError("SerpAPI 返回了无效 JSON。") from exc

        if not isinstance(data, Mapping):
            raise SearchProviderError("SerpAPI JSON 顶层必须是对象。")
        return data


def build_news_search_provider(
    settings: Settings,
    *,
    opener: Callable[..., Any] = urlopen,
) -> NewsSearchProvider:
    """根据 SEARCH_PROVIDER 创建搜索 Provider。"""

    if settings.search_provider == SearchProviderMode.TAVILY:
        return TavilySearchProvider(settings, opener=opener)
    if settings.search_provider == SearchProviderMode.SERPAPI:
        return SerpApiSearchProvider(settings, opener=opener)
    return MockSearchProvider()

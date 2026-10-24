from app.core.config import Settings
from app.core.market import MarketCode
from app.services.mock_ai_research_service import get_mock_ai_research


def test_get_mock_ai_research_reports_missing_llm_configuration() -> None:
    """开启 LLM 研究但缺少百炼配置时，页面应看到明确的工具调用失败原因。"""

    settings = Settings(
        ENABLE_LLM_RESEARCH=True,
        BAILIAN_API_KEY="",
        BAILIAN_BASE_URL="",
        _env_file=None,
    )

    response = get_mock_ai_research(MarketCode.US, settings=settings)

    assert response.tool_calls[-1].tool_name == "bailian_chat_completion"
    assert response.tool_calls[-1].status.value == "failed"
    assert "缺少配置：BAILIAN_API_KEY, BAILIAN_BASE_URL" in response.tool_calls[-1].summary
    assert all(not point.startswith("LLM 摘要：") for point in response.result.key_points)


def test_get_mock_ai_research_appends_search_event_evidence() -> None:
    """配置真实搜索源时，AI Research 页面应看到事件证据和搜索工具调用。"""

    class FakeSearchProvider:
        """测试用搜索源，不访问网络，只返回一条可审计事件。"""

        def is_configured(self) -> bool:
            return True

        def search(self, query: str, *, limit: int | None = None):
            assert "为什么 NVDA 今天异动" in query
            assert limit == 2
            return [
                {
                    "title": "NVDA rises after AI demand report",
                    "url": "https://example.test/nvda",
                    "snippet": "AI demand expectations lifted semiconductor shares.",
                    "source": "Tavily",
                    "published_at": "2026-10-12",
                }
            ]

    settings = Settings(
        SEARCH_PROVIDER="tavily",
        SEARCH_API_KEY="test-token",
        SEARCH_RESULT_LIMIT=2,
        _env_file=None,
    )

    response = get_mock_ai_research(MarketCode.US, settings=settings, search_provider=FakeSearchProvider())

    assert response.tool_calls[-1].tool_name == "web_search"
    assert response.tool_calls[-1].status.value == "completed"
    assert response.evidence[-1].evidence_type.value == "event"
    assert response.evidence[-1].source == "Tavily"
    assert "https://example.test/nvda" in response.evidence[-1].value
    assert response.evidence[-1].evidence_id in response.result.evidence_ids


def test_get_mock_ai_research_keeps_quant_result_when_search_fails() -> None:
    """搜索源失败时，只展示失败工具调用，不影响已有 Quant 证据和结论。"""

    class FailingSearchProvider:
        """测试用失败搜索源，模拟外部新闻 API 超时或不可用。"""

        def is_configured(self) -> bool:
            return True

        def search(self, query: str, *, limit: int | None = None):
            from app.providers.search_provider import SearchProviderError

            raise SearchProviderError("network timeout")

    settings = Settings(
        SEARCH_PROVIDER="tavily",
        SEARCH_API_KEY="test-token",
        _env_file=None,
    )

    response = get_mock_ai_research(MarketCode.US, settings=settings, search_provider=FailingSearchProvider())

    assert response.status.value == "completed"
    assert response.tool_calls[-1].tool_name == "web_search"
    assert response.tool_calls[-1].status.value == "failed"
    assert "network timeout" in response.tool_calls[-1].summary
    assert all(item.evidence_type.value != "event" for item in response.evidence)

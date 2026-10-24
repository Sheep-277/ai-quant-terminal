from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agents.llm_client import LLMClientError
from app.providers.search_provider import SearchProviderError
from app.api.v1.ai_research import (
    build_ai_research_llm_check_response,
    build_ai_research_llm_status_response,
    build_ai_research_search_check_response,
    build_ai_research_search_status_response,
)
from app.core.config import Settings
from app.core.market import MarketCode
from app.main import app
from app.schemas.ai_research import (
    AIResearchRequest,
    AIResearchTaskCreateResponse,
    ResearchTaskStatus,
)
from app.schemas.market import DataStatus
from app.services.mock_ai_research_service import AI_RESEARCH_FIXTURES, create_mock_ai_research_task


client = TestClient(app)


class FakeLLMCheckClient:
    def check_connection(self) -> str:
        return "ok"


class FailingLLMCheckClient:
    def check_connection(self) -> str:
        raise LLMClientError("Bailian LLM HTTP 401: invalid api key")


class FakeSearchCheckProvider:
    def is_configured(self) -> bool:
        return True

    def search(self, query: str, *, limit: int | None = None):
        assert query == "AI Quant Terminal market news"
        assert limit == 1
        return [
            {
                "title": "AI Quant Terminal public search check",
                "url": "https://example.test/search-check",
                "snippet": "Search provider is reachable.",
                "source": "Tavily",
                "published_at": None,
            }
        ]


class FailingSearchCheckProvider:
    def is_configured(self) -> bool:
        return True

    def search(self, query: str, *, limit: int | None = None):
        raise SearchProviderError("search provider timeout")


def test_ai_research_task_defaults_to_us() -> None:
    # 不传 market 时应返回默认美股 AI Research Mock 任务。
    response = client.get("/api/v1/ai-research/task")

    assert response.status_code == 200
    payload = response.json()
    assert payload["market"] == "US"
    assert payload["status"] == "completed"
    assert payload["timezone"] == "America/New_York"
    assert payload["trace"]
    assert payload["tool_calls"]
    assert payload["tool_calls"][0]["tool_name"] == "run_quant_pipeline"
    assert {item["source"] for item in payload["evidence"]} == {
        "ToolRegistry.run_quant_pipeline.factors",
        "ToolRegistry.run_quant_pipeline.signals",
        "ToolRegistry.run_quant_pipeline.strategy",
    }


def test_research_task_formal_route_defaults_to_us() -> None:
    # PRD 规划的正式 Research 路由应与旧 AI Research 展示路由返回同构合同。
    response = client.get("/api/v1/research/task")

    assert response.status_code == 200
    payload = response.json()
    assert payload["market"] == "US"
    assert payload["status"] == "completed"
    assert payload["timezone"] == "America/New_York"
    assert payload["trace"]
    assert payload["tool_calls"]


def test_ai_research_llm_status_reports_disabled_state() -> None:
    # 默认关闭 LLM 时，状态接口应提示当前只展示确定性 Quant 结论。
    response = build_ai_research_llm_status_response(Settings(ENABLE_LLM_RESEARCH=False, _env_file=None))

    assert response.enabled is False
    assert response.configured is False
    assert response.provider_name == "bailian"
    assert response.endpoint is None
    assert response.missing_configuration == ["BAILIAN_API_KEY", "BAILIAN_BASE_URL"]
    assert "Quant 结论" in response.next_action


def test_ai_research_llm_status_reports_missing_configuration() -> None:
    # 开启 LLM 但配置不完整时，应明确列出缺失环境变量。
    response = build_ai_research_llm_status_response(
        Settings(
            ENABLE_LLM_RESEARCH=True,
            BAILIAN_API_KEY="test-token",
            BAILIAN_BASE_URL="",
            _env_file=None,
        )
    )

    assert response.enabled is True
    assert response.configured is False
    assert response.endpoint is None
    assert response.missing_configuration == ["BAILIAN_BASE_URL"]
    assert response.next_action == "补全配置：BAILIAN_BASE_URL。"


def test_ai_research_llm_status_reports_normalized_endpoint() -> None:
    # 配置完整时，状态接口展示规范化后的 Chat Completions endpoint，但不发起真实调用。
    response = build_ai_research_llm_status_response(
        Settings(
            ENABLE_LLM_RESEARCH=True,
            BAILIAN_API_KEY="test-token",
            BAILIAN_BASE_URL="dashscope.aliyuncs.com/compatible-mode/v1",
            BAILIAN_MODEL="qwen-plus",
            _env_file=None,
        )
    )

    assert response.enabled is True
    assert response.configured is True
    assert response.model == "qwen-plus"
    assert response.endpoint == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert response.missing_configuration == []
    assert "会尝试调用百炼摘要" in response.next_action


def test_ai_research_llm_check_returns_configuration_error_without_request() -> None:
    # 配置不完整时不应发起真实 LLM 请求，而是返回可展示的失败结果。
    response = build_ai_research_llm_check_response(Settings(ENABLE_LLM_RESEARCH=True, _env_file=None))

    assert response.ok is False
    assert response.error == "补全配置：BAILIAN_API_KEY, BAILIAN_BASE_URL。"
    assert response.next_action == "先补全 LLM 配置，再执行连通性检查。"


def test_ai_research_llm_check_reports_success_with_fake_client() -> None:
    # 使用 fake client 验证 API 构造逻辑，不访问真实百炼网络。
    response = build_ai_research_llm_check_response(
        Settings(
            ENABLE_LLM_RESEARCH=True,
            BAILIAN_API_KEY="test-token",
            BAILIAN_BASE_URL="dashscope.aliyuncs.com/compatible-mode/v1",
            BAILIAN_MODEL="qwen-plus",
            _env_file=None,
        ),
        client=FakeLLMCheckClient(),
    )

    assert response.ok is True
    assert response.model == "qwen-plus"
    assert response.endpoint == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert response.response_preview == "ok"
    assert response.error is None


def test_ai_research_llm_check_reports_client_failure_with_fake_client() -> None:
    # 百炼返回认证或模型错误时，接口应返回 ok=false，而不是抛出 500。
    response = build_ai_research_llm_check_response(
        Settings(
            ENABLE_LLM_RESEARCH=True,
            BAILIAN_API_KEY="bad-token",
            BAILIAN_BASE_URL="dashscope.aliyuncs.com/compatible-mode/v1",
            _env_file=None,
        ),
        client=FailingLLMCheckClient(),
    )

    assert response.ok is False
    assert response.error == "Bailian LLM HTTP 401: invalid api key"
    assert "BAILIAN_API_KEY" in response.next_action


def test_ai_research_search_status_reports_mock_mode() -> None:
    # Mock 搜索源不需要 Key，状态接口只读配置，不发起真实搜索请求。
    response = build_ai_research_search_status_response(Settings(SEARCH_PROVIDER="mock", _env_file=None))

    assert response.provider_name == "mock"
    assert response.configured is True
    assert response.api_key_configured is False
    assert response.missing_configuration == []
    assert "本地事件线索" in response.next_action


def test_ai_research_search_status_reports_configured_real_provider() -> None:
    # 配置真实搜索源和 Key 后，前端应能看到搜索源已准备好，但接口不返回密钥值。
    response = build_ai_research_search_status_response(
        Settings(
            SEARCH_PROVIDER="tavily",
            SEARCH_API_KEY="test-search-token",
            SEARCH_RESULT_LIMIT=3,
            SEARCH_TIMEOUT_SECONDS=6,
            _env_file=None,
        )
    )

    assert response.provider_name == "tavily"
    assert response.configured is True
    assert response.api_key_configured is True
    assert response.result_limit == 3
    assert response.timeout_seconds == 6
    assert response.missing_configuration == []
    assert "test-search-token" not in response.model_dump_json()


def test_ai_research_search_status_reports_missing_api_key() -> None:
    # 真实搜索源缺少 Key 时，应明确提示缺失 SEARCH_API_KEY。
    response = build_ai_research_search_status_response(
        Settings(SEARCH_PROVIDER="serpapi", SEARCH_API_KEY="", _env_file=None)
    )

    assert response.provider_name == "serpapi"
    assert response.configured is False
    assert response.api_key_configured is False
    assert response.missing_configuration == ["SEARCH_API_KEY"]
    assert response.next_action == "补全配置：SEARCH_API_KEY。"


def test_ai_research_search_check_returns_configuration_error_without_request() -> None:
    # 配置不完整时不应发起真实搜索请求，而是返回可展示的失败结果。
    response = build_ai_research_search_check_response(
        Settings(SEARCH_PROVIDER="tavily", SEARCH_API_KEY="", _env_file=None),
        provider=FakeSearchCheckProvider(),
    )

    assert response.ok is False
    assert response.provider_name == "tavily"
    assert response.result_count == 0
    assert response.error == "补全配置：SEARCH_API_KEY。"
    assert response.next_action == "先补全公开搜索源配置，再执行连通性检查。"


def test_ai_research_search_check_reports_success_with_fake_provider() -> None:
    # 使用 fake provider 验证 API 构造逻辑，不访问真实搜索网络。
    response = build_ai_research_search_check_response(
        Settings(SEARCH_PROVIDER="tavily", SEARCH_API_KEY="test-token", _env_file=None),
        provider=FakeSearchCheckProvider(),
    )

    assert response.ok is True
    assert response.provider_name == "tavily"
    assert response.result_count == 1
    assert response.response_preview == "AI Quant Terminal public search check"
    assert response.error is None
    assert "test-token" not in response.model_dump_json()


def test_ai_research_search_check_reports_provider_failure_with_fake_provider() -> None:
    # 搜索源超时或认证失败时，接口应返回 ok=false，而不是抛出 500。
    response = build_ai_research_search_check_response(
        Settings(SEARCH_PROVIDER="serpapi", SEARCH_API_KEY="test-token", _env_file=None),
        provider=FailingSearchCheckProvider(),
    )

    assert response.ok is False
    assert response.provider_name == "serpapi"
    assert response.result_count == 0
    assert response.error == "search provider timeout"
    assert "SEARCH_API_KEY" in response.next_action


def test_ai_research_fixtures_cover_all_v1_markets() -> None:
    # Mock fixture 是 GET 展示任务和 POST 创建回执共同的数据来源。
    assert set(AI_RESEARCH_FIXTURES) == {MarketCode.US, MarketCode.HK, MarketCode.CN}

    for market, fixture in AI_RESEARCH_FIXTURES.items():
        assert fixture["query"]
        assert fixture["symbol"]
        assert fixture["data_status"] in {DataStatus.REALTIME, DataStatus.DELAYED}
        assert len(fixture["closes"]) >= 20
        assert isinstance(fixture["fundamentals"], dict)
        assert isinstance(fixture["entry_conditions"], list)
        assert isinstance(fixture["exit_conditions"], list)


def test_ai_research_task_supports_all_v1_markets() -> None:
    # AI Research 的任务、证据都必须显式绑定市场。
    expected_timezones = {
        "US": "America/New_York",
        "HK": "Asia/Hong_Kong",
        "CN": "Asia/Shanghai",
    }

    for market, timezone in expected_timezones.items():
        response = client.get("/api/v1/ai-research/task", params={"market": market})

        assert response.status_code == 200
        payload = response.json()
        assert payload["market"] == market
        assert payload["timezone"] == timezone
        assert payload["data_status"] in {"realtime", "delayed"}
        assert all(item["market"] == market for item in payload["evidence"])


def test_ai_research_task_binds_result_to_evidence() -> None:
    # 结构化结论必须引用证据 ID，避免变成无来源的自然语言判断。
    response = client.get("/api/v1/ai-research/task", params={"market": "HK"})

    assert response.status_code == 200
    payload = response.json()
    evidence_ids = {item["evidence_id"] for item in payload["evidence"]}
    result_evidence_ids = set(payload["result"]["evidence_ids"])
    assert result_evidence_ids
    assert result_evidence_ids.issubset(evidence_ids)


def test_ai_research_task_rejects_unknown_market() -> None:
    # 未支持市场必须返回参数校验错误，不能套用默认研究任务。
    response = client.get("/api/v1/ai-research/task", params={"market": "EU"})

    assert response.status_code == 422


def test_create_ai_research_task_returns_mock_acceptance() -> None:
    # 当前 POST 只返回任务接收回执，不启动真实 LangGraph、Celery 或 LLM。
    response = client.post(
        "/api/v1/ai-research/tasks",
        json={
            "market": "US",
            "query": "分析 NVDA 今天异动原因",
            "symbols": ["NVDA"],
            "include_strategy_idea": True,
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["task_id"] == "research-us-nvda-queued"
    assert payload["market"] == "US"
    assert payload["query"] == "分析 NVDA 今天异动原因"
    assert payload["status"] == "queued"
    assert payload["timezone"] == "America/New_York"
    assert payload["data_status"] == "realtime"
    assert payload["poll_url"] == "/api/v1/ai-research/tasks/research-us-nvda-queued"
    assert payload["accepted_at"]


def test_create_research_task_formal_route_returns_formal_poll_url() -> None:
    # 正式 Research 创建入口返回正式轮询地址，避免后续任务系统继续绑定旧路由命名。
    response = client.post(
        "/api/v1/research/tasks",
        json={
            "market": "US",
            "query": "分析 NVDA 今天异动原因",
            "symbols": ["NVDA"],
            "include_strategy_idea": True,
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["task_id"] == "research-us-nvda-queued"
    assert payload["market"] == "US"
    assert payload["status"] == "queued"
    assert payload["poll_url"] == "/api/v1/research/tasks/research-us-nvda-queued"


def test_create_ai_research_task_uses_market_fixture_data_status() -> None:
    # 创建回执的数据状态应与对应市场 GET Mock fixture 保持一致。
    expected_data_status = {
        "US": "realtime",
        "HK": "delayed",
        "CN": "delayed",
    }

    for market, data_status in expected_data_status.items():
        response = client.post(
            "/api/v1/ai-research/tasks",
            json={"market": market, "query": "分析当前市场", "symbols": []},
        )

        assert response.status_code == 202
        assert response.json()["data_status"] == data_status


def test_create_ai_research_task_rejects_invalid_payload() -> None:
    # 创建任务也必须遵守 market、query 和 symbols 数量限制。
    invalid_market_response = client.post(
        "/api/v1/ai-research/tasks",
        json={"market": "EU", "query": "分析未知市场", "symbols": ["TEST"]},
    )
    empty_query_response = client.post(
        "/api/v1/ai-research/tasks",
        json={"market": "US", "query": "", "symbols": ["NVDA"]},
    )
    too_many_symbols_response = client.post(
        "/api/v1/ai-research/tasks",
        json={
            "market": "US",
            "query": "批量研究",
            "symbols": [f"MOCK{i}" for i in range(21)],
        },
    )

    assert invalid_market_response.status_code == 422
    assert empty_query_response.status_code == 422
    assert too_many_symbols_response.status_code == 422


def test_ai_research_request_contract_validates_input() -> None:
    # 创建研究任务时必须显式携带 market，并限制一次请求中的标的数量。
    request = AIResearchRequest(
        market=MarketCode.US,
        query="分析 NVDA 今天异动原因",
        symbols=[" nvda ", "00700.hk"],
        include_strategy_idea=True,
    )

    assert request.market == MarketCode.US
    assert request.symbols == ["NVDA", "00700.HK"]
    assert request.include_strategy_idea is True

    with pytest.raises(ValidationError):
        AIResearchRequest(market=MarketCode.US, query="")

    with pytest.raises(ValidationError):
        AIResearchRequest(
            market=MarketCode.US,
            query="批量研究",
            symbols=[f"MOCK{i}" for i in range(21)],
        )

    with pytest.raises(ValidationError):
        AIResearchRequest(market=MarketCode.US, query="空 symbol", symbols=[" "])

    with pytest.raises(ValidationError):
        AIResearchRequest(market=MarketCode.US, query="非法 symbol", symbols=["NVDA/USD"])


def test_ai_research_task_create_response_contract() -> None:
    # 当前只定义异步任务创建响应合同，不代表已经启动真实队列或 LLM。
    accepted_at = datetime.now(timezone.utc)
    response = AIResearchTaskCreateResponse(
        task_id="research-us-nvda-queued",
        market=MarketCode.US,
        query="分析 NVDA 今天异动原因",
        status=ResearchTaskStatus.QUEUED,
        accepted_at=accepted_at,
        timezone="America/New_York",
        data_status=DataStatus.DELAYED,
        poll_url="/api/v1/ai-research/tasks/research-us-nvda-queued",
    )

    assert response.status == ResearchTaskStatus.QUEUED
    assert response.accepted_at == accepted_at
    assert response.poll_url == "/api/v1/ai-research/tasks/research-us-nvda-queued"

    with pytest.raises(ValidationError):
        AIResearchTaskCreateResponse(
            task_id="research-us-nvda-queued",
            market=MarketCode.US,
            query="分析 NVDA 今天异动原因",
            status=ResearchTaskStatus.QUEUED,
            accepted_at=accepted_at,
            timezone="America/New_York",
            data_status=DataStatus.DELAYED,
            poll_url="api/v1/ai-research/tasks/research-us-nvda-queued",
        )

    with pytest.raises(ValidationError):
        AIResearchTaskCreateResponse(
            task_id="research-us-nvda-queued",
            market=MarketCode.US,
            query="分析 NVDA 今天异动原因",
            status=ResearchTaskStatus.QUEUED,
            accepted_at=accepted_at,
            timezone="America/New_York",
            data_status=DataStatus.DELAYED,
            poll_url="https://example.com/api/v1/ai-research/tasks/research-us-nvda-queued",
        )


def test_create_mock_ai_research_task_uses_general_subject_without_symbols() -> None:
    # 没有传 symbol 时，Mock 任务仍应生成稳定 ID，不能让 route 层承担默认规则。
    request = AIResearchRequest(
        market=MarketCode.HK,
        query="分析港股科技股是否走强",
    )

    response = create_mock_ai_research_task(request)

    assert response.task_id == "research-hk-general-queued"
    assert response.market == MarketCode.HK
    assert response.status == ResearchTaskStatus.QUEUED
    assert response.timezone == "Asia/Hong_Kong"
    assert response.poll_url == "/api/v1/ai-research/tasks/research-hk-general-queued"


def test_create_mock_ai_research_task_normalizes_dotted_symbol_in_task_id() -> None:
    # 港股和 A 股常带市场后缀，Mock ID 应使用规范化后的 symbol，并把点号转成短横线。
    hk_request = AIResearchRequest(
        market=MarketCode.HK,
        query="分析腾讯当前量化状态",
        symbols=[" 00700.hk "],
    )
    cn_request = AIResearchRequest(
        market=MarketCode.CN,
        query="分析宁德时代当前量化状态",
        symbols=["300750.sz"],
    )

    hk_response = create_mock_ai_research_task(hk_request)
    cn_response = create_mock_ai_research_task(cn_request)

    assert hk_request.symbols == ["00700.HK"]
    assert cn_request.symbols == ["300750.SZ"]
    assert hk_response.task_id == "research-hk-00700-hk-queued"
    assert cn_response.task_id == "research-cn-300750-sz-queued"

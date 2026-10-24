import pytest

import app.agents.research_orchestrator as research_orchestrator
from app.agents.research_orchestrator import run_research_orchestrator
from app.core.market import MarketCode
from app.schemas.ai_research import ResearchHorizon, ResearchTaskStatus
from app.schemas.market import Direction


class FakeLLMClient:
    def summarize_research(self, **_kwargs) -> str:
        return "动量和综合评分偏强，但仍需结合数据延迟状态复核。"


class FailingLLMClient:
    def summarize_research(self, **_kwargs) -> str:
        raise RuntimeError("Bailian LLM HTTP 401: invalid api key")


def test_run_research_orchestrator_returns_structured_response() -> None:
    response = run_research_orchestrator(
        market=MarketCode.US,
        query="分析 NVDA 当前量化状态",
        symbol="NVDA",
        closes=[float(value) for value in range(100, 131)],
        fundamentals={
            "roe": 0.18,
            "roic": 0.12,
            "gross_margin": 0.42,
        },
        entry_conditions=[
            {
                "field": "momentum_20d",
                "operator": "gt",
                "value": 0.08,
            },
        ],
    )

    assert response.market == MarketCode.US
    assert response.status == ResearchTaskStatus.COMPLETED
    assert response.timezone == "America/New_York"
    assert response.result.direction == Direction.POSITIVE
    assert response.result.horizon == ResearchHorizon.SHORT_TERM
    assert response.result.evidence_ids == [
        "evidence-us-nvda-factor-001",
        "evidence-us-nvda-signal-001",
        "evidence-us-nvda-strategy-001",
    ]
    assert response.tool_calls[0].tool_name == "run_quant_pipeline"
    assert {item.source for item in response.evidence} == {
        "ToolRegistry.run_quant_pipeline.factors",
        "ToolRegistry.run_quant_pipeline.signals",
        "ToolRegistry.run_quant_pipeline.strategy",
    }
    assert set(response.result.evidence_ids) == {item.evidence_id for item in response.evidence}
    assert response.evidence[1].title == "量化信号 Quant Signals"
    assert response.evidence[1].value.startswith("signals=")
    assert response.evidence[2].value == "entry_matched=True; exit_matched=False"


def test_run_research_orchestrator_appends_llm_summary_without_replacing_evidence() -> None:
    response = run_research_orchestrator(
        market=MarketCode.US,
        query="分析 NVDA 当前量化状态",
        symbol="NVDA",
        closes=[float(value) for value in range(100, 131)],
        llm_client=FakeLLMClient(),
    )

    assert response.result.evidence_ids == [
        "evidence-us-nvda-factor-001",
        "evidence-us-nvda-signal-001",
        "evidence-us-nvda-strategy-001",
    ]
    assert response.tool_calls[-1].tool_name == "bailian_chat_completion"
    assert response.tool_calls[-1].status.value == "completed"
    assert response.result.key_points[-1] == "LLM 摘要：动量和综合评分偏强，但仍需结合数据延迟状态复核。"


def test_run_research_orchestrator_reports_llm_failure_reason_without_breaking_result() -> None:
    response = run_research_orchestrator(
        market=MarketCode.US,
        query="分析 NVDA 当前量化状态",
        symbol="NVDA",
        closes=[float(value) for value in range(100, 131)],
        llm_client=FailingLLMClient(),
    )

    assert response.status == ResearchTaskStatus.COMPLETED
    assert response.tool_calls[-1].tool_name == "bailian_chat_completion"
    assert response.tool_calls[-1].status.value == "failed"
    assert "原因=Bailian LLM HTTP 401: invalid api key" in response.tool_calls[-1].summary
    assert all(not point.startswith("LLM 摘要：") for point in response.result.key_points)


def test_run_research_orchestrator_generates_public_trace_only() -> None:
    response = run_research_orchestrator(
        market=MarketCode.CN,
        query="分析 600519.SH 当前量化状态",
        symbol="600519.SH",
        closes=[float(value) for value in range(100, 131)],
    )

    assert [step.step_id for step in response.trace] == [
        "trace-task-001",
        "trace-context-001",
        "trace-tool-001",
        "trace-evidence-001",
        "trace-result-001",
    ]
    assert all(step.status.value == "completed" for step in response.trace)
    assert all("私有思维链" not in step.summary for step in response.trace)


def test_run_research_orchestrator_marks_exit_condition_as_warning() -> None:
    response = run_research_orchestrator(
        market=MarketCode.HK,
        query="检查 00700.HK 是否触发风险退出",
        symbol="00700.HK",
        closes=[float(value) for value in range(100, 131)],
        exit_conditions=[
            {
                "field": "volatility_20d",
                "operator": "lt",
                "value": 0.5,
            },
        ],
    )

    assert response.result.direction == Direction.WARNING
    assert response.result.headline == "00700.HK 存在需要关注的量化风险"
    assert response.result.horizon == ResearchHorizon.RISK_REVIEW


def test_run_research_orchestrator_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="query must not be empty"):
        run_research_orchestrator(
            market=MarketCode.US,
            query="",
            symbol="NVDA",
            closes=[float(value) for value in range(100, 131)],
        )


def test_run_research_orchestrator_rejects_empty_symbol() -> None:
    with pytest.raises(ValueError, match="symbol must not be empty"):
        run_research_orchestrator(
            market=MarketCode.US,
            query="分析当前量化状态",
            symbol="",
            closes=[float(value) for value in range(100, 131)],
        )


def test_run_research_orchestrator_reports_invalid_quant_tool_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Tool Registry 输出结构异常时，应给出明确错误，而不是在后续步骤暴露 KeyError。
    monkeypatch.setattr(
        research_orchestrator,
        "call_tool",
        lambda _name, _arguments: {"factors": {}, "signals": []},
    )

    with pytest.raises(ValueError, match="quant tool output missing keys"):
        run_research_orchestrator(
            market=MarketCode.US,
            query="分析 NVDA 当前量化状态",
            symbol="NVDA",
            closes=[float(value) for value in range(100, 131)],
        )

    monkeypatch.setattr(
        research_orchestrator,
        "call_tool",
        lambda _name, _arguments: {"factors": [], "signals": [], "strategy": {}},
    )

    with pytest.raises(ValueError, match="factors must be a dict"):
        run_research_orchestrator(
            market=MarketCode.US,
            query="分析 NVDA 当前量化状态",
            symbol="NVDA",
            closes=[float(value) for value in range(100, 131)],
        )

    monkeypatch.setattr(
        research_orchestrator,
        "call_tool",
        lambda _name, _arguments: {
            "factors": {"momentum_20d": 0.2},
            "signals": [],
            "strategy": {"entry_matched": False, "exit_matched": False},
        },
    )

    with pytest.raises(ValueError, match="factors missing keys"):
        run_research_orchestrator(
            market=MarketCode.US,
            query="分析 NVDA 当前量化状态",
            symbol="NVDA",
            closes=[float(value) for value in range(100, 131)],
        )

    monkeypatch.setattr(
        research_orchestrator,
        "call_tool",
        lambda _name, _arguments: {
            "factors": {"momentum_20d": "high", "composite_score": 0.8},
            "signals": [],
            "strategy": {"entry_matched": False, "exit_matched": False},
        },
    )

    with pytest.raises(ValueError, match="factor momentum_20d must be numeric or None"):
        run_research_orchestrator(
            market=MarketCode.US,
            query="分析 NVDA 当前量化状态",
            symbol="NVDA",
            closes=[float(value) for value in range(100, 131)],
        )

    monkeypatch.setattr(
        research_orchestrator,
        "call_tool",
        lambda _name, _arguments: {
            "factors": {"momentum_20d": 0.2, "composite_score": 0.8},
            "signals": [{"title": "动量信号", "direction": "positive"}],
            "strategy": {},
        },
    )

    with pytest.raises(ValueError, match=r"signal\[0\] missing keys"):
        run_research_orchestrator(
            market=MarketCode.US,
            query="分析 NVDA 当前量化状态",
            symbol="NVDA",
            closes=[float(value) for value in range(100, 131)],
        )

    monkeypatch.setattr(
        research_orchestrator,
        "call_tool",
        lambda _name, _arguments: {
            "factors": {"momentum_20d": 0.2, "composite_score": 0.8},
            "signals": [],
            "strategy": {"entry_matched": True},
        },
    )

    with pytest.raises(ValueError, match="strategy missing keys"):
        run_research_orchestrator(
            market=MarketCode.US,
            query="分析 NVDA 当前量化状态",
            symbol="NVDA",
            closes=[float(value) for value in range(100, 131)],
        )

    monkeypatch.setattr(
        research_orchestrator,
        "call_tool",
        lambda _name, _arguments: {
            "factors": {"momentum_20d": 0.2, "composite_score": 0.8},
            "signals": [],
            "strategy": {"entry_matched": "yes", "exit_matched": False},
        },
    )

    with pytest.raises(ValueError, match="entry_matched must be a bool"):
        run_research_orchestrator(
            market=MarketCode.US,
            query="分析 NVDA 当前量化状态",
            symbol="NVDA",
            closes=[float(value) for value in range(100, 131)],
        )

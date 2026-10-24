"""AI Research 编排器。

当前 Orchestrator 不调用真实 LLM，只按固定流程调用 Tool Registry。
它负责生成公开 Research Trace、工具调用记录和结构化结论，不展示模型私有思维链。
"""

from datetime import datetime, timezone
from typing import Any, TypedDict

from app.agents.llm_client import LLMResearchClient
from app.core.market import MarketCode, get_market_context
from app.schemas.ai_research import (
    AIResearchResponse,
    EvidenceType,
    ResearchAgentType,
    ResearchHorizon,
    ResearchEvidence,
    ResearchTaskStatus,
    ResearchToolCall,
    ResearchTraceStep,
    StructuredResearchResult,
    ToolCallStatus,
)
from app.schemas.market import DataStatus, Direction
from app.tools.registry import call_tool


class QuantSignalOutput(TypedDict):
    """Quant Tool 序列化后的单条信号输出。"""

    code: str
    title: str
    direction: str
    severity: str
    score: float
    evidence: list[str]


class QuantStrategyOutput(TypedDict):
    """Quant Tool 序列化后的策略评估概要。"""

    entry_matched: bool
    exit_matched: bool
    entry_evaluations: list[dict[str, Any]]
    exit_evaluations: list[dict[str, Any]]


class QuantToolOutputView(TypedDict):
    """Orchestrator 使用的 Quant Tool 输出视图。"""

    factors: dict[str, float | None]
    signals: list[QuantSignalOutput]
    strategy: QuantStrategyOutput


def run_research_orchestrator(
    *,
    market: MarketCode,
    query: str,
    symbol: str,
    closes: list[float],
    fundamentals: dict[str, float | None] | None = None,
    entry_conditions: list[dict[str, Any]] | None = None,
    exit_conditions: list[dict[str, Any]] | None = None,
    data_status: DataStatus = DataStatus.REALTIME,
    llm_client: LLMResearchClient | None = None,
) -> AIResearchResponse:
    """运行最小 AI Research 编排流程。"""

    if not query:
        raise ValueError("query must not be empty")

    if not symbol:
        raise ValueError("symbol must not be empty")

    context = get_market_context(market)
    started_at = datetime.now(timezone.utc)
    tool_arguments = {
        "symbol": symbol,
        "closes": closes,
        "fundamentals": fundamentals or {},
        "entry_conditions": entry_conditions or [],
        "exit_conditions": exit_conditions or [],
    }
    tool_output = call_tool("run_quant_pipeline", tool_arguments)
    tool_output_view = _parse_quant_tool_output(tool_output)
    factors = tool_output_view["factors"]
    signals = tool_output_view["signals"]
    strategy = tool_output_view["strategy"]
    completed_at = datetime.now(timezone.utc)

    evidence = _build_evidence(
        market=market,
        symbol=symbol,
        factors=factors,
        signals=signals,
        strategy=strategy,
        data_status=data_status,
        timestamp=completed_at,
    )
    direction = _infer_direction(strategy=strategy, signals=signals)
    confidence = _infer_confidence(factors=factors, signals=signals)
    horizon = _infer_horizon(strategy=strategy, signals=signals)
    llm_summary, llm_tool_call = _run_llm_summary(
        llm_client=llm_client,
        market=market,
        query=query,
        symbol=symbol,
        factors=factors,
        signals=signals,
        strategy=strategy,
        started_at=started_at,
    )

    return AIResearchResponse(
        task_id=f"research-{market.value.lower()}-{symbol.lower()}-orchestrated",
        market=market,
        query=query,
        status=ResearchTaskStatus.COMPLETED,
        timestamp=completed_at,
        timezone=context.timezone,
        data_status=data_status,
        trace=_build_trace(started_at=started_at, completed_at=completed_at),
        tool_calls=[
            ResearchToolCall(
                tool_call_id="tool-call-quant-pipeline-001",
                agent=ResearchAgentType.MARKET_ANALYST,
                tool_name="run_quant_pipeline",
                status=ToolCallStatus.COMPLETED,
                started_at=started_at,
                completed_at=completed_at,
                summary="已调用确定性 Quant Pipeline，返回因子、信号和策略评估结果。",
            )
        ] + ([llm_tool_call] if llm_tool_call is not None else []),
        evidence=evidence,
        result=StructuredResearchResult(
            headline=_build_headline(symbol=symbol, direction=direction),
            direction=direction,
            confidence=confidence,
            horizon=horizon,
            key_points=_build_key_points(factors=factors, strategy=strategy, llm_summary=llm_summary),
            risk_flags=_build_risk_flags(signals),
            evidence_ids=[item.evidence_id for item in evidence],
        ),
    )


def _run_llm_summary(
    *,
    llm_client: LLMResearchClient | None,
    market: MarketCode,
    query: str,
    symbol: str,
    factors: dict[str, float | None],
    signals: list[QuantSignalOutput],
    strategy: QuantStrategyOutput,
    started_at: datetime,
) -> tuple[str | None, ResearchToolCall | None]:
    """可选调用 LLM 生成解释摘要；失败时只记录公开工具状态，不影响确定性结论。"""

    if llm_client is None:
        return None, None

    completed_at = datetime.now(timezone.utc)
    try:
        summary = llm_client.summarize_research(
            market=market,
            query=query,
            symbol=symbol,
            factors=factors,
            signals=signals,
            strategy=strategy,
        )
    except Exception as exc:
        return None, ResearchToolCall(
            tool_call_id="tool-call-llm-summary-001",
            agent=ResearchAgentType.ORCHESTRATOR,
            tool_name="bailian_chat_completion",
            status=ToolCallStatus.FAILED,
            started_at=started_at,
            completed_at=completed_at,
            summary=f"百炼 LLM 摘要生成失败，已保留确定性 Quant 结论。原因={_format_llm_error(exc)}。",
        )

    return summary, ResearchToolCall(
        tool_call_id="tool-call-llm-summary-001",
        agent=ResearchAgentType.ORCHESTRATOR,
        tool_name="bailian_chat_completion",
        status=ToolCallStatus.COMPLETED,
        started_at=started_at,
        completed_at=completed_at,
        summary="已调用百炼 LLM，根据结构化证据生成自然语言研究摘要。",
    )


def _parse_quant_tool_output(tool_output: dict[str, Any]) -> QuantToolOutputView:
    """提取 Orchestrator 需要的 Quant Tool 输出字段。"""

    missing_keys = {"factors", "signals", "strategy"} - set(tool_output)
    if missing_keys:
        raise ValueError(f"quant tool output missing keys: {sorted(missing_keys)}")

    if not isinstance(tool_output["factors"], dict):
        raise ValueError("quant tool output factors must be a dict")
    if not isinstance(tool_output["signals"], list):
        raise ValueError("quant tool output signals must be a list")
    if not isinstance(tool_output["strategy"], dict):
        raise ValueError("quant tool output strategy must be a dict")

    _validate_quant_factors(tool_output["factors"])
    _validate_quant_signals(tool_output["signals"])
    _validate_quant_strategy(tool_output["strategy"])

    return {
        "factors": tool_output["factors"],
        "signals": tool_output["signals"],
        "strategy": tool_output["strategy"],
    }


def _format_llm_error(exc: Exception, *, max_length: int = 300) -> str:
    """生成可展示的 LLM 失败原因，避免表格中出现过长错误堆栈。"""

    message = " ".join(str(exc).split()) or type(exc).__name__
    if len(message) <= max_length:
        return message
    return f"{message[:max_length]}..."


def _validate_quant_factors(factors: dict[str, Any]) -> None:
    """校验关键因子字段，保证关键点和证据摘要可以安全生成。"""

    required_keys = {"momentum_20d", "composite_score"}
    missing_keys = required_keys - set(factors)
    if missing_keys:
        raise ValueError(f"quant tool output factors missing keys: {sorted(missing_keys)}")

    for key in required_keys:
        value = factors[key]
        if value is not None and not isinstance(value, int | float):
            raise ValueError(f"quant tool output factor {key} must be numeric or None")


def _validate_quant_signals(signals: list[Any]) -> None:
    """校验信号输出的最小公开字段，避免后续证据生成时报错不清晰。"""

    required_keys = {"title", "direction", "score"}
    for index, signal in enumerate(signals):
        if not isinstance(signal, dict):
            raise ValueError(f"quant tool output signal[{index}] must be a dict")

        missing_keys = required_keys - set(signal)
        if missing_keys:
            raise ValueError(
                f"quant tool output signal[{index}] missing keys: {sorted(missing_keys)}"
            )

        if not isinstance(signal["title"], str) or not signal["title"]:
            raise ValueError(f"quant tool output signal[{index}] title must be a non-empty string")
        if not isinstance(signal["direction"], str) or not signal["direction"]:
            raise ValueError(f"quant tool output signal[{index}] direction must be a non-empty string")
        if not isinstance(signal["score"], int | float):
            raise ValueError(f"quant tool output signal[{index}] score must be numeric")


def _validate_quant_strategy(strategy: dict[str, Any]) -> None:
    """校验策略评估输出的最小公开字段，保证结论方向可以安全推断。"""

    required_keys = {"entry_matched", "exit_matched"}
    missing_keys = required_keys - set(strategy)
    if missing_keys:
        raise ValueError(f"quant tool output strategy missing keys: {sorted(missing_keys)}")

    if not isinstance(strategy["entry_matched"], bool):
        raise ValueError("quant tool output strategy entry_matched must be a bool")
    if not isinstance(strategy["exit_matched"], bool):
        raise ValueError("quant tool output strategy exit_matched must be a bool")


def _build_trace(
    *,
    started_at: datetime,
    completed_at: datetime,
) -> list[ResearchTraceStep]:
    """生成公开研究轨迹，不包含模型私有推理。

    当前 trace 按未来 LangGraph 节点粒度组织，但每一步仍是确定性 Mock 流程。
    """

    return [
        ResearchTraceStep(
            step_id="trace-task-001",
            agent=ResearchAgentType.ORCHESTRATOR,
            status=ToolCallStatus.COMPLETED,
            title="接收研究任务",
            summary="Orchestrator 已接收研究问题和标的，不启动真实异步任务。",
            started_at=started_at,
            completed_at=completed_at,
        ),
        ResearchTraceStep(
            step_id="trace-context-001",
            agent=ResearchAgentType.ORCHESTRATOR,
            status=ToolCallStatus.COMPLETED,
            title="确认市场上下文",
            summary="Orchestrator 已确认 market、timezone 和数据状态。",
            started_at=started_at,
            completed_at=completed_at,
        ),
        ResearchTraceStep(
            step_id="trace-tool-001",
            agent=ResearchAgentType.MARKET_ANALYST,
            status=ToolCallStatus.COMPLETED,
            title="调用 Quant Tool",
            summary="Market Analyst Agent 通过 Tool Registry 调用确定性量化工具。",
            started_at=started_at,
            completed_at=completed_at,
        ),
        ResearchTraceStep(
            step_id="trace-evidence-001",
            agent=ResearchAgentType.MARKET_ANALYST,
            status=ToolCallStatus.COMPLETED,
            title="生成结构化证据",
            summary="Market Analyst Agent 将工具输出拆分为因子、信号和策略评估证据。",
            started_at=started_at,
            completed_at=completed_at,
        ),
        ResearchTraceStep(
            step_id="trace-result-001",
            agent=ResearchAgentType.ORCHESTRATOR,
            status=ToolCallStatus.COMPLETED,
            title="绑定结构化结论",
            summary="Orchestrator 根据证据 ID 绑定标题、方向、置信度、关键点和风险提示。",
            started_at=started_at,
            completed_at=completed_at,
        ),
    ]


def _infer_direction(
    *,
    strategy: QuantStrategyOutput,
    signals: list[QuantSignalOutput],
) -> Direction:
    """根据工具输出推断结构化方向。"""

    if strategy["exit_matched"]:
        return Direction.WARNING

    if strategy["entry_matched"]:
        return Direction.POSITIVE

    if any(signal["direction"] == Direction.WARNING.value for signal in signals):
        return Direction.WARNING

    if any(signal["direction"] == Direction.NEGATIVE.value for signal in signals):
        return Direction.NEGATIVE

    if any(signal["direction"] == Direction.POSITIVE.value for signal in signals):
        return Direction.POSITIVE

    return Direction.NEUTRAL


def _infer_confidence(
    *,
    factors: dict[str, float | None],
    signals: list[QuantSignalOutput],
) -> float:
    """用综合评分或最高信号分数生成 0 到 1 的置信度。"""

    composite_score = factors.get("composite_score")
    if composite_score is not None:
        return min(max(float(composite_score), 0), 1)

    scores = [float(signal["score"]) for signal in signals]
    if scores:
        return min(max(max(scores), 0), 1)

    return 0.5


def _infer_horizon(
    *,
    strategy: QuantStrategyOutput,
    signals: list[QuantSignalOutput],
) -> ResearchHorizon:
    """根据策略和风险信号推断研究结论适用周期。"""

    if strategy["exit_matched"] or _has_risk_signal(signals):
        return ResearchHorizon.RISK_REVIEW
    if strategy["entry_matched"]:
        return ResearchHorizon.SHORT_TERM

    return ResearchHorizon.WATCHLIST


def _build_headline(*, symbol: str, direction: Direction) -> str:
    """生成结构化结论标题。"""

    if direction == Direction.POSITIVE:
        return f"{symbol} 的量化条件偏正面"
    if direction == Direction.NEGATIVE:
        return f"{symbol} 的量化条件偏负面"
    if direction == Direction.WARNING:
        return f"{symbol} 存在需要关注的量化风险"

    return f"{symbol} 当前量化条件中性"


def _build_key_points(
    *,
    factors: dict[str, float | None],
    strategy: QuantStrategyOutput,
    llm_summary: str | None = None,
) -> list[str]:
    """把工具输出压缩为前端可展示的关键点。"""

    points = [
        f"momentum_20d={_format_optional_float(factors['momentum_20d'])}",
        f"composite_score={_format_optional_float(factors['composite_score'])}",
        f"entry_matched={strategy['entry_matched']}",
        f"exit_matched={strategy['exit_matched']}",
    ]
    if llm_summary:
        points.append(f"LLM 摘要：{llm_summary}")
    return points


def _build_risk_flags(signals: list[QuantSignalOutput]) -> list[str]:
    """从信号中提取风险提示。"""

    return [
        signal["title"]
        for signal in signals
        if signal["direction"] in {Direction.WARNING.value, Direction.NEGATIVE.value}
    ]


def _build_evidence(
    *,
    market: MarketCode,
    symbol: str,
    factors: dict[str, float | None],
    signals: list[QuantSignalOutput],
    strategy: QuantStrategyOutput,
    data_status: DataStatus,
    timestamp: datetime,
) -> list[ResearchEvidence]:
    """把 Quant Tool 输出拆成可单独审计的证据项。"""

    evidence_prefix = f"evidence-{market.value.lower()}-{symbol.lower()}"

    return [
        ResearchEvidence(
            evidence_id=f"{evidence_prefix}-factor-001",
            evidence_type=EvidenceType.TOOL_OUTPUT,
            market=market,
            symbol=symbol,
            title="因子快照 Factor Snapshot",
            value=(
                f"momentum_20d={_format_optional_float(factors['momentum_20d'])}; "
                f"composite_score={_format_optional_float(factors['composite_score'])}"
            ),
            source="ToolRegistry.run_quant_pipeline.factors",
            data_status=data_status,
            timestamp=timestamp,
        ),
        ResearchEvidence(
            evidence_id=f"{evidence_prefix}-signal-001",
            evidence_type=EvidenceType.RISK if _has_risk_signal(signals) else EvidenceType.TOOL_OUTPUT,
            market=market,
            symbol=symbol,
            title="量化信号 Quant Signals",
            value=_summarize_signals(signals),
            source="ToolRegistry.run_quant_pipeline.signals",
            data_status=data_status,
            timestamp=timestamp,
        ),
        ResearchEvidence(
            evidence_id=f"{evidence_prefix}-strategy-001",
            evidence_type=EvidenceType.TOOL_OUTPUT,
            market=market,
            symbol=symbol,
            title="策略评估 Strategy Evaluation",
            value=(
                f"entry_matched={strategy['entry_matched']}; "
                f"exit_matched={strategy['exit_matched']}"
            ),
            source="ToolRegistry.run_quant_pipeline.strategy",
            data_status=data_status,
            timestamp=timestamp,
        ),
    ]


def _has_risk_signal(signals: list[QuantSignalOutput]) -> bool:
    """判断工具输出中是否包含风险或负面方向信号。"""

    return any(
        signal["direction"] in {Direction.WARNING.value, Direction.NEGATIVE.value}
        for signal in signals
    )


def _summarize_signals(signals: list[QuantSignalOutput]) -> str:
    """生成信号证据摘要，保留信号数量和最高评分。"""

    if not signals:
        return "signals=0; max_score=None"

    max_score = max(float(signal["score"]) for signal in signals)
    return f"signals={len(signals)}; max_score={max_score:.4f}"


def _format_optional_float(value: float | None) -> str:
    """格式化可缺失数值。"""

    if value is None:
        return "None"

    return f"{value:.4f}"

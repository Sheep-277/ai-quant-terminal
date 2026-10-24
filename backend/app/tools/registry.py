"""工具注册中心。

Tool Registry 统一登记 Agent 可调用的工具，避免 Agent 绕过受控入口直接访问业务代码。
当前只注册确定性 Quant Tool，后续 Market、Backtest、Risk Tool 会按同样方式加入。
"""

from dataclasses import dataclass
from typing import Any, Callable

from app.tools.quant_tools import run_quant_pipeline_tool


ToolCallable = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class ToolDefinition:
    """单个工具的公开定义。"""

    name: str
    description: str
    callable: ToolCallable


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "run_quant_pipeline": ToolDefinition(
        name="run_quant_pipeline",
        description="运行单标的确定性量化流水线，返回因子、信号和策略评估结果。",
        callable=run_quant_pipeline_tool,
    ),
}


def list_tools() -> list[ToolDefinition]:
    """列出当前已注册工具。"""

    return list(TOOL_REGISTRY.values())


def get_tool(name: str) -> ToolDefinition:
    """按名称获取工具定义。"""

    try:
        return TOOL_REGISTRY[name]
    except KeyError as error:
        raise ValueError(f"unknown tool: {name}") from error


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """按名称调用已注册工具。"""

    tool = get_tool(name)
    return tool.callable(**arguments)

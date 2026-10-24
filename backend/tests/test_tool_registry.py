import pytest

from app.tools.registry import call_tool, get_tool, list_tools


def test_list_tools_contains_quant_pipeline_tool() -> None:
    tools = list_tools()

    assert [tool.name for tool in tools] == ["run_quant_pipeline"]
    assert "确定性量化流水线" in tools[0].description


def test_get_tool_returns_tool_definition() -> None:
    tool = get_tool("run_quant_pipeline")

    assert tool.name == "run_quant_pipeline"
    assert callable(tool.callable)


def test_call_tool_runs_registered_quant_pipeline() -> None:
    result = call_tool(
        "run_quant_pipeline",
        {
            "symbol": "NVDA",
            "closes": [float(value) for value in range(100, 131)],
            "fundamentals": {
                "roe": 0.18,
                "roic": 0.12,
                "gross_margin": 0.42,
            },
            "entry_conditions": [
                {
                    "field": "momentum_20d",
                    "operator": "gt",
                    "value": 0.08,
                },
            ],
        },
    )

    assert result["symbol"] == "NVDA"
    assert result["factors"]["momentum_20d"] is not None
    assert result["strategy"]["entry_matched"] is True


def test_get_tool_rejects_unknown_tool() -> None:
    with pytest.raises(ValueError, match="unknown tool"):
        get_tool("unknown_tool")


def test_call_tool_rejects_unknown_tool() -> None:
    with pytest.raises(ValueError, match="unknown tool"):
        call_tool("unknown_tool", {})

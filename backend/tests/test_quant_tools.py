import pytest

from app.tools.quant_tools import run_quant_pipeline_tool


def test_run_quant_pipeline_tool_returns_json_friendly_result() -> None:
    result = run_quant_pipeline_tool(
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
            {
                "field": "composite_score",
                "operator": "gte",
                "value": 0.7,
            },
        ],
    )

    assert result["symbol"] == "NVDA"
    assert result["factors"]["momentum_20d"] is not None
    assert result["signals"]
    assert result["strategy"]["entry_matched"] is True
    assert result["strategy"]["entry_evaluations"][0]["matched"] is True


def test_run_quant_pipeline_tool_supports_exit_conditions() -> None:
    result = run_quant_pipeline_tool(
        symbol="AMD",
        closes=[float(value) for value in range(100, 131)],
        exit_conditions=[
            {
                "field": "volatility_20d",
                "operator": "lt",
                "value": 0.5,
            },
        ],
    )

    assert result["strategy"]["entry_matched"] is False
    assert result["strategy"]["exit_matched"] is True
    assert result["strategy"]["exit_evaluations"][0]["reason"] == "matched"


def test_run_quant_pipeline_tool_rejects_unknown_condition_field() -> None:
    with pytest.raises(ValueError):
        run_quant_pipeline_tool(
            symbol="NVDA",
            closes=[float(value) for value in range(100, 131)],
            entry_conditions=[
                {
                    "field": "unknown_factor",
                    "operator": "gt",
                    "value": 0,
                },
            ],
        )


def test_run_quant_pipeline_tool_rejects_unknown_condition_operator() -> None:
    with pytest.raises(ValueError):
        run_quant_pipeline_tool(
            symbol="NVDA",
            closes=[float(value) for value in range(100, 131)],
            entry_conditions=[
                {
                    "field": "momentum_20d",
                    "operator": "unknown_operator",
                    "value": 0,
                },
            ],
        )

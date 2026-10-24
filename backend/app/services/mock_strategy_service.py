from datetime import datetime, timezone

from app.core.market import MarketCode, get_market_context
from app.quant.factors import FactorSnapshot
from app.quant.strategy import (
    StrategyCondition as QuantStrategyCondition,
    StrategyConditionField as QuantStrategyConditionField,
    StrategyConditionOperator as QuantStrategyConditionOperator,
    StrategyEvaluation,
    evaluate_strategy,
)
from app.schemas.strategy import (
    PositionRule,
    RebalanceFrequency,
    RiskConstraint,
    StrategyCondition,
    StrategyConditionField,
    StrategyConditionOperator,
    StrategyCreatedBy,
    StrategyDraft,
    StrategyDraftCreateRequest,
    StrategyLabResponse,
    StrategyStatus,
    StrategyUniverse,
    UniverseType,
)


# Strategy Lab 当前先按市场提供一个默认股票池，后续可替换为 Provider 或数据库中的 Universe。
DEFAULT_STRATEGY_UNIVERSES: dict[MarketCode, StrategyUniverse] = {
    MarketCode.US: StrategyUniverse(
        market=MarketCode.US,
        universe_type=UniverseType.INDEX,
        name="NASDAQ 100",
        symbols=["NVDA", "AAPL", "AMD", "MSFT"],
    ),
    MarketCode.HK: StrategyUniverse(
        market=MarketCode.HK,
        universe_type=UniverseType.INDEX,
        name="Hang Seng TECH",
        symbols=["00700.HK", "09988.HK", "03690.HK", "01810.HK"],
    ),
    MarketCode.CN: StrategyUniverse(
        market=MarketCode.CN,
        universe_type=UniverseType.INDEX,
        name="CSI 300",
        symbols=["600519.SH", "300750.SZ", "000001.SZ", "600000.SH"],
    ),
}


STRATEGY_FIXTURES = {
    MarketCode.US: {
        "strategy_id": "mock-us-momentum-quality-v1",
        "name": "US Momentum Quality Draft",
        "description": "筛选 20 日动量较强、ROE 较高且成交量放大的美股科技标的。",
        "entry": [
            (StrategyConditionField.MOMENTUM_20D, StrategyConditionOperator.GREATER_THAN, 0.1, None, "20 日动量大于 10%"),
            (StrategyConditionField.ROE, StrategyConditionOperator.GREATER_THAN, 0.15, None, "ROE 大于 15%"),
            (StrategyConditionField.VOLUME_RATIO, StrategyConditionOperator.GREATER_THAN, 1.5, None, "成交量比率大于 1.5"),
        ],
        "exit": [
            (StrategyConditionField.RSI_14, StrategyConditionOperator.GREATER_THAN, 75, None, "RSI 过热时退出"),
        ],
        "factor_snapshot": FactorSnapshot(
            momentum_20d=0.13,
            trend_strength=0.08,
            volatility_20d=0.24,
            quality_score=0.72,
            composite_score=0.76,
        ),
        "engine_entry": [
            (QuantStrategyConditionField.MOMENTUM_20D, QuantStrategyConditionOperator.GREATER_THAN, 0.1, None),
            (QuantStrategyConditionField.QUALITY_SCORE, QuantStrategyConditionOperator.GREATER_THAN, 0.7, None),
        ],
        "engine_exit": [
            (QuantStrategyConditionField.VOLATILITY_20D, QuantStrategyConditionOperator.GREATER_THAN, 0.35, None),
        ],
        "rebalance": RebalanceFrequency.WEEKLY,
        "max_holdings": 10,
        "max_position_weight": 0.12,
        "max_drawdown": 0.18,
        "stop_loss": 0.08,
        "min_liquidity": 50_000_000,
    },
    MarketCode.HK: {
        "strategy_id": "mock-hk-cashflow-value-v1",
        "name": "HK Cash Flow Value Draft",
        "description": "筛选估值不过分高、现金流较稳健且流动性足够的港股互联网标的。",
        "entry": [
            (StrategyConditionField.PE_TTM, StrategyConditionOperator.LESS_THAN_OR_EQUAL, 30, None, "PE TTM 不高于 30"),
            (StrategyConditionField.ROE, StrategyConditionOperator.GREATER_THAN_OR_EQUAL, 0.12, None, "ROE 不低于 12%"),
            (StrategyConditionField.VOLUME_RATIO, StrategyConditionOperator.GREATER_THAN, 1.1, None, "成交量比率大于 1.1"),
        ],
        "exit": [
            (StrategyConditionField.MOMENTUM_20D, StrategyConditionOperator.LESS_THAN, -0.06, None, "20 日动量跌破 -6%"),
        ],
        "factor_snapshot": FactorSnapshot(
            momentum_20d=0.07,
            trend_strength=0.04,
            volatility_20d=0.21,
            quality_score=0.68,
            composite_score=0.66,
        ),
        "engine_entry": [
            (QuantStrategyConditionField.MOMENTUM_20D, QuantStrategyConditionOperator.GREATER_THAN_OR_EQUAL, 0.05, None),
            (QuantStrategyConditionField.QUALITY_SCORE, QuantStrategyConditionOperator.GREATER_THAN_OR_EQUAL, 0.65, None),
        ],
        "engine_exit": [
            (QuantStrategyConditionField.MOMENTUM_20D, QuantStrategyConditionOperator.LESS_THAN, -0.06, None),
        ],
        "rebalance": RebalanceFrequency.WEEKLY,
        "max_holdings": 8,
        "max_position_weight": 0.15,
        "max_drawdown": 0.2,
        "stop_loss": 0.1,
        "min_liquidity": 20_000_000,
    },
    MarketCode.CN: {
        "strategy_id": "mock-cn-quality-trend-v1",
        "name": "CN Quality Trend Draft",
        "description": "筛选盈利能力较强、趋势稳定且流动性满足要求的 A 股大盘标的。",
        "entry": [
            (StrategyConditionField.ROE, StrategyConditionOperator.GREATER_THAN, 0.18, None, "ROE 大于 18%"),
            (StrategyConditionField.MOMENTUM_20D, StrategyConditionOperator.BETWEEN, 0.02, 0.16, "20 日动量在 2% 到 16% 之间"),
            (StrategyConditionField.PE_TTM, StrategyConditionOperator.LESS_THAN, 35, None, "PE TTM 小于 35"),
        ],
        "exit": [
            (StrategyConditionField.RSI_14, StrategyConditionOperator.GREATER_THAN, 78, None, "RSI 明显过热时退出"),
        ],
        "factor_snapshot": FactorSnapshot(
            momentum_20d=0.11,
            trend_strength=0.06,
            volatility_20d=0.18,
            quality_score=0.75,
            composite_score=0.79,
        ),
        "engine_entry": [
            (QuantStrategyConditionField.MOMENTUM_20D, QuantStrategyConditionOperator.BETWEEN, 0.02, 0.16),
            (QuantStrategyConditionField.QUALITY_SCORE, QuantStrategyConditionOperator.GREATER_THAN, 0.7, None),
        ],
        "engine_exit": [
            (QuantStrategyConditionField.VOLATILITY_20D, QuantStrategyConditionOperator.GREATER_THAN, 0.3, None),
        ],
        "rebalance": RebalanceFrequency.MONTHLY,
        "max_holdings": 12,
        "max_position_weight": 0.1,
        "max_drawdown": 0.16,
        "stop_loss": 0.07,
        "min_liquidity": 30_000_000,
    },
}


def get_mock_strategy_lab(market: MarketCode) -> StrategyLabResponse:
    """生成 Strategy Lab Mock 响应，并执行可确定计算的策略规则评估。"""

    # 读取 MarketContext 是为了保持 service 对市场能力的入口一致，后续接规则时可直接复用。
    market_context = get_market_context(market)
    timestamp = datetime.now(timezone.utc)
    universe = DEFAULT_STRATEGY_UNIVERSES[market]
    fixture = STRATEGY_FIXTURES[market]
    strategy_evaluation = evaluate_strategy(
        fixture["factor_snapshot"],
        entry_conditions=_build_quant_conditions(fixture["engine_entry"]),
        exit_conditions=_build_quant_conditions(fixture["engine_exit"]),
    )

    return StrategyLabResponse(
        market=market,
        timestamp=timestamp,
        default_universe=universe,
        drafts=[
            StrategyDraft(
                strategy_id=fixture["strategy_id"],
                name=fixture["name"],
                version=1,
                description=fixture["description"],
                status=StrategyStatus.DRAFT,
                created_by=StrategyCreatedBy.AGENT,
                created_at=timestamp,
                updated_at=timestamp,
                universe=universe,
                entry_conditions=_build_conditions(fixture["entry"]),
                exit_conditions=_build_conditions(fixture["exit"]),
                position_rule=PositionRule(
                    max_holdings=fixture["max_holdings"],
                    max_position_weight=fixture["max_position_weight"],
                    equal_weight=True,
                ),
                rebalance_frequency=fixture["rebalance"],
                risk_constraints=[
                    RiskConstraint(
                        max_drawdown=fixture["max_drawdown"],
                        stop_loss=fixture["stop_loss"],
                        min_liquidity=fixture["min_liquidity"],
                    )
                ],
                parameters={
                    **_build_strategy_metadata(
                        market=market,
                        benchmark=universe.name,
                        market_timezone=market_context.timezone,
                        universe_source="mock_index_universe",
                    ),
                    "strategy_evaluation": _serialize_strategy_evaluation(strategy_evaluation),
                },
            )
        ],
    )


def create_mock_strategy_draft(request: StrategyDraftCreateRequest) -> StrategyDraft:
    """创建用户提交的策略草案 Mock 对象，当前不持久化也不进入回测。"""

    market_context = get_market_context(request.market)
    timestamp = datetime.now(timezone.utc)

    return StrategyDraft(
        strategy_id=_build_mock_strategy_id(market=request.market, name=request.name),
        name=request.name,
        version=1,
        description=request.description,
        status=StrategyStatus.DRAFT,
        created_by=request.created_by,
        created_at=timestamp,
        updated_at=timestamp,
        universe=request.universe,
        entry_conditions=request.entry_conditions,
        exit_conditions=request.exit_conditions,
        position_rule=request.position_rule,
        rebalance_frequency=request.rebalance_frequency,
        risk_constraints=request.risk_constraints,
        parameters={
            **_build_strategy_metadata(
                market=request.market,
                benchmark=market_context.benchmark,
                market_timezone=market_context.timezone,
                universe_source="user_request",
            ),
        },
    )


def _build_conditions(rows: list[tuple[StrategyConditionField, StrategyConditionOperator, float, float | None, str]]) -> list[StrategyCondition]:
    """把紧凑的 fixture 元组转换成正式 Pydantic 条件对象。"""

    return [
        StrategyCondition(
            field=field,
            operator=operator,
            value=value,
            upper_value=upper_value,
            description=description,
        )
        for field, operator, value, upper_value, description in rows
    ]


def _build_mock_strategy_id(*, market: MarketCode, name: str) -> str:
    """根据市场和名称生成稳定的 Mock strategy_id，便于前端调试和测试断言。"""

    normalized_name = "-".join(name.strip().lower().split())
    return f"mock-{market.value.lower()}-{normalized_name}-draft"


def _build_strategy_metadata(
    *,
    market: MarketCode,
    benchmark: str,
    market_timezone: str,
    universe_source: str,
) -> dict[str, object]:
    """生成策略草案元信息，标明当前数据来源和后续真实 Provider 切换边界。"""

    return {
        "benchmark": benchmark,
        "data_mode": "mock",
        "provider": "MockMarketDataProvider",
        "provider_ready": False,
        "universe_source": universe_source,
        "market": market.value,
        "market_timezone": market_timezone,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
    }


def _build_quant_conditions(
    rows: list[tuple[QuantStrategyConditionField, QuantStrategyConditionOperator, float, float | None]],
) -> list[QuantStrategyCondition]:
    """把 Mock 可执行规则转换成 Strategy Engine 条件。"""

    return [
        QuantStrategyCondition(
            field=field,
            operator=operator,
            value=value,
            upper_value=upper_value,
        )
        for field, operator, value, upper_value in rows
    ]


def _serialize_strategy_evaluation(evaluation: StrategyEvaluation) -> dict[str, object]:
    """把 Strategy Engine 评估结果转换为可 JSON 序列化的参数。"""

    return {
        "entry_matched": evaluation.entry_matched,
        "exit_matched": evaluation.exit_matched,
        "entry_evaluations": [
            {
                "field": item.condition.field.value,
                "operator": item.condition.operator.value,
                "expected_value": item.condition.value,
                "upper_value": item.condition.upper_value,
                "actual_value": item.actual_value,
                "matched": item.matched,
                "reason": item.reason,
            }
            for item in evaluation.entry_evaluations
        ],
        "exit_evaluations": [
            {
                "field": item.condition.field.value,
                "operator": item.condition.operator.value,
                "expected_value": item.condition.value,
                "upper_value": item.condition.upper_value,
                "actual_value": item.actual_value,
                "matched": item.matched,
                "reason": item.reason,
            }
            for item in evaluation.exit_evaluations
        ],
    }

import pytest
from pydantic import ValidationError

from app.schemas.risk import (
    PreTradeRiskCheckRequest,
    PreTradeRiskCheckResponse,
    RiskCheckDecision,
    RiskCheckReason,
    RiskCheckSeverity,
    RiskPositionInput,
)


def test_pre_trade_risk_check_request_normalizes_symbol() -> None:
    # 风险检查合同复用显式 market，不允许只靠 symbol 猜市场。
    request = PreTradeRiskCheckRequest(
        account_id="paper-us-001",
        market="US",
        symbol=" nvda ",
        side="buy",
        quantity=1,
        limit_price=180.5,
        nav=100_000,
        cash=20_000,
    )

    assert request.symbol == "NVDA"
    assert request.paper_trading is True


def test_pre_trade_risk_check_request_rejects_live_trading_flag() -> None:
    # V1 只允许模拟订单进入下单前风险检查。
    with pytest.raises(ValidationError, match="paper_trading must be true"):
        PreTradeRiskCheckRequest(
            account_id="paper-us-001",
            market="US",
            symbol="NVDA",
            side="buy",
            quantity=1,
            nav=100_000,
            cash=20_000,
            paper_trading=False,
        )


def test_pre_trade_risk_check_request_rejects_cross_market_positions() -> None:
    # 同一次风险检查不能混用不同市场持仓，避免币种和交易规则口径错配。
    with pytest.raises(ValidationError, match="current_positions market must match"):
        PreTradeRiskCheckRequest(
            account_id="paper-us-001",
            market="US",
            symbol="NVDA",
            side="buy",
            quantity=1,
            nav=100_000,
            cash=20_000,
            current_positions=[
                RiskPositionInput(market="HK", symbol="0700", market_value=10_000),
            ],
        )


def test_pre_trade_risk_check_response_keeps_decision_and_reasons() -> None:
    # 响应合同只表达风险结论，不代表订单已经创建或成交。
    response = PreTradeRiskCheckResponse(
        account_id="paper-us-001",
        market="US",
        symbol="NVDA",
        side="buy",
        decision=RiskCheckDecision.WARNING,
        risk_checked=True,
        checked_at="2026-09-07T00:00:00Z",
        projected_order_value=180.5,
        projected_cash=19_819.5,
        projected_cash_weight=0.198195,
        projected_position_weight=0.301,
        reasons=[
            RiskCheckReason(
                code="position_weight_near_limit",
                message="订单成交后单一持仓接近权重上限",
                severity=RiskCheckSeverity.WARNING,
            ),
        ],
    )

    assert response.decision == RiskCheckDecision.WARNING
    assert response.reasons[0].severity == RiskCheckSeverity.WARNING

from app.schemas.risk import (
    PreTradeRiskCheckRequest,
    RiskCheckDecision,
    RiskCheckSeverity,
    RiskPositionInput,
)
from app.services.risk_service import pre_trade_check


def test_pre_trade_check_approves_small_mock_order() -> None:
    # 小额模拟买入不会突破现金和持仓权重约束，应直接通过。
    request = PreTradeRiskCheckRequest(
        account_id="paper-us-001",
        market="US",
        symbol="NVDA",
        side="buy",
        quantity=1,
        limit_price=100,
        nav=100_000,
        cash=30_000,
        current_positions=[
            RiskPositionInput(market="US", symbol="MSFT", market_value=20_000),
        ],
    )

    response = pre_trade_check(request)

    assert response.decision == RiskCheckDecision.APPROVED
    assert response.risk_checked is True
    assert response.projected_order_value == 100
    assert response.projected_cash == 29_900
    assert response.reasons == []


def test_pre_trade_check_warns_when_position_weight_exceeds_limit() -> None:
    # 下单后单一持仓权重超过上限时，应给出警告但不直接代表真实拒单。
    request = PreTradeRiskCheckRequest(
        account_id="paper-us-001",
        market="US",
        symbol="NVDA",
        side="buy",
        quantity=10,
        limit_price=1_000,
        nav=100_000,
        cash=50_000,
        current_positions=[
            RiskPositionInput(market="US", symbol="NVDA", market_value=25_000),
        ],
        max_position_weight=0.3,
    )

    response = pre_trade_check(request)

    assert response.decision == RiskCheckDecision.WARNING
    assert response.projected_position_weight == 0.35
    assert any(reason.code == "position_weight_exceeded" for reason in response.reasons)


def test_pre_trade_check_rejects_insufficient_cash() -> None:
    # 买入金额超过现金时属于严重风险，应返回 rejected。
    request = PreTradeRiskCheckRequest(
        account_id="paper-us-001",
        market="US",
        symbol="NVDA",
        side="buy",
        quantity=100,
        limit_price=1_000,
        nav=100_000,
        cash=20_000,
    )

    response = pre_trade_check(request)

    assert response.decision == RiskCheckDecision.REJECTED
    assert response.projected_cash == -80_000
    assert any(
        reason.code == "insufficient_cash" and reason.severity == RiskCheckSeverity.CRITICAL
        for reason in response.reasons
    )


def test_pre_trade_check_warns_when_limit_price_is_missing() -> None:
    # 没有限价时无法估算订单名义金额，先返回 warning，后续接实时行情后可替换估价逻辑。
    request = PreTradeRiskCheckRequest(
        account_id="paper-us-001",
        market="US",
        symbol="NVDA",
        side="buy",
        quantity=1,
        limit_price=None,
        nav=100_000,
        cash=30_000,
    )

    response = pre_trade_check(request)

    assert response.decision == RiskCheckDecision.WARNING
    assert response.projected_order_value == 0
    assert any(reason.code == "missing_limit_price" for reason in response.reasons)

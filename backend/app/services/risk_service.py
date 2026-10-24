from datetime import datetime, timezone

from app.quant.risk import PositionInput, calculate_portfolio_risk
from app.schemas.portfolio import PaperOrderSide
from app.schemas.risk import (
    PreTradeRiskCheckRequest,
    PreTradeRiskCheckResponse,
    RiskCheckDecision,
    RiskCheckReason,
    RiskCheckSeverity,
)


def pre_trade_check(request: PreTradeRiskCheckRequest) -> PreTradeRiskCheckResponse:
    """执行下单前模拟风险检查，不创建订单、不连接真实券商。"""

    order_value = _calculate_order_value(request)
    projected_cash = _calculate_projected_cash(request, order_value)
    projected_positions = _build_projected_positions(request, order_value)
    risk = calculate_portfolio_risk(
        positions=projected_positions,
        nav=request.nav,
        cash=max(projected_cash, 0),
        max_position_weight=request.max_position_weight,
    )
    projected_position_weight = _find_projected_position_weight(
        positions=projected_positions,
        symbol=request.symbol,
        nav=request.nav,
    )
    reasons = _build_reasons(
        request=request,
        order_value=order_value,
        projected_cash=projected_cash,
        projected_cash_weight=projected_cash / request.nav,
        projected_position_weight=projected_position_weight,
        engine_flags=risk.risk_flags,
    )

    return PreTradeRiskCheckResponse(
        account_id=request.account_id,
        market=request.market,
        symbol=request.symbol,
        side=request.side,
        decision=_decide(reasons),
        risk_checked=True,
        checked_at=datetime.now(timezone.utc),
        projected_order_value=round(order_value, 4),
        projected_cash=round(projected_cash, 4),
        projected_cash_weight=round(projected_cash / request.nav, 6),
        projected_position_weight=round(projected_position_weight, 6),
        reasons=reasons,
    )


def _calculate_order_value(request: PreTradeRiskCheckRequest) -> float:
    """根据限价和数量估算订单名义金额；没有限价时暂按 0 处理并给出提示。"""

    if request.limit_price is None:
        return 0
    return request.quantity * request.limit_price


def _calculate_projected_cash(
    request: PreTradeRiskCheckRequest,
    order_value: float,
) -> float:
    """估算订单提交后的现金余额，买入减少现金，卖出增加现金。"""

    if request.side == PaperOrderSide.BUY:
        return request.cash - order_value
    return request.cash + order_value


def _build_projected_positions(
    request: PreTradeRiskCheckRequest,
    order_value: float,
) -> list[PositionInput]:
    """把当前持仓和本次订单合并成风险计算输入。"""

    projected_market_values: dict[tuple[str, str], float] = {
        (position.symbol, position.side.value): position.market_value
        for position in request.current_positions
    }
    position_key = (request.symbol, "long")
    signed_order_value = order_value if request.side == PaperOrderSide.BUY else -order_value
    projected_market_values[position_key] = max(
        projected_market_values.get(position_key, 0) + signed_order_value,
        0,
    )

    return [
        PositionInput(symbol=symbol, market_value=market_value, side=side)
        for (symbol, side), market_value in projected_market_values.items()
        if market_value > 0
    ]


def _find_projected_position_weight(
    *,
    positions: list[PositionInput],
    symbol: str,
    nav: float,
) -> float:
    """读取目标标的在模拟订单后的持仓权重。"""

    return sum(position.market_value for position in positions if position.symbol == symbol) / nav


def _build_reasons(
    *,
    request: PreTradeRiskCheckRequest,
    order_value: float,
    projected_cash: float,
    projected_cash_weight: float,
    projected_position_weight: float,
    engine_flags: list[str],
) -> list[RiskCheckReason]:
    """把确定性风险码转换成 API 响应原因。"""

    reasons: list[RiskCheckReason] = []

    if request.limit_price is None:
        reasons.append(
            RiskCheckReason(
                code="missing_limit_price",
                message="订单缺少限价，当前无法完整估算下单后风险",
                severity=RiskCheckSeverity.WARNING,
            )
        )

    if request.side == PaperOrderSide.BUY and order_value > request.cash:
        reasons.append(
            RiskCheckReason(
                code="insufficient_cash",
                message="买入订单金额超过当前可用现金",
                severity=RiskCheckSeverity.CRITICAL,
            )
        )

    if projected_cash_weight < request.min_cash_weight:
        reasons.append(
            RiskCheckReason(
                code="cash_weight_below_limit",
                message="订单提交后现金权重低于风险下限",
                severity=RiskCheckSeverity.WARNING,
            )
        )

    if projected_position_weight > request.max_position_weight:
        reasons.append(
            RiskCheckReason(
                code="position_weight_exceeded",
                message="订单提交后单一持仓权重超过风险上限",
                severity=RiskCheckSeverity.WARNING,
            )
        )

    for flag in engine_flags:
        if flag == "gross_exposure_above_nav":
            reasons.append(
                RiskCheckReason(
                    code=flag,
                    message="订单提交后总敞口超过组合净值",
                    severity=RiskCheckSeverity.CRITICAL,
                )
            )

    return reasons


def _decide(reasons: list[RiskCheckReason]) -> RiskCheckDecision:
    """根据原因严重程度生成最终风险检查结论。"""

    if any(reason.severity == RiskCheckSeverity.CRITICAL for reason in reasons):
        return RiskCheckDecision.REJECTED
    if reasons:
        return RiskCheckDecision.WARNING
    return RiskCheckDecision.APPROVED

"""风险指标计算。

Risk Engine 负责把权益曲线和持仓转换为可审计的风险指标。
本模块只做确定性计算，不负责下单、调仓或生成投资建议。
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PositionInput:
    """计算持仓风险所需的最小输入。"""

    symbol: str
    market_value: float
    side: str = "long"


@dataclass(frozen=True)
class PositionRisk:
    """单个持仓的风险摘要。"""

    symbol: str
    market_value: float
    weight: float
    side: str


@dataclass(frozen=True)
class PortfolioRiskSnapshot:
    """组合级风险快照。"""

    gross_exposure: float
    net_exposure: float
    largest_position_weight: float
    cash_weight: float
    risk_flags: list[str] = field(default_factory=list)


def calculate_drawdown(equity_curve: list[float]) -> list[float | None]:
    """根据权益曲线计算每个时间点的回撤比例。"""

    if not equity_curve:
        return []

    drawdowns: list[float | None] = []
    peak: float | None = None

    for equity in equity_curve:
        if equity < 0:
            raise ValueError("equity value must be greater than or equal to 0")

        peak = equity if peak is None else max(peak, equity)
        if peak == 0:
            drawdowns.append(None)
        else:
            drawdowns.append((peak - equity) / peak)

    return drawdowns


def calculate_max_drawdown(equity_curve: list[float]) -> float | None:
    """计算权益曲线的最大回撤。"""

    drawdowns = calculate_drawdown(equity_curve)
    valid_drawdowns = [drawdown for drawdown in drawdowns if drawdown is not None]
    if not valid_drawdowns:
        return None

    return max(valid_drawdowns)


def calculate_position_risk(
    positions: list[PositionInput],
    nav: float,
) -> list[PositionRisk]:
    """计算单个持仓权重。"""

    if nav <= 0:
        raise ValueError("nav must be greater than 0")

    return [
        PositionRisk(
            symbol=position.symbol,
            market_value=position.market_value,
            weight=position.market_value / nav,
            side=position.side,
        )
        for position in positions
    ]


def calculate_exposure(
    positions: list[PositionInput],
    nav: float,
) -> tuple[float, float]:
    """计算总敞口和净敞口。

    long 持仓计为正敞口，short 持仓计为负敞口。V1 当前不做真实做空，
    但这里保留 short 逻辑，方便未来风险计算复用。
    """

    if nav <= 0:
        raise ValueError("nav must be greater than 0")

    signed_values = [
        position.market_value if position.side == "long" else -position.market_value
        for position in positions
    ]
    gross_exposure = sum(abs(value) for value in signed_values) / nav
    net_exposure = sum(signed_values) / nav

    return gross_exposure, net_exposure


def calculate_portfolio_risk(
    positions: list[PositionInput],
    nav: float,
    cash: float,
    *,
    max_position_weight: float = 0.3,
) -> PortfolioRiskSnapshot:
    """计算组合级风险摘要。"""

    if cash < 0:
        raise ValueError("cash must be greater than or equal to 0")

    position_risks = calculate_position_risk(positions, nav)
    gross_exposure, net_exposure = calculate_exposure(positions, nav)
    largest_position_weight = max(
        (position.weight for position in position_risks),
        default=0,
    )
    cash_weight = cash / nav
    risk_flags: list[str] = []

    if largest_position_weight > max_position_weight:
        risk_flags.append("largest_position_weight_exceeded")

    if cash_weight < 0.05:
        risk_flags.append("low_cash_weight")

    if gross_exposure > 1:
        risk_flags.append("gross_exposure_above_nav")

    return PortfolioRiskSnapshot(
        gross_exposure=gross_exposure,
        net_exposure=net_exposure,
        largest_position_weight=largest_position_weight,
        cash_weight=cash_weight,
        risk_flags=risk_flags,
    )

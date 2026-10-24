from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.market import MarketCode, get_market_context
from app.db.repositories.portfolio_repository import PortfolioRepository
from app.models.portfolio import Order as OrderModel
from app.models.portfolio import Portfolio, Position as PositionModel
from app.schemas.portfolio import (
    PaperOrder,
    PaperOrderSide,
    PaperOrderStatus,
    PortfolioAccount,
    PortfolioDataMode,
    PortfolioPosition,
    PortfolioResponse,
    PortfolioRiskSummary,
)


@dataclass(frozen=True)
class PortfolioReadSnapshot:
    """模拟组合只读快照，标记当前数据来自数据库。"""

    response: PortfolioResponse
    source: str


def get_latest_portfolio_snapshot(session: Session, market: MarketCode) -> PortfolioReadSnapshot | None:
    """读取当前市场最近更新的模拟组合；没有数据时返回 None，让调用方回退 Mock。"""

    repository = PortfolioRepository(session)
    portfolios = repository.list_by_market(market.value, limit=1)
    if not portfolios:
        return None

    portfolio = portfolios[0]
    return PortfolioReadSnapshot(
        response=_portfolio_to_response(
            portfolio,
            positions=repository.list_positions(portfolio.account_id),
            orders=repository.list_orders(portfolio.account_id),
        ),
        source="database",
    )


def get_portfolio_snapshot_by_account_id(session: Session, account_id: str) -> PortfolioReadSnapshot | None:
    """按 account_id 读取模拟组合；不存在时返回 None。"""

    repository = PortfolioRepository(session)
    portfolio = repository.get_by_account_id(account_id)
    if portfolio is None:
        return None

    return PortfolioReadSnapshot(
        response=_portfolio_to_response(
            portfolio,
            positions=repository.list_positions(portfolio.account_id),
            orders=repository.list_orders(portfolio.account_id),
        ),
        source="database",
    )


def _portfolio_to_response(
    portfolio: Portfolio,
    *,
    positions: list[PositionModel],
    orders: list[OrderModel],
) -> PortfolioResponse:
    """把数据库组合记录转换为前端使用的 PortfolioResponse。"""

    context = get_market_context(MarketCode(portfolio.market))
    return PortfolioResponse(
        market=MarketCode(portfolio.market),
        timestamp=_to_utc(portfolio.updated_at),
        timezone=context.timezone,
        currency=portfolio.currency,
        data_mode=PortfolioDataMode(portfolio.data_mode),
        account=PortfolioAccount(
            account_id=portfolio.account_id,
            market=MarketCode(portfolio.market),
            currency=portfolio.currency,
            nav=float(portfolio.nav),
            cash=float(portfolio.cash),
            market_value=float(portfolio.market_value),
            daily_pnl=float(portfolio.daily_pnl),
            total_pnl=float(portfolio.total_pnl),
            total_return=float(portfolio.total_return),
            updated_at=_to_utc(portfolio.updated_at),
        ),
        positions=[_position_to_schema(position) for position in positions],
        orders=[_order_to_schema(order) for order in orders],
        risk=PortfolioRiskSummary(
            gross_exposure=float(portfolio.gross_exposure),
            net_exposure=float(portfolio.net_exposure),
            largest_position_weight=float(portfolio.largest_position_weight),
            cash_weight=float(portfolio.cash_weight),
            risk_flags=list(portfolio.risk_flags),
        ),
    )


def _position_to_schema(position: PositionModel) -> PortfolioPosition:
    """把数据库持仓转换为 API schema。"""

    return PortfolioPosition(
        market=MarketCode(position.market),
        symbol=position.symbol,
        name=position.name,
        quantity=position.quantity,
        average_cost=float(position.average_cost),
        last_price=float(position.last_price),
        market_value=float(position.market_value),
        weight=float(position.weight),
        unrealized_pnl=float(position.unrealized_pnl),
        unrealized_pnl_percent=float(position.unrealized_pnl_percent),
    )


def _order_to_schema(order: OrderModel) -> PaperOrder:
    """把数据库模拟订单转换为 API schema。"""

    return PaperOrder(
        order_id=order.order_id,
        market=MarketCode(order.market),
        symbol=order.symbol,
        side=PaperOrderSide(order.side),
        quantity=order.quantity,
        limit_price=None if order.limit_price is None else float(order.limit_price),
        status=PaperOrderStatus(order.status),
        submitted_at=_to_utc(order.submitted_at),
        filled_at=None if order.filled_at is None else _to_utc(order.filled_at),
        source=order.source,
    )


def _to_utc(value: datetime) -> datetime:
    """把数据库中的无时区时间补成 UTC，保持 API 响应时间语义明确。"""

    if value.tzinfo is not None:
        return value.astimezone(timezone.utc)
    return value.replace(tzinfo=timezone.utc)

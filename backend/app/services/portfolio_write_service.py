from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.repositories.portfolio_repository import PortfolioRepository
from app.models.portfolio import Order, Portfolio, Position, Trade
from app.quant.risk import PositionInput, calculate_portfolio_risk
from app.schemas.portfolio import (
    PaperOrder,
    PaperOrderCreateResponse,
    PaperOrderSide,
    PaperOrderStatus,
    PortfolioPosition,
    PortfolioResponse,
)


def save_portfolio_summary(session: Session, response: PortfolioResponse) -> Portfolio:
    """把模拟组合响应快照保存到数据库，包含账户、持仓、订单和成交。"""

    repository = PortfolioRepository(session)
    saved_portfolio = repository.save_portfolio(_response_to_portfolio(response))
    session.flush()
    repository.replace_positions(
        saved_portfolio,
        [_position_to_model(position, source="mock_summary") for position in response.positions],
    )
    repository.replace_orders(
        saved_portfolio,
        [_order_to_model(response.account.account_id, response.currency, order, source="mock_summary") for order in response.orders],
    )
    repository.replace_trades(
        saved_portfolio,
        _orders_to_trade_models(response.account.account_id, response.orders, response.positions, source="mock_summary"),
    )
    session.commit()
    session.refresh(saved_portfolio)
    return saved_portfolio


def save_paper_order_receipt(session: Session, receipt: PaperOrderCreateResponse) -> Order | None:
    """把模拟下单回执保存到账户订单表；账户不存在时不创建真实交易上下文。"""

    repository = PortfolioRepository(session)
    portfolio = repository.get_by_account_id(receipt.account_id)
    if portfolio is None:
        return None

    stored_orders = repository.list_orders(receipt.account_id)
    stored_positions = repository.list_positions(receipt.account_id)
    existing_order = next((order for order in stored_orders if order.order_id == receipt.order_id), None)
    if existing_order is not None:
        return existing_order

    should_settle = _can_settle_paper_order(
        portfolio=portfolio,
        positions=stored_positions,
        receipt=receipt,
        existing_order=existing_order,
    )
    existing_orders = [
        _stored_order_to_model(order, source=order.source)
        for order in stored_orders
        if order.order_id != receipt.order_id
    ]
    saved_orders = repository.replace_orders(
        portfolio,
        existing_orders + [_receipt_to_order_model(receipt, source="paper_order", filled=should_settle)],
    )
    if should_settle:
        _apply_paper_fill(
            repository=repository,
            portfolio=portfolio,
            positions=stored_positions,
            receipt=receipt,
        )
    session.commit()
    return next((order for order in saved_orders if order.order_id == receipt.order_id), None)


def _response_to_portfolio(response: PortfolioResponse) -> Portfolio:
    """把 API 组合摘要主信息转换成 portfolios 表记录。"""

    account = response.account
    risk = response.risk
    return Portfolio(
        account_id=account.account_id,
        market=response.market.value,
        currency=response.currency,
        data_mode=response.data_mode.value,
        nav=_decimal(account.nav),
        cash=_decimal(account.cash),
        market_value=_decimal(account.market_value),
        daily_pnl=_decimal(account.daily_pnl),
        total_pnl=_decimal(account.total_pnl),
        total_return=_decimal(account.total_return),
        gross_exposure=_decimal(risk.gross_exposure),
        net_exposure=_decimal(risk.net_exposure),
        largest_position_weight=_decimal(risk.largest_position_weight),
        cash_weight=_decimal(risk.cash_weight),
        risk_flags=risk.risk_flags,
        source="mock_summary",
        updated_at=_to_naive_datetime(account.updated_at),
    )


def _position_to_model(position: PortfolioPosition, *, source: str) -> Position:
    """把 API 持仓转换成 positions 表记录。"""

    return Position(
        portfolio_id=0,
        account_id="",
        market=position.market.value,
        symbol=position.symbol,
        name=position.name,
        quantity=position.quantity,
        average_cost=_decimal(position.average_cost),
        last_price=_decimal(position.last_price),
        market_value=_decimal(position.market_value),
        weight=_decimal(position.weight),
        unrealized_pnl=_decimal(position.unrealized_pnl),
        unrealized_pnl_percent=_decimal(position.unrealized_pnl_percent),
        source=source,
        updated_at=_to_naive_datetime(datetime.now(timezone.utc)),
    )


def _can_settle_paper_order(
    *,
    portfolio: Portfolio,
    positions: list[Position],
    receipt: PaperOrderCreateResponse,
    existing_order: Order | None,
) -> bool:
    """判断模拟订单是否可以在本地立即成交；重复订单和拒绝订单不结算。"""

    if existing_order is not None:
        return False
    if receipt.status != PaperOrderStatus.SUBMITTED or receipt.limit_price is None:
        return False

    fill_value = _decimal(receipt.limit_price) * Decimal(receipt.quantity)
    if receipt.side == PaperOrderSide.BUY:
        return portfolio.cash >= fill_value

    position = next((item for item in positions if item.symbol == receipt.symbol and item.market == receipt.market.value), None)
    return position is not None and position.quantity >= receipt.quantity


def _apply_paper_fill(
    *,
    repository: PortfolioRepository,
    portfolio: Portfolio,
    positions: list[Position],
    receipt: PaperOrderCreateResponse,
) -> None:
    """把本地模拟成交反映到账户现金、持仓、成交和风险摘要。"""

    updated_positions = [_stored_position_to_model(position, source=position.source) for position in positions]
    fill_price = _decimal(receipt.limit_price or 0)
    fill_value = fill_price * Decimal(receipt.quantity)
    if receipt.side == PaperOrderSide.BUY:
        portfolio.cash -= fill_value
        _apply_buy_fill(updated_positions, receipt, fill_price)
    else:
        portfolio.cash += fill_value
        _apply_sell_fill(updated_positions, receipt, fill_price)

    _refresh_position_weights(updated_positions, portfolio)
    repository.replace_positions(portfolio, updated_positions)

    existing_trades = [
        _stored_trade_to_model(trade, source=trade.source)
        for trade in repository.list_trades(receipt.account_id)
        if trade.trade_id != _paper_trade_id(receipt.order_id)
    ]
    repository.replace_trades(
        portfolio,
        existing_trades + [_receipt_to_trade_model(receipt, fill_price, source="paper_order")],
    )


def _apply_buy_fill(positions: list[Position], receipt: PaperOrderCreateResponse, fill_price: Decimal) -> None:
    """把买入成交合并到现有持仓；没有持仓时创建一个最小持仓记录。"""

    position = next((item for item in positions if item.symbol == receipt.symbol and item.market == receipt.market.value), None)
    if position is None:
        positions.append(
            Position(
                portfolio_id=0,
                account_id="",
                market=receipt.market.value,
                symbol=receipt.symbol,
                name=receipt.symbol,
                quantity=receipt.quantity,
                average_cost=fill_price,
                last_price=fill_price,
                market_value=fill_price * Decimal(receipt.quantity),
                weight=Decimal("0"),
                unrealized_pnl=Decimal("0"),
                unrealized_pnl_percent=Decimal("0"),
                source="paper_order",
                updated_at=_to_naive_datetime(receipt.submitted_at),
            )
        )
        return

    old_quantity = Decimal(position.quantity)
    new_quantity = position.quantity + receipt.quantity
    total_cost = position.average_cost * old_quantity + fill_price * Decimal(receipt.quantity)
    position.quantity = new_quantity
    position.average_cost = total_cost / Decimal(new_quantity)
    position.last_price = fill_price
    position.source = "paper_order"
    position.updated_at = _to_naive_datetime(receipt.submitted_at)


def _apply_sell_fill(positions: list[Position], receipt: PaperOrderCreateResponse, fill_price: Decimal) -> None:
    """把卖出成交反映到持仓数量；当前不允许产生空头持仓。"""

    position = next((item for item in positions if item.symbol == receipt.symbol and item.market == receipt.market.value), None)
    if position is None:
        return

    position.quantity -= receipt.quantity
    position.last_price = fill_price
    position.source = "paper_order"
    position.updated_at = _to_naive_datetime(receipt.submitted_at)
    if position.quantity <= 0:
        positions.remove(position)


def _refresh_position_weights(positions: list[Position], portfolio: Portfolio) -> None:
    """重新计算持仓市值、权重和组合风险字段。"""

    for position in positions:
        quantity = Decimal(position.quantity)
        position.market_value = position.last_price * quantity
        position.unrealized_pnl = (position.last_price - position.average_cost) * quantity
        position.unrealized_pnl_percent = (
            Decimal("0") if position.average_cost == 0 else (position.last_price - position.average_cost) / position.average_cost
        )

    portfolio.market_value = sum((position.market_value for position in positions), Decimal("0"))
    portfolio.nav = portfolio.cash + portfolio.market_value
    for position in positions:
        position.weight = Decimal("0") if portfolio.nav == 0 else position.market_value / portfolio.nav

    risk = calculate_portfolio_risk(
        positions=[PositionInput(symbol=position.symbol, market_value=float(position.market_value)) for position in positions],
        nav=float(portfolio.nav),
        cash=float(portfolio.cash),
    )
    portfolio.gross_exposure = _decimal(risk.gross_exposure)
    portfolio.net_exposure = _decimal(risk.net_exposure)
    portfolio.largest_position_weight = _decimal(risk.largest_position_weight)
    portfolio.cash_weight = _decimal(risk.cash_weight)


def _receipt_to_order_model(receipt: PaperOrderCreateResponse, *, source: str, filled: bool = False) -> Order:
    """把模拟订单创建回执转换成 orders 表记录。"""

    return Order(
        portfolio_id=0,
        order_id=receipt.order_id,
        account_id=receipt.account_id,
        market=receipt.market.value,
        symbol=receipt.symbol,
        side=receipt.side.value,
        quantity=receipt.quantity,
        limit_price=None if receipt.limit_price is None else _decimal(receipt.limit_price),
        status=PaperOrderStatus.FILLED.value if filled else receipt.status.value,
        currency=receipt.currency,
        risk_checked=receipt.risk_checked,
        risk_decision=receipt.risk_decision.value,
        risk_reason_codes=receipt.risk_reason_codes,
        risk_reasons=receipt.risk_reasons,
        submitted_at=_to_naive_datetime(receipt.submitted_at),
        filled_at=_to_naive_datetime(receipt.submitted_at) if filled else None,
        source=source,
    )


def _stored_position_to_model(position: Position, *, source: str) -> Position:
    """复制已有持仓为新的 ORM 对象，供替换持仓快照时重新写入。"""

    return Position(
        portfolio_id=0,
        account_id=position.account_id,
        market=position.market,
        symbol=position.symbol,
        name=position.name,
        quantity=position.quantity,
        average_cost=position.average_cost,
        last_price=position.last_price,
        market_value=position.market_value,
        weight=position.weight,
        unrealized_pnl=position.unrealized_pnl,
        unrealized_pnl_percent=position.unrealized_pnl_percent,
        source=source,
        updated_at=position.updated_at,
    )


def _stored_order_to_model(order: Order, *, source: str) -> Order:
    """复制已有订单为新的 ORM 对象，供替换订单快照时重新写入。"""

    return Order(
        portfolio_id=0,
        order_id=order.order_id,
        account_id=order.account_id,
        market=order.market,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        limit_price=order.limit_price,
        status=order.status,
        currency=order.currency,
        risk_checked=order.risk_checked,
        risk_decision=order.risk_decision,
        risk_reason_codes=list(order.risk_reason_codes),
        risk_reasons=list(order.risk_reasons),
        submitted_at=order.submitted_at,
        filled_at=order.filled_at,
        source=source,
    )


def _receipt_to_trade_model(receipt: PaperOrderCreateResponse, fill_price: Decimal, *, source: str) -> Trade:
    """把本地模拟成交转换成 trades 表记录。"""

    return Trade(
        portfolio_id=0,
        order_id=receipt.order_id,
        trade_id=_paper_trade_id(receipt.order_id),
        account_id=receipt.account_id,
        market=receipt.market.value,
        symbol=receipt.symbol,
        side=receipt.side.value,
        quantity=receipt.quantity,
        price=fill_price,
        fee=Decimal("0"),
        filled_at=_to_naive_datetime(receipt.submitted_at),
        source=source,
    )


def _stored_trade_to_model(trade: Trade, *, source: str) -> Trade:
    """复制已有成交为新的 ORM 对象，供替换成交快照时重新写入。"""

    return Trade(
        portfolio_id=0,
        order_id=trade.order_id,
        trade_id=trade.trade_id,
        account_id=trade.account_id,
        market=trade.market,
        symbol=trade.symbol,
        side=trade.side,
        quantity=trade.quantity,
        price=trade.price,
        fee=trade.fee,
        filled_at=trade.filled_at,
        source=source,
    )


def _paper_trade_id(order_id: str) -> str:
    """生成用户模拟订单的本地成交 ID。"""

    return f"{order_id}-paper-fill"


def _order_to_model(account_id: str, currency: str, order: PaperOrder, *, source: str) -> Order:
    """把 API 模拟订单转换成 orders 表记录。"""

    return Order(
        portfolio_id=0,
        order_id=order.order_id,
        account_id=account_id,
        market=order.market.value,
        symbol=order.symbol,
        side=order.side.value,
        quantity=order.quantity,
        limit_price=None if order.limit_price is None else _decimal(order.limit_price),
        status=order.status.value,
        currency=currency,
        risk_checked=True,
        risk_decision="approved",
        risk_reason_codes=[],
        risk_reasons=[],
        submitted_at=_to_naive_datetime(order.submitted_at),
        filled_at=None if order.filled_at is None else _to_naive_datetime(order.filled_at),
        source=source,
    )


def _orders_to_trade_models(
    account_id: str,
    orders: list[PaperOrder],
    positions: list[PortfolioPosition],
    *,
    source: str,
) -> list[Trade]:
    """把已成交模拟订单转换成 trades 表记录。"""

    last_price_by_symbol = {position.symbol: position.last_price for position in positions}
    trades: list[Trade] = []
    for order in orders:
        if order.filled_at is None:
            continue
        trade_price = order.limit_price if order.limit_price is not None else last_price_by_symbol.get(order.symbol, 0)
        trades.append(
            Trade(
                portfolio_id=0,
                order_id=order.order_id,
                trade_id=f"{order.order_id}-fill",
                account_id=account_id,
                market=order.market.value,
                symbol=order.symbol,
                side=order.side.value,
                quantity=order.quantity,
                price=_decimal(trade_price),
                fee=Decimal("0"),
                filled_at=_to_naive_datetime(order.filled_at),
                source=source,
            )
        )
    return trades


def _decimal(value: float) -> Decimal:
    """把响应中的浮点数转换为 Decimal，减少金融数值落库时的二进制浮点误差。"""

    return Decimal(str(value))


def _to_naive_datetime(value: datetime) -> datetime:
    """统一去除时区信息，匹配当前项目 DateTime 字段的存储方式。"""

    return value.replace(tzinfo=None)

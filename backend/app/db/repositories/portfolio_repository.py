from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.portfolio import Order, Portfolio, Position, Trade


class PortfolioRepository:
    """模拟组合 Repository，封装账户、持仓、订单和成交的基础读写。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_account_id(self, account_id: str) -> Portfolio | None:
        """根据业务 account_id 查询模拟组合账户。"""

        statement = select(Portfolio).where(Portfolio.account_id == account_id.strip())
        return self._session.execute(statement).scalar_one_or_none()

    def list_by_market(self, market: str, *, limit: int = 20) -> list[Portfolio]:
        """按市场查询最近更新的模拟组合账户。"""

        statement = (
            select(Portfolio)
            .where(Portfolio.market == market.upper())
            .order_by(Portfolio.updated_at.desc(), Portfolio.id.desc())
            .limit(limit)
        )
        return list(self._session.execute(statement).scalars().all())

    def save_portfolio(self, portfolio: Portfolio) -> Portfolio:
        """保存模拟组合账户；account_id 已存在时更新账户和风险摘要。"""

        existing_portfolio = self.get_by_account_id(portfolio.account_id)
        if existing_portfolio is None:
            self._session.add(portfolio)
            return portfolio

        existing_portfolio.market = portfolio.market.upper()
        existing_portfolio.currency = portfolio.currency
        existing_portfolio.data_mode = portfolio.data_mode
        existing_portfolio.nav = portfolio.nav
        existing_portfolio.cash = portfolio.cash
        existing_portfolio.market_value = portfolio.market_value
        existing_portfolio.daily_pnl = portfolio.daily_pnl
        existing_portfolio.total_pnl = portfolio.total_pnl
        existing_portfolio.total_return = portfolio.total_return
        existing_portfolio.gross_exposure = portfolio.gross_exposure
        existing_portfolio.net_exposure = portfolio.net_exposure
        existing_portfolio.largest_position_weight = portfolio.largest_position_weight
        existing_portfolio.cash_weight = portfolio.cash_weight
        existing_portfolio.risk_flags = portfolio.risk_flags
        existing_portfolio.source = portfolio.source
        existing_portfolio.updated_at = portfolio.updated_at
        return existing_portfolio

    def replace_positions(self, portfolio: Portfolio, positions: Sequence[Position]) -> list[Position]:
        """替换某个账户的持仓快照，事务提交由调用方控制。"""

        self._session.execute(delete(Position).where(Position.account_id == portfolio.account_id))
        position_list = list(positions)
        for position in position_list:
            position.portfolio_id = portfolio.id
            position.account_id = portfolio.account_id
        self._session.add_all(position_list)
        return position_list

    def replace_orders(self, portfolio: Portfolio, orders: Sequence[Order]) -> list[Order]:
        """替换某个账户的订单快照，事务提交由调用方控制。"""

        self._session.execute(delete(Order).where(Order.account_id == portfolio.account_id))
        order_list = list(orders)
        for order in order_list:
            order.portfolio_id = portfolio.id
            order.account_id = portfolio.account_id
        self._session.add_all(order_list)
        return order_list

    def replace_trades(self, portfolio: Portfolio, trades: Sequence[Trade]) -> list[Trade]:
        """替换某个账户的成交快照，事务提交由调用方控制。"""

        self._session.execute(delete(Trade).where(Trade.account_id == portfolio.account_id))
        trade_list = list(trades)
        for trade in trade_list:
            trade.portfolio_id = portfolio.id
            trade.account_id = portfolio.account_id
        self._session.add_all(trade_list)
        return trade_list

    def list_positions(self, account_id: str) -> list[Position]:
        """按持仓权重倒序查询账户持仓。"""

        statement = (
            select(Position)
            .where(Position.account_id == account_id.strip())
            .order_by(Position.weight.desc(), Position.id.asc())
        )
        return list(self._session.execute(statement).scalars().all())

    def list_orders(self, account_id: str) -> list[Order]:
        """按提交时间倒序查询账户模拟订单。"""

        statement = (
            select(Order)
            .where(Order.account_id == account_id.strip())
            .order_by(Order.submitted_at.desc(), Order.id.desc())
        )
        return list(self._session.execute(statement).scalars().all())

    def list_trades(self, account_id: str) -> list[Trade]:
        """按成交时间倒序查询账户模拟成交。"""

        statement = (
            select(Trade)
            .where(Trade.account_id == account_id.strip())
            .order_by(Trade.filled_at.desc(), Trade.id.desc())
        )
        return list(self._session.execute(statement).scalars().all())

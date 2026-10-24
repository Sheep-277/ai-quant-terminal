from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.stock import Stock


class StockRepository:
    """股票主数据 Repository，封装 stocks 表的基础读写。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_market_symbol(self, market: str, symbol: str) -> Stock | None:
        """按市场和股票代码查询单个标的。"""

        statement = select(Stock).where(
            Stock.market == market.upper(),
            Stock.symbol == symbol.strip().upper(),
        )
        return self._session.execute(statement).scalar_one_or_none()

    def list_by_market(self, market: str, *, active_only: bool = True) -> list[Stock]:
        """查询指定市场下的股票主数据。"""

        statement = select(Stock).where(Stock.market == market.upper()).order_by(Stock.symbol.asc())
        if active_only:
            statement = statement.where(Stock.is_active.is_(True))

        return list(self._session.execute(statement).scalars().all())

    def add(self, stock: Stock) -> Stock:
        """新增股票主数据并等待当前事务提交。"""

        self._session.add(stock)
        return stock

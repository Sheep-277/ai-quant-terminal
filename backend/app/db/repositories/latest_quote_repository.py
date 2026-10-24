from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.latest_quote import LatestQuote


class LatestQuoteRepository:
    """最新行情 Repository，封装 latest_quotes 表的基础读写。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_market_symbol(self, market: str, symbol: str) -> LatestQuote | None:
        """按市场和股票代码查询最新行情。"""

        statement = select(LatestQuote).where(
            LatestQuote.market == market.upper(),
            LatestQuote.symbol == symbol.strip().upper(),
        )
        return self._session.execute(statement).scalar_one_or_none()

    def list_by_market(self, market: str) -> list[LatestQuote]:
        """查询指定市场下的最新行情，并按股票代码排序。"""

        statement = (
            select(LatestQuote)
            .where(LatestQuote.market == market.upper())
            .order_by(LatestQuote.symbol.asc())
        )
        return list(self._session.execute(statement).scalars().all())

    def save_latest(self, quote: LatestQuote) -> LatestQuote:
        """保存最新行情；同市场同代码存在时更新原记录。"""

        existing_quote = self.get_by_market_symbol(quote.market, quote.symbol)
        if existing_quote is None:
            self._session.add(quote)
            return quote

        existing_quote.stock_id = quote.stock_id
        existing_quote.price = quote.price
        existing_quote.change_amount = quote.change_amount
        existing_quote.change_percent = quote.change_percent
        existing_quote.volume = quote.volume
        existing_quote.turnover = quote.turnover
        existing_quote.data_status = quote.data_status
        existing_quote.source = quote.source
        existing_quote.quote_timestamp = quote.quote_timestamp
        return existing_quote

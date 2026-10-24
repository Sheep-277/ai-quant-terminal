from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.financial import Financial


class FinancialRepository:
    """基本面财务 Repository，封装 financials 表的基础读写。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_latest_by_market_symbol(self, market: str, symbol: str) -> Financial | None:
        """查询指定标的最新一期基本面财务数据。"""

        statement = (
            select(Financial)
            .where(
                Financial.market == market.upper(),
                Financial.symbol == symbol.strip().upper(),
            )
            .order_by(Financial.period_end_date.desc(), Financial.id.desc())
            .limit(1)
        )
        return self._session.execute(statement).scalar_one_or_none()

    def list_by_market_symbol(self, market: str, symbol: str, *, limit: int = 8) -> list[Financial]:
        """按报告期倒序查询指定标的的基本面历史。"""

        statement = (
            select(Financial)
            .where(
                Financial.market == market.upper(),
                Financial.symbol == symbol.strip().upper(),
            )
            .order_by(Financial.period_end_date.desc(), Financial.id.desc())
            .limit(limit)
        )
        return list(self._session.execute(statement).scalars().all())

    def save_period(self, financial: Financial) -> Financial:
        """保存一期基本面数据；同市场、代码、报告期和结束日存在时更新原记录。"""

        statement = select(Financial).where(
            Financial.market == financial.market.upper(),
            Financial.symbol == financial.symbol.strip().upper(),
            Financial.fiscal_period == financial.fiscal_period,
            Financial.period_end_date == financial.period_end_date,
        )
        existing_financial = self._session.execute(statement).scalar_one_or_none()
        if existing_financial is None:
            self._session.add(financial)
            return financial

        existing_financial.stock_id = financial.stock_id
        existing_financial.revenue = financial.revenue
        existing_financial.net_income = financial.net_income
        existing_financial.gross_margin = financial.gross_margin
        existing_financial.operating_margin = financial.operating_margin
        existing_financial.roe = financial.roe
        existing_financial.roic = financial.roic
        existing_financial.operating_cash_flow = financial.operating_cash_flow
        existing_financial.capex = financial.capex
        existing_financial.fcf = financial.fcf
        existing_financial.source = financial.source
        return existing_financial

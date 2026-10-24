from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.factor_value import FactorValue


class FactorValueRepository:
    """因子值 Repository，封装 factor_values 表的基础读写。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_latest_by_market_symbol(self, market: str, symbol: str) -> list[FactorValue]:
        """查询指定标的最近一个日期的全部因子值。"""

        latest_date_statement = (
            select(FactorValue.as_of_date)
            .where(
                FactorValue.market == market.upper(),
                FactorValue.symbol == symbol.strip().upper(),
            )
            .order_by(FactorValue.as_of_date.desc())
            .limit(1)
        )
        latest_date = self._session.execute(latest_date_statement).scalar_one_or_none()
        if latest_date is None:
            return []

        statement = (
            select(FactorValue)
            .where(
                FactorValue.market == market.upper(),
                FactorValue.symbol == symbol.strip().upper(),
                FactorValue.as_of_date == latest_date,
            )
            .order_by(FactorValue.factor_name.asc())
        )
        return list(self._session.execute(statement).scalars().all())

    def list_history(
        self,
        market: str,
        symbol: str,
        factor_name: str,
        *,
        limit: int = 30,
    ) -> list[FactorValue]:
        """按日期倒序查询某个因子的历史值。"""

        statement = (
            select(FactorValue)
            .where(
                FactorValue.market == market.upper(),
                FactorValue.symbol == symbol.strip().upper(),
                FactorValue.factor_name == factor_name,
            )
            .order_by(FactorValue.as_of_date.desc(), FactorValue.id.desc())
            .limit(limit)
        )
        return list(self._session.execute(statement).scalars().all())

    def save_values(self, values: Sequence[FactorValue]) -> list[FactorValue]:
        """批量保存因子值；同市场、代码、因子名和日期存在时更新原记录。"""

        saved_values: list[FactorValue] = []
        for value in values:
            saved_values.append(self._save_one(value))
        return saved_values

    def _save_one(self, value: FactorValue) -> FactorValue:
        """保存单个因子值，事务提交由调用方控制。"""

        statement = select(FactorValue).where(
            FactorValue.market == value.market.upper(),
            FactorValue.symbol == value.symbol.strip().upper(),
            FactorValue.factor_name == value.factor_name,
            FactorValue.as_of_date == value.as_of_date,
        )
        existing_value = self._session.execute(statement).scalar_one_or_none()
        if existing_value is None:
            self._session.add(value)
            return value

        existing_value.stock_id = value.stock_id
        existing_value.factor_value = value.factor_value
        existing_value.data_status = value.data_status
        existing_value.source = value.source
        return existing_value

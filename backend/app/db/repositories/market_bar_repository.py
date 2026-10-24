from datetime import datetime
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_bar import MarketBar


class MarketBarRepository:
    """K 线 Repository，封装 market_bars 表的时间序列读写。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_by_symbol(
        self,
        market: str,
        symbol: str,
        interval_code: str,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> list[MarketBar]:
        """按市场、代码、周期和可选时间范围查询 K 线。"""

        statement = select(MarketBar).where(
            MarketBar.market == market.upper(),
            MarketBar.symbol == symbol.strip().upper(),
            MarketBar.interval_code == interval_code,
        )
        if start_at is not None:
            statement = statement.where(MarketBar.bar_timestamp >= start_at)
        if end_at is not None:
            statement = statement.where(MarketBar.bar_timestamp <= end_at)

        statement = statement.order_by(MarketBar.bar_timestamp.asc())
        return list(self._session.execute(statement).scalars().all())

    def list_latest(
        self,
        market: str,
        symbol: str,
        interval_code: str,
        *,
        limit: int,
    ) -> list[MarketBar]:
        """查询最近 N 根 K 线，并按时间升序返回。"""

        statement = (
            select(MarketBar)
            .where(
                MarketBar.market == market.upper(),
                MarketBar.symbol == symbol.strip().upper(),
                MarketBar.interval_code == interval_code,
            )
            .order_by(MarketBar.bar_timestamp.desc())
            .limit(limit)
        )
        bars = list(self._session.execute(statement).scalars().all())
        return list(reversed(bars))

    def add_many(self, bars: Sequence[MarketBar]) -> list[MarketBar]:
        """批量新增 K 线，事务提交由调用方控制。"""

        bar_list = list(bars)
        self._session.add_all(bar_list)
        return bar_list

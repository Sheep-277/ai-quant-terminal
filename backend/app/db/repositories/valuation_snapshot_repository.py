from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.valuation_snapshot import ValuationSnapshot


class ValuationSnapshotRepository:
    """估值快照 Repository，封装 valuation_snapshots 表的基础读写。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_latest_by_market_symbol(self, market: str, symbol: str) -> ValuationSnapshot | None:
        """查询指定标的最近一次估值快照。"""

        statement = (
            select(ValuationSnapshot)
            .where(
                ValuationSnapshot.market == market.upper(),
                ValuationSnapshot.symbol == symbol.strip().upper(),
            )
            .order_by(ValuationSnapshot.snapshot_timestamp.desc(), ValuationSnapshot.id.desc())
            .limit(1)
        )
        return self._session.execute(statement).scalar_one_or_none()

    def list_by_market_symbol(self, market: str, symbol: str, *, limit: int = 8) -> list[ValuationSnapshot]:
        """按快照时间倒序查询指定标的的估值历史。"""

        statement = (
            select(ValuationSnapshot)
            .where(
                ValuationSnapshot.market == market.upper(),
                ValuationSnapshot.symbol == symbol.strip().upper(),
            )
            .order_by(ValuationSnapshot.snapshot_timestamp.desc(), ValuationSnapshot.id.desc())
            .limit(limit)
        )
        return list(self._session.execute(statement).scalars().all())

    def save_snapshot(self, snapshot: ValuationSnapshot) -> ValuationSnapshot:
        """保存估值快照；同市场、代码和快照时间存在时更新原记录。"""

        statement = select(ValuationSnapshot).where(
            ValuationSnapshot.market == snapshot.market.upper(),
            ValuationSnapshot.symbol == snapshot.symbol.strip().upper(),
            ValuationSnapshot.snapshot_timestamp == snapshot.snapshot_timestamp,
        )
        existing_snapshot = self._session.execute(statement).scalar_one_or_none()
        if existing_snapshot is None:
            self._session.add(snapshot)
            return snapshot

        existing_snapshot.stock_id = snapshot.stock_id
        existing_snapshot.pe_ttm = snapshot.pe_ttm
        existing_snapshot.pb = snapshot.pb
        existing_snapshot.ps_ttm = snapshot.ps_ttm
        existing_snapshot.pfcf_ttm = snapshot.pfcf_ttm
        existing_snapshot.source = snapshot.source
        return existing_snapshot

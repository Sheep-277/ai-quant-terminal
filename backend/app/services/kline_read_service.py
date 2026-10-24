from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.market import MarketCode
from app.db.repositories.market_bar_repository import MarketBarRepository
from app.schemas.market import DataStatus
from app.schemas.stock import KLineBar, KLineInterval, KLineSeries


@dataclass(frozen=True)
class KLineReadSnapshot:
    """数据库 K 线只读快照。"""

    kline: KLineSeries
    source: str
    detail: str = "K 线来自本地数据库 market_bars 表"


def get_kline_read_snapshot(
    session: Session,
    market: MarketCode,
    symbol: str,
    *,
    interval: KLineInterval = KLineInterval.ONE_DAY,
    limit: int = 30,
) -> KLineReadSnapshot | None:
    """读取最近 K 线；无记录沿用 Provider 路径，异常记录返回不可用快照。"""

    repository = MarketBarRepository(session)
    bars = repository.list_latest(market.value, symbol, interval.value, limit=limit)
    if not bars:
        return None

    try:
        kline = KLineSeries(
            interval=interval,
            data_status=DataStatus(bars[-1].data_status),
            bars=[
                KLineBar(
                    timestamp=bar.bar_timestamp,
                    open=float(bar.open_price),
                    high=float(bar.high_price),
                    low=float(bar.low_price),
                    close=float(bar.close_price),
                    volume=bar.volume,
                )
                for bar in bars
            ],
        )
    except (ValueError, TypeError, OverflowError):
        # 有记录但数据异常，不伪装成缺记录，也不丢弃坏行后展示残缺行情。
        return KLineReadSnapshot(
            kline=KLineSeries(interval=interval, data_status=DataStatus.UNAVAILABLE, bars=[]),
            source="database",
            detail="数据库 K 线数据校验失败，当前序列不可用；未自动修正或替换为样例行情",
        )

    return KLineReadSnapshot(kline=kline, source="database")

from typing import Annotated
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query

from app.core.config import Settings, get_settings
from app.core.market import MarketCode
from app.db.session import get_db_session
from app.schemas.market import DataStatus, MarketEvent, MarketEventOrigin, MarketOverviewResponse
from app.services.market_read_service import get_market_overview_read_snapshot
from app.services.mock_market_service import get_mock_market_overview


router = APIRouter(prefix="/market", tags=["market"])


@router.get("/overview", response_model=MarketOverviewResponse)
def get_market_overview(
    settings: Annotated[Settings, Depends(get_settings)],
    market: MarketCode = Query(default=MarketCode.US, description="当前市场代码：US / HK / CN"),
) -> MarketOverviewResponse:
    """返回当前市场总览；开启数据库读取时优先使用本地最新行情。"""

    return build_market_overview_response(market, settings)


def build_market_overview_response(market: MarketCode, settings: Settings) -> MarketOverviewResponse:
    """根据配置构造市场总览响应；本地行情缺失时回退 Mock。"""

    fallback_response = get_mock_market_overview(market)
    if not settings.enable_market_database_reads:
        return fallback_response

    session_generator = get_db_session(settings)
    session = next(session_generator)
    try:
        try:
            snapshot = get_market_overview_read_snapshot(session, market, fallback_response)
        except Exception as exc:
            return fallback_response.model_copy(
                update={
                    "data_status": DataStatus.UNAVAILABLE,
                    "events": [
                        MarketEvent(
                            timestamp=datetime.now(UTC),
                            source="PROVIDER",
                            origin=MarketEventOrigin.SYSTEM,
                            title=f"数据库市场总览读取失败，当前页面已回退到 Mock 市场总览；错误类型={type(exc).__name__}。",
                            impact="warning",
                            confidence=1.0,
                        ),
                        *fallback_response.events,
                    ],
                },
            )
        if snapshot is None:
            return fallback_response
        return snapshot
    finally:
        session_generator.close()

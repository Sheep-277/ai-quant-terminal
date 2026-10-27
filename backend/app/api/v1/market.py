from typing import Annotated
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings, get_settings
from app.core.exceptions import ProviderError, ProviderUnavailableError
from app.core.market import MarketCode
from app.db.session import get_db_session
from app.providers.factory import get_market_data_provider
from app.schemas.market import DataStatus, MarketEvent, MarketEventOrigin, MarketOverviewResponse
from app.schemas.market import MarketQuoteRefreshRequest, MarketQuoteRefreshResponse
from app.services.market_quote_refresh_service import refresh_market_quotes
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


@router.post("/quotes/refresh", response_model=MarketQuoteRefreshResponse)
def refresh_market_quote_snapshot(
    request: MarketQuoteRefreshRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> MarketQuoteRefreshResponse:
    """显式触发本地股票池刷新；默认预览，写入须开启市场数据库写开关。"""
    if not request.dry_run and not settings.enable_market_database_writes:
        raise HTTPException(status_code=403, detail={
            "code": "market_database_writes_disabled",
            "message": "Market database writes are disabled.",
        })
    session_generator = get_db_session(settings)
    try:
        session = next(session_generator)
        provider = get_market_data_provider(settings)
        with session.begin():
            report = refresh_market_quotes(session, request.market, provider, dry_run=request.dry_run)
            response = MarketQuoteRefreshResponse.model_validate(report)
        # 在上下文外返回，避免提交失败后仍发送 updated 回执。
        return response
    except ProviderUnavailableError:
        raise HTTPException(status_code=503, detail={
            "code": "market_quote_provider_unavailable",
            "message": "A ready real market data provider is required.",
        }) from None
    except (ProviderError, OSError):
        raise HTTPException(status_code=502, detail={
            "code": "market_quote_provider_failed",
            "message": "Market quote provider request failed.",
        }) from None
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail={
            "code": "market_quote_database_failed",
            "message": "Market quote refresh could not be committed.",
        }) from None
    finally:
        session_generator.close()


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

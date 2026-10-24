from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.exceptions import ProviderError
from app.core.market import MarketCode
from app.db.session import get_db_session
from app.providers.factory import get_market_data_provider
from app.schemas.market import Direction
from app.schemas.monitor import MonitorCalculatedSignalsResponse, MonitorEvent, MonitorResponse, MonitorSource
from app.schemas.stock import StockQuantSignal, StockResearchQuery
from app.services.monitor_read_service import get_monitor_signal_read_snapshot
from app.services.mock_monitor_service import get_mock_monitor_stream
from app.services.monitor_signal_service import calculate_monitor_signals


router = APIRouter(prefix="/monitor", tags=["monitor"])


def parse_monitor_signal_query(
    market: MarketCode = Query(description="当前市场代码：US / HK / CN"),
    symbol: str = Query(min_length=1, max_length=32, description="本次计算的单个股票代码"),
) -> StockResearchQuery:
    """复用现有股票代码校验，两个参数均由调用方明确提供。"""

    try:
        return StockResearchQuery(market=market, symbol=symbol)
    except ValidationError as error:
        errors = [{**item, "loc": ("query", *item["loc"])} for item in error.errors()]
        raise RequestValidationError(errors) from error


@router.get("/signals", response_model=MonitorCalculatedSignalsResponse)
def get_monitor_calculated_signals(
    query: Annotated[StockResearchQuery, Depends(parse_monitor_signal_query)],
) -> MonitorCalculatedSignalsResponse:
    """读取单标的公开日 K 线并计算信号；失败不进入原快照的 Mock 回退路径。"""

    # 默认标的仅适用于原快照接口，此计算入口必须明确指定。
    if query.symbol is None:
        raise HTTPException(status_code=422, detail="symbol is required")
    try:
        snapshot = calculate_monitor_signals(
            query.market,
            query.symbol,
            provider=get_market_data_provider(),
            observed_at=datetime.now(timezone.utc),
        )
    except (ProviderError, ValueError, OSError) as error:
        # 不向客户端透出供应商 URL、配置或原始异常，避免泄露密钥。
        raise HTTPException(status_code=503, detail={
            "code": "monitor_public_data_unavailable",
            "message": "公开日 K 线不可用、样本不足或校验失败；本次未生成替代信号，也未回退到 Mock。",
        }) from error

    return MonitorCalculatedSignalsResponse(
        market=snapshot.market,
        symbol=snapshot.symbol,
        timezone=snapshot.timezone,
        currency=snapshot.currency,
        source=snapshot.source,
        data_status=snapshot.data_status,
        timestamp=snapshot.timestamp,
        bar_count=snapshot.bar_count,
        signals=[StockQuantSignal(
            code=signal.code,
            title=signal.title,
            direction=signal.direction.value,
            severity=signal.severity.value,
            score=signal.score,
            evidence=signal.evidence,
        ) for signal in snapshot.result.signals],
    )


@router.get("/stream", response_model=MonitorResponse)
def get_monitor_stream(
    market: MarketCode = Query(default=MarketCode.US, description="当前市场代码：US / HK / CN"),
) -> MonitorResponse:
    """返回实时监控页面数据；开启数据库读取时优先使用本地信号。"""

    return build_monitor_stream_response(market=market, settings=get_settings())


def build_monitor_stream_response(market: MarketCode, settings: Settings) -> MonitorResponse:
    """根据配置构造实时监控响应；本地信号缺失时回退 Mock。"""

    fallback_response = get_mock_monitor_stream(market=market)
    if not settings.enable_monitor_database_reads:
        return fallback_response

    try:
        session_generator = get_db_session(settings)
        session = next(session_generator)
        try:
            snapshot = get_monitor_signal_read_snapshot(session, market, fallback_response)
            if snapshot is None:
                return fallback_response
            return snapshot
        finally:
            session_generator.close()
    except Exception as error:
        return _append_monitor_database_fallback_event(fallback_response, error)


def _append_monitor_database_fallback_event(
    fallback_response: MonitorResponse,
    error: Exception,
) -> MonitorResponse:
    """数据库读取异常时保留 Mock 监控流，并在事件流中暴露回退原因。"""

    fallback_event = MonitorEvent(
        event_id=f"event-{fallback_response.market.value.lower()}-db-read-fallback",
        market=fallback_response.market,
        source=MonitorSource.PROVIDER,
        title="监控数据库读取失败",
        summary=(
            "警告：读取数据库 signals 表失败，"
            f"当前实时监控页已回退到 Mock Monitor。错误类型={type(error).__name__}。"
        ),
        impact=Direction.WARNING,
        confidence=1.0,
        created_at=fallback_response.timestamp,
    )
    return fallback_response.model_copy(
        update={
            "provenance": fallback_response.provenance.model_copy(
                update={"event_source": "mixed"}
            ),
            "events": [*fallback_response.events, fallback_event],
        }
    )

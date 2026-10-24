from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import Settings, get_settings
from app.core.market import MarketCode
from app.db.session import get_db_session
from app.schemas.market import DataStatus
from app.schemas.backtest import BacktestRequest, BacktestResponse, BacktestTaskCreateResponse
from app.services.backtest_read_service import get_backtest_snapshot_by_id, get_latest_backtest_snapshot
from app.services.backtest_write_service import save_backtest_result
from app.services.backtest_result_service import create_backtest_task_receipt, get_backtest_result as build_service_backtest_result


router = APIRouter()
result_router = APIRouter(prefix="/backtest", tags=["backtest"])
backtests_router = APIRouter(prefix="/backtests", tags=["backtest"])


@result_router.get("/result", response_model=BacktestResponse)
def get_backtest_result(
    market: MarketCode = Query(default=MarketCode.US, description="当前市场代码：US / HK / CN"),
) -> BacktestResponse:
    """返回回测中心所需的结构化结果；开启数据库读取时优先使用本地回测结果。"""

    return build_backtest_result_response(market, get_settings())


def build_backtest_result_response(market: MarketCode, settings: Settings) -> BacktestResponse:
    """根据配置构造回测结果响应；缺少数据库结果时使用 Provider/Mock 服务结果。"""

    fallback_response = build_service_backtest_result(market=market, settings=settings)
    if not settings.enable_backtest_database_reads:
        return fallback_response

    try:
        session_generator = get_db_session(settings)
        session = next(session_generator)
        try:
            snapshot = get_latest_backtest_snapshot(session, market)
            if snapshot is None:
                return fallback_response
            return snapshot.response
        finally:
            session_generator.close()
    except Exception as error:
        return _append_backtest_database_fallback_assumption(fallback_response, error)


def _append_backtest_database_fallback_assumption(
    fallback_response: BacktestResponse,
    error: Exception,
) -> BacktestResponse:
    """数据库读取异常时保留 Mock 回测，并在 assumptions 中暴露回退原因。"""

    return fallback_response.model_copy(
        update={
            "assumptions": [
                *fallback_response.assumptions,
                (
                    "数据库回测结果读取失败，当前页面已回退到 Mock 回测结果；"
                    f"错误类型={type(error).__name__}。"
                ),
            ],
        }
    )


@backtests_router.post("", response_model=BacktestTaskCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_backtest_task(request: BacktestRequest) -> BacktestTaskCreateResponse:
    """创建回测任务回执；开启数据库写入时保存当前回测结果快照。"""

    return build_backtest_task_response(request, get_settings())


def build_backtest_task_response(request: BacktestRequest, settings: Settings) -> BacktestTaskCreateResponse:
    """根据配置创建回测任务回执；默认不写库。"""

    receipt = create_backtest_task_receipt(request=request)
    if not settings.enable_backtest_database_writes:
        return receipt

    result_snapshot = build_service_backtest_result(request.market, settings=settings).model_copy(
        update={
            "backtest_id": receipt.backtest_id,
            "strategy_id": receipt.strategy_id,
        }
    )
    try:
        session_generator = get_db_session(settings)
        session = next(session_generator)
        try:
            save_backtest_result(session, result_snapshot)
            return receipt.model_copy(
                update={
                    "storage_source": "database",
                    "result_data_mode": result_snapshot.data_mode,
                }
            )
        finally:
            session_generator.close()
    except Exception as exc:
        return receipt.model_copy(
            update={
                "data_status": DataStatus.UNAVAILABLE,
                "fallback_active": True,
                "fallback_reason": f"数据库回测任务写入失败，当前仅返回未持久化回测任务回执；错误类型={type(exc).__name__}。",
                "storage_source": "mock_fallback",
            }
        )


@backtests_router.get("/{backtest_id}", response_model=BacktestResponse)
def get_backtest_by_id(backtest_id: str) -> BacktestResponse:
    """按回测 ID 返回已保存的回测结果。"""

    return build_backtest_by_id_response(backtest_id, get_settings())


def build_backtest_by_id_response(backtest_id: str, settings: Settings) -> BacktestResponse:
    """查询指定回测结果；未开启数据库读取或记录不存在时返回 404。"""

    if not settings.enable_backtest_database_reads:
        raise_backtest_not_found(
            backtest_id,
            code="backtest_database_reads_disabled",
            message="Backtest database reads are disabled.",
        )

    session_generator = get_db_session(settings)
    session = next(session_generator)
    try:
        snapshot = get_backtest_snapshot_by_id(session, backtest_id)
        if snapshot is None:
            raise_backtest_not_found(
                backtest_id,
                code="backtest_result_not_found",
                message="Backtest result was not found.",
            )
        return snapshot.response
    finally:
        session_generator.close()


def raise_backtest_not_found(backtest_id: str, *, code: str, message: str) -> None:
    """返回结构化 404，方便前端区分未开启读取和任务结果不存在。"""

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": code,
            "message": message,
            "backtest_id": backtest_id,
        },
    )


router.include_router(result_router)
router.include_router(backtests_router)

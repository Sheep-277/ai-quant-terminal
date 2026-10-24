from fastapi import APIRouter, HTTPException, Path, Query, status

from app.core.config import DataProviderMode, Settings, get_settings
from app.core.market import MarketCode
from app.db.session import get_db_session
from app.schemas.market import DataStatus
from app.schemas.portfolio import PaperOrderStatus
from app.schemas.portfolio import PaperOrderCreateResponse, PaperOrderRequest, PortfolioResponse
from app.services.mock_portfolio_service import (
    create_mock_paper_order,
    get_portfolio_summary as build_service_portfolio_summary,
)
from app.services.portfolio_read_service import get_latest_portfolio_snapshot, get_portfolio_snapshot_by_account_id
from app.services.portfolio_write_service import save_paper_order_receipt


router = APIRouter()
portfolio_router = APIRouter(prefix="/portfolio", tags=["portfolio"])
paper_router = APIRouter(prefix="/paper", tags=["portfolio"])


@portfolio_router.get("/summary", response_model=PortfolioResponse)
def get_portfolio_summary(
    market: MarketCode = Query(default=MarketCode.US, description="当前市场代码：US / HK / CN"),
) -> PortfolioResponse:
    """返回模拟组合页面所需的结构化摘要；开启数据库读取时优先使用本地快照。"""

    return build_portfolio_summary_response(market, get_settings())


def build_portfolio_summary_response(market: MarketCode, settings: Settings) -> PortfolioResponse:
    """根据配置构造组合摘要；真实行情模式优先使用 Provider 重估持仓。"""

    fallback_response = build_service_portfolio_summary(market=market, settings=settings)
    if settings.data_provider == DataProviderMode.REAL:
        return fallback_response

    if not settings.enable_portfolio_database_reads:
        return fallback_response

    try:
        session_generator = get_db_session(settings)
        session = next(session_generator)
        try:
            snapshot = get_latest_portfolio_snapshot(session, market)
            if snapshot is None:
                return fallback_response
            return snapshot.response
        finally:
            session_generator.close()
    except Exception as error:
        return _append_portfolio_database_fallback_risk_flag(fallback_response, error)


def _append_portfolio_database_fallback_risk_flag(
    fallback_response: PortfolioResponse,
    error: Exception,
) -> PortfolioResponse:
    """数据库读取异常时保留 Mock 组合，并在 risk_flags 中暴露回退原因。"""

    return fallback_response.model_copy(
        update={
            "risk": fallback_response.risk.model_copy(
                update={
                    "risk_flags": [
                        *fallback_response.risk.risk_flags,
                        (
                            "数据库组合快照读取失败，当前页面已回退到服务层组合摘要；"
                            f"错误类型={type(error).__name__}。"
                        ),
                    ],
                }
            ),
        }
    )


@portfolio_router.get("/accounts/{account_id}/summary", response_model=PortfolioResponse)
def get_portfolio_account_summary(
    account_id: str = Path(min_length=1, max_length=80, description="模拟账户 ID"),
) -> PortfolioResponse:
    """按账户 ID 返回模拟组合快照；只读取数据库中的明确账户。"""

    return build_portfolio_account_summary_response(account_id, get_settings())


def build_portfolio_account_summary_response(account_id: str, settings: Settings) -> PortfolioResponse:
    """按 account_id 精确读取组合；关闭数据库读取或账户不存在时返回 404。"""

    normalized_account_id = account_id.strip()
    if not settings.enable_portfolio_database_reads:
        _raise_portfolio_account_not_found(
            code="portfolio_database_reads_disabled",
            message="Portfolio database reads are disabled.",
            account_id=normalized_account_id,
        )

    session_generator = get_db_session(settings)
    session = next(session_generator)
    try:
        snapshot = get_portfolio_snapshot_by_account_id(session, normalized_account_id)
        if snapshot is None:
            _raise_portfolio_account_not_found(
                code="portfolio_account_not_found",
                message="Portfolio account was not found.",
                account_id=normalized_account_id,
            )
        return snapshot.response
    finally:
        session_generator.close()


def _raise_portfolio_account_not_found(*, code: str, message: str, account_id: str) -> None:
    """抛出结构化账户读取错误，方便前端按 code 展示中文提示。"""

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": code,
            "message": message,
            "account_id": account_id,
        },
    )


@paper_router.post("/orders", response_model=PaperOrderCreateResponse)
def create_paper_order(request: PaperOrderRequest) -> PaperOrderCreateResponse:
    """创建模拟订单回执；开启数据库写入时保存到本地订单表。"""

    return build_paper_order_response(request, get_settings())


def build_paper_order_response(request: PaperOrderRequest, settings: Settings) -> PaperOrderCreateResponse:
    """根据配置创建模拟订单回执；默认不写库、不连接真实券商。"""

    receipt = create_mock_paper_order(request=request)
    if not settings.enable_portfolio_database_writes:
        return receipt

    try:
        session_generator = get_db_session(settings)
        session = next(session_generator)
        try:
            saved_order = save_paper_order_receipt(session, receipt)
            if saved_order is None:
                return _mark_paper_order_database_write_fallback(
                    receipt,
                    "数据库模拟账户不存在，当前仅返回未持久化 Mock 模拟订单。",
                )
            return receipt.model_copy(
                update={
                    "status": PaperOrderStatus(saved_order.status),
                    "storage_source": "database",
                }
            )
        finally:
            session_generator.close()
    except Exception as exc:
        return _mark_paper_order_database_write_fallback(
            receipt,
            f"数据库模拟订单写入失败，当前仅返回未持久化 Mock 模拟订单；错误类型={type(exc).__name__}。",
        )


def _mark_paper_order_database_write_fallback(
    receipt: PaperOrderCreateResponse,
    fallback_reason: str,
) -> PaperOrderCreateResponse:
    """模拟订单未能写入数据库时，返回带回退状态的未持久化回执。"""

    return receipt.model_copy(
        update={
            "data_status": DataStatus.UNAVAILABLE,
            "fallback_active": True,
            "fallback_reason": fallback_reason,
            "storage_source": "mock_fallback",
        }
    )


router.include_router(portfolio_router)
router.include_router(paper_router)

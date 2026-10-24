from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import Settings, get_settings
from app.core.market import MarketCode
from app.db.session import get_db_session
from app.schemas.strategy import (
    StrategyDraft,
    StrategyDraftCreateRequest,
    StrategyLabResponse,
    StrategyNaturalLanguageParseRequest,
    StrategyNaturalLanguageParseResponse,
)
from app.services.mock_strategy_service import create_mock_strategy_draft, get_mock_strategy_lab
from app.services.strategy_read_service import get_strategy_read_snapshot
from app.services.strategy_nl_parser import parse_strategy_natural_language
from app.services.strategy_write_service import create_strategy_draft_record


router = APIRouter()
lab_router = APIRouter(prefix="/strategy", tags=["strategy"])
strategies_router = APIRouter(prefix="/strategies", tags=["strategy"])


@lab_router.get("/lab", response_model=StrategyLabResponse)
def get_strategy_lab(
    market: MarketCode = Query(default=MarketCode.US, description="当前市场代码：US / HK / CN"),
) -> StrategyLabResponse:
    """返回策略实验室所需的结构化数据。"""

    return build_strategy_lab_response(market, get_settings())


def build_strategy_lab_response(market: MarketCode, settings: Settings) -> StrategyLabResponse:
    """根据配置构造 Strategy Lab 响应；开启数据库读取时优先使用本地策略草案。"""

    fallback_response = get_mock_strategy_lab(market=market)
    if not settings.enable_strategy_database_reads:
        return fallback_response

    session_generator = get_db_session(settings)
    session = next(session_generator)
    try:
        try:
            snapshot = get_strategy_read_snapshot(session, market)
        except Exception as exc:
            return fallback_response.model_copy(
                update={
                    "drafts": [
                        draft.model_copy(
                            update={
                                "parameters": {
                                    **draft.parameters,
                                    "data_status": "unavailable",
                                    "fallback_active": True,
                                    "fallback_reason": f"数据库策略草案读取失败，当前页面已回退到 Mock Strategy Lab；错误类型={type(exc).__name__}。",
                                }
                            },
                        )
                        for draft in fallback_response.drafts
                    ]
                },
            )
        if snapshot is None:
            return fallback_response
        return StrategyLabResponse(
            market=market,
            timestamp=fallback_response.timestamp,
            default_universe=fallback_response.default_universe,
            drafts=snapshot.drafts,
        )
    finally:
        session_generator.close()


@lab_router.post("/parse-natural-language", response_model=StrategyNaturalLanguageParseResponse)
def parse_strategy_text(request: StrategyNaturalLanguageParseRequest) -> StrategyNaturalLanguageParseResponse:
    """把自然语言策略描述解析为可编辑条件；不保存草案，不触发回测。"""

    try:
        return parse_strategy_natural_language(request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "strategy_natural_language_parse_failed",
                "message": str(exc),
            },
        ) from exc


@strategies_router.post("", response_model=StrategyDraft, status_code=status.HTTP_202_ACCEPTED)
def create_strategy_draft(request: StrategyDraftCreateRequest) -> StrategyDraft:
    """创建策略草案；开启数据库写入时保存到本地 strategies 表。"""

    return build_strategy_draft_response(request, get_settings())


def build_strategy_draft_response(request: StrategyDraftCreateRequest, settings: Settings) -> StrategyDraft:
    """根据配置创建策略草案；默认只返回 Mock 回执，不写入数据库。"""

    if not settings.enable_strategy_database_writes:
        return create_mock_strategy_draft(request=request)

    session_generator = get_db_session(settings)
    session = next(session_generator)
    try:
        try:
            return create_strategy_draft_record(session, request)
        except Exception as exc:
            draft = create_mock_strategy_draft(request=request)
            return draft.model_copy(
                update={
                    "parameters": {
                        **draft.parameters,
                        "data_status": "unavailable",
                        "fallback_active": True,
                        "fallback_reason": f"数据库策略草案写入失败，当前仅返回未持久化 Mock 草案；错误类型={type(exc).__name__}。",
                        "storage_source": "mock_fallback",
                    }
                },
            )
    finally:
        session_generator.close()


router.include_router(lab_router)
router.include_router(strategies_router)

from fastapi import APIRouter, Query

from app.core.config import Settings, get_settings
from app.db.repositories.provider_status_log_repository import ProviderStatusLogRepository
from app.db.session import get_db_session
from app.models.provider_status_log import ProviderStatusLog
from app.providers.factory import get_market_data_provider
from app.schemas.provider import ProviderStatusLogItem, ProviderStatusLogListResponse, ProviderStatusResponse
from app.services.provider_status_service import get_provider_status as get_provider_status_service


router = APIRouter(prefix="/provider", tags=["provider"])


@router.get("/status", response_model=ProviderStatusResponse)
def get_provider_status() -> ProviderStatusResponse:
    """返回当前市场数据 Provider 的运行状态。"""

    return build_provider_status_response(get_settings())


@router.get("/status/logs", response_model=ProviderStatusLogListResponse)
def list_provider_status_logs(
    limit: int = Query(default=20, ge=1, le=100, description="返回最近日志条数，范围 1-100。"),
    provider_name: str | None = Query(default=None, description="可选 Provider 名称过滤。"),
) -> ProviderStatusLogListResponse:
    """返回最近 Provider 状态日志；数据库不可用时返回空列表和回退原因。"""

    return build_provider_status_log_list_response(
        settings=get_settings(),
        limit=limit,
        provider_name=provider_name,
    )


def build_provider_status_response(settings: Settings) -> ProviderStatusResponse:
    """根据配置返回 Provider 状态；开启日志时同步写入数据库。"""

    provider = get_market_data_provider(settings)
    status = get_provider_status_service(provider=provider)

    if not settings.enable_provider_status_logging:
        return ProviderStatusResponse(**status)

    try:
        session_generator = get_db_session(settings)
        session = next(session_generator)
    except Exception:
        return ProviderStatusResponse(**status)

    try:
        repository = ProviderStatusLogRepository(session)
        get_provider_status_service(provider=provider, status_log_repository=repository)
        session.flush()
        recent_logs = repository.list_recent(limit=20, provider_name=status["provider_name"])
        session.commit()
        latest_log = recent_logs[0] if recent_logs else None
        return ProviderStatusResponse(
            **status,
            last_logged_at=latest_log.checked_at if latest_log is not None else None,
            recent_log_count=len(recent_logs),
        )
    except Exception:
        session.rollback()
        return ProviderStatusResponse(**status)
    finally:
        session_generator.close()


def build_provider_status_log_list_response(
    settings: Settings,
    *,
    limit: int = 20,
    provider_name: str | None = None,
) -> ProviderStatusLogListResponse:
    """读取最近 Provider 状态日志，供本地验收和数据源诊断使用。"""

    try:
        session_generator = get_db_session(settings)
        session = next(session_generator)
    except Exception as error:
        return _build_provider_status_log_unavailable_response(error)

    try:
        repository = ProviderStatusLogRepository(session)
        logs = repository.list_recent(limit=limit, provider_name=provider_name)
        return ProviderStatusLogListResponse(
            items=[_provider_status_log_to_item(log) for log in logs],
            total=len(logs),
            database_available=True,
            fallback_reason=None,
        )
    except Exception as error:
        return _build_provider_status_log_unavailable_response(error)
    finally:
        session_generator.close()


def _provider_status_log_to_item(log: ProviderStatusLog) -> ProviderStatusLogItem:
    """把 SQLAlchemy 日志模型转换为 API 响应 DTO。"""

    return ProviderStatusLogItem(
        id=log.id,
        provider_name=log.provider_name,
        mode=log.mode,
        ready=log.ready,
        data_status=log.data_status,
        fallback_active=log.fallback_active,
        fallback_reason=log.fallback_reason,
        checked_at=log.checked_at,
    )


def _build_provider_status_log_unavailable_response(error: Exception) -> ProviderStatusLogListResponse:
    """日志数据库不可用时返回可观察降级结果，避免验收页面或脚本直接失败。"""

    return ProviderStatusLogListResponse(
        items=[],
        total=0,
        database_available=False,
        fallback_reason=f"Provider 状态日志读取失败；错误类型={type(error).__name__}。",
    )

from app.db.repositories.provider_status_log_repository import ProviderStatusLogRepository
from app.models.provider_status_log import ProviderStatusLog
from app.providers.base import MarketDataProvider, ProviderStatus
from app.providers.factory import get_market_data_provider


def get_provider_status(
    provider: MarketDataProvider | None = None,
    status_log_repository: ProviderStatusLogRepository | None = None,
) -> ProviderStatus:
    """读取当前 Provider 状态；传入 Repository 时同步写入状态日志。"""

    resolved_provider = provider or get_market_data_provider()
    status = resolved_provider.get_provider_status()

    if status_log_repository is not None:
        status_log_repository.add(
            ProviderStatusLog(
                provider_name=status["provider_name"],
                mode=status["mode"],
                ready=status["ready"],
                data_status=status["data_status"],
                fallback_active=status["fallback_active"],
                fallback_reason=status["fallback_reason"],
            )
        )

    return status

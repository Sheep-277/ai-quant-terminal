class ProviderError(Exception):
    """Provider 层基础异常，用于统一描述外部数据源或数据归一化错误。"""

    def __init__(
        self,
        message: str,
        *,
        provider_name: str | None = None,
        retryable: bool = False,
    ) -> None:
        """保存可观测错误信息，避免上层只能解析异常字符串。"""

        super().__init__(message)
        self.message = message
        self.provider_name = provider_name
        self.retryable = retryable


class ProviderUnavailableError(ProviderError):
    """真实 Provider 不可用时抛出的异常，例如配置缺失或外部服务不可达。"""


class ProviderResponseError(ProviderError):
    """Provider 响应字段缺失或格式不符合项目标准结构时抛出的异常。"""

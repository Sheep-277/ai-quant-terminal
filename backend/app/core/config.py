from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DataProviderMode(StrEnum):
    """后端数据源模式；real 配置完整时尝试读取真实数据，失败时回退到 Mock。"""

    MOCK = "mock"
    REAL = "real"


class SearchProviderMode(StrEnum):
    """新闻/搜索源模式；先用于 AI Research 读取公开事件线索。"""

    MOCK = "mock"
    TAVILY = "tavily"
    SERPAPI = "serpapi"


class Settings(BaseSettings):
    """后端运行配置，统一从环境变量或 .env 文件读取。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_name: str = Field(default="AI Quant Terminal API", alias="PROJECT_NAME")
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")
    data_provider: DataProviderMode = Field(default=DataProviderMode.MOCK, alias="DATA_PROVIDER")
    real_provider_name: str = Field(default="RealMarketDataProvider", alias="REAL_PROVIDER_NAME")
    real_provider_base_url: str | None = Field(default=None, alias="REAL_PROVIDER_BASE_URL")
    real_provider_api_key_env: str | None = Field(default=None, alias="REAL_PROVIDER_API_KEY_ENV")
    real_provider_api_key_header: str = Field(default="Authorization", alias="REAL_PROVIDER_API_KEY_HEADER")
    database_url: str = Field(
        default="mysql+pymysql://root:password@localhost:3306/ai_quant_terminal?charset=utf8mb4",
        alias="DATABASE_URL",
    )
    enable_provider_status_logging: bool = Field(default=False, alias="ENABLE_PROVIDER_STATUS_LOGGING")
    enable_market_database_reads: bool = Field(default=False, alias="ENABLE_MARKET_DATABASE_READS")
    enable_stock_database_reads: bool = Field(default=False, alias="ENABLE_STOCK_DATABASE_READS")
    enable_monitor_database_reads: bool = Field(default=False, alias="ENABLE_MONITOR_DATABASE_READS")
    enable_ai_research_database_reads: bool = Field(default=False, alias="ENABLE_AI_RESEARCH_DATABASE_READS")
    enable_ai_research_database_writes: bool = Field(default=False, alias="ENABLE_AI_RESEARCH_DATABASE_WRITES")
    enable_strategy_database_reads: bool = Field(default=False, alias="ENABLE_STRATEGY_DATABASE_READS")
    enable_strategy_database_writes: bool = Field(default=False, alias="ENABLE_STRATEGY_DATABASE_WRITES")
    enable_backtest_database_reads: bool = Field(default=False, alias="ENABLE_BACKTEST_DATABASE_READS")
    enable_backtest_database_writes: bool = Field(default=False, alias="ENABLE_BACKTEST_DATABASE_WRITES")
    enable_portfolio_database_reads: bool = Field(default=False, alias="ENABLE_PORTFOLIO_DATABASE_READS")
    enable_portfolio_database_writes: bool = Field(default=False, alias="ENABLE_PORTFOLIO_DATABASE_WRITES")
    enable_llm_research: bool = Field(default=False, alias="ENABLE_LLM_RESEARCH")
    bailian_api_key: str | None = Field(default=None, alias="BAILIAN_API_KEY")
    bailian_base_url: str | None = Field(default=None, alias="BAILIAN_BASE_URL")
    bailian_model: str = Field(default="qwen-plus", alias="BAILIAN_MODEL")
    bailian_timeout_seconds: float = Field(default=30.0, alias="BAILIAN_TIMEOUT_SECONDS")
    bailian_summary_max_tokens: int = Field(default=512, alias="BAILIAN_SUMMARY_MAX_TOKENS")
    search_provider: SearchProviderMode = Field(default=SearchProviderMode.MOCK, alias="SEARCH_PROVIDER")
    search_api_key: str | None = Field(default=None, alias="SEARCH_API_KEY")
    search_result_limit: int = Field(default=5, alias="SEARCH_RESULT_LIMIT")
    search_timeout_seconds: float = Field(default=10.0, alias="SEARCH_TIMEOUT_SECONDS")


@lru_cache
def get_settings() -> Settings:
    """缓存配置对象，避免每次请求都重复读取环境变量。"""

    return Settings()

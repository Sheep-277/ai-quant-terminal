from app.core.config import DataProviderMode, Settings, get_settings
from app.providers.base import MarketDataProvider
from app.providers.demo_quote_adapter import DemoQuoteAdapter
from app.providers.http_quote_fetcher import HttpQuoteFetcher
from app.providers.market_data import MockMarketDataProvider
from app.providers.real_market_data import RealMarketDataProvider
from app.providers.yahoo_finance_adapter import YahooFinanceAdapter


_mock_market_data_provider = MockMarketDataProvider()


def get_market_data_provider(settings: Settings | None = None) -> MarketDataProvider:
    """根据运行配置返回市场数据 Provider，作为 Mock 与真实数据源的统一切换入口。"""

    resolved_settings = settings or get_settings()

    if resolved_settings.data_provider == DataProviderMode.MOCK:
        return _mock_market_data_provider
    if resolved_settings.data_provider == DataProviderMode.REAL:
        return _build_real_market_data_provider(resolved_settings)

    raise ValueError(f"Unsupported DATA_PROVIDER: {resolved_settings.data_provider}")


def _build_real_market_data_provider(settings: Settings) -> RealMarketDataProvider:
    """创建真实 Provider 过渡层，并显式保留 Mock 作为失败回退。"""

    return RealMarketDataProvider(
        settings=settings,
        fallback_provider=_mock_market_data_provider,
        quote_fetcher=_build_http_provider_fetcher(settings),
    )


def _build_http_provider_fetcher(settings: Settings) -> HttpQuoteFetcher | DemoQuoteAdapter:
    """创建真实 Provider JSON 获取器；DemoProvider 走本地样例，其余 Provider 走 HTTP。"""

    provider_name = settings.real_provider_name.strip().lower()
    if provider_name == "demoprovider":
        # DemoProvider 用于本地验证 real 模式全链路，不读取密钥、不访问外部网络。
        return DemoQuoteAdapter()
    if provider_name == "yahoofinance":
        # Yahoo Finance chart 接口不需要 API Key，用于课程演示的无 Key 真实行情最小闭环。
        return YahooFinanceAdapter()

    return HttpQuoteFetcher(api_key_header=settings.real_provider_api_key_header)

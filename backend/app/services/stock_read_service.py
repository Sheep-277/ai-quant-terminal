from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.market import MarketCode, get_market_context
from app.db.repositories.latest_quote_repository import LatestQuoteRepository
from app.db.repositories.stock_repository import StockRepository
from app.providers.base import ProviderStatus
from app.providers.factory import get_market_data_provider
from app.schemas.market import DataStatus
from app.schemas.stock import MarketDataSourceStatus, StockAssetType, StockProfile, StockQuote


@dataclass(frozen=True)
class StockReadSnapshot:
    """个股基础资料和最新行情的只读快照。"""

    profile: StockProfile
    quote: StockQuote
    source: str
    quote_data_source: MarketDataSourceStatus | None = None


def get_stock_read_snapshot(session: Session, market: MarketCode, symbol: str) -> StockReadSnapshot:
    """优先读取数据库个股快照；缺少股票或行情时读取当前配置的 Provider。"""

    normalized_symbol = symbol.strip().upper()
    stock_repository = StockRepository(session)
    quote_repository = LatestQuoteRepository(session)
    stock = stock_repository.get_by_market_symbol(market.value, normalized_symbol)
    quote = quote_repository.get_by_market_symbol(market.value, normalized_symbol)

    if stock is not None and quote is not None:
        return StockReadSnapshot(
            profile=StockProfile(
                market=MarketCode(stock.market),
                symbol=stock.symbol,
                name=stock.name,
                asset_type=StockAssetType(stock.asset_type),
                exchange=stock.exchange,
                currency=stock.currency,
                timezone=stock.timezone,
                sector=stock.sector or "",
                industry=stock.industry or "",
            ),
            quote=StockQuote(
                price=float(quote.price),
                change=float(quote.change_amount),
                change_percent=float(quote.change_percent),
                volume=quote.volume,
                turnover=float(quote.turnover),
                timestamp=quote.quote_timestamp,
                data_status=DataStatus(quote.data_status),
            ),
            source="database",
        )

    return _get_mock_stock_read_snapshot(market, normalized_symbol)


def _get_mock_stock_read_snapshot(market: MarketCode, symbol: str) -> StockReadSnapshot:
    """从当前 Provider 构造快照，保留真实行情、样例和失败回退的区别。"""

    context = get_market_context(market)
    provider = get_market_data_provider()
    asset_profile = provider.get_asset_profile(market, symbol)
    provider_quote = provider.get_quote(market, symbol)
    quote_data_source = build_provider_quote_data_source(provider_quote["data_status"], provider.get_provider_status())

    return StockReadSnapshot(
        profile=StockProfile(
            market=market,
            symbol=symbol,
            name=asset_profile["name"],
            asset_type=StockAssetType.COMMON_STOCK,
            exchange=asset_profile["exchange"],
            currency=context.currency,
            timezone=context.timezone,
            sector=asset_profile["sector"],
            industry=asset_profile["industry"],
        ),
        quote=StockQuote(
            price=provider_quote["price"],
            change=provider_quote["change"],
            change_percent=provider_quote["change_percent"],
            volume=provider_quote["volume"],
            turnover=provider_quote["turnover"],
            timestamp=provider_quote.get("timestamp"),
            data_status=provider_quote["data_status"],
        ),
        source=quote_data_source.source,
        quote_data_source=quote_data_source,
    )


def build_provider_quote_data_source(
    data_status: DataStatus, provider_status: ProviderStatus,
) -> MarketDataSourceStatus:
    """统一解释本次报价结果；配置成功不代表报价请求成功。"""

    if provider_status["mode"] == "mock":
        return MarketDataSourceStatus(
            source="mock_provider", detail="最新行情来自当前 Mock Provider",
            fallback_active=False, data_status=data_status,
        )

    if data_status == DataStatus.UNAVAILABLE or provider_status.get("active_source") == "mock_fallback":
        return MarketDataSourceStatus(
            source="mock_fallback", detail="最新行情来自 Mock Provider 回退",
            fallback_active=True, data_status=data_status,
        )

    source = provider_status.get("active_source", "provider")
    return MarketDataSourceStatus(
        source=source,
        detail="最新行情来自本地 DemoProvider 样例数据" if source == "demo_provider" else "最新行情来自真实 Provider",
        fallback_active=False, data_status=data_status,
    )

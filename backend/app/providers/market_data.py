from datetime import date

from app.core.market import MarketCode
from app.providers.base import (
    ProviderAssetProfile,
    ProviderBar,
    ProviderFinancials,
    ProviderMarketBreadth,
    ProviderMarketEvent,
    ProviderMarketIndex,
    ProviderMarketOverviewData,
    ProviderQuote,
    ProviderResearchNotes,
    ProviderSectorPerformance,
    ProviderStatus,
)
from app.providers.mock_market_fixtures import (
    DEFAULT_STOCK_SYMBOLS,
    MARKET_OVERVIEW_FIXTURES,
    STOCK_RESEARCH_FIXTURES,
    MarketOverviewFixture,
    StockResearchFixture,
)
from app.schemas.market import DataStatus, MarketEventOrigin


class MockMarketDataProvider:
    """当前阶段的 Mock 行情 Provider，未来可替换为真实数据源适配器。"""

    def get_provider_status(self) -> ProviderStatus:
        """返回 Mock Provider 的运行状态。"""

        return {
            "provider_name": "MockMarketDataProvider",
            "mode": "mock",
            "ready": True,
            "data_status": DataStatus.REALTIME,
            "fallback_active": False,
            "fallback_reason": None,
        }

    def get_default_stock_symbol(self, market: MarketCode) -> str:
        """根据市场返回默认研究标的。"""

        return DEFAULT_STOCK_SYMBOLS[market]

    def supports_symbol(self, market: MarketCode, symbol: str) -> bool:
        """判断 Mock 股票池是否覆盖指定标的，不通过回退 fixture 间接推断。"""

        normalized_symbol = symbol.strip().upper()
        return normalized_symbol in STOCK_RESEARCH_FIXTURES[market]

    def get_stock_research_fixture(self, market: MarketCode, symbol: str | None = None) -> StockResearchFixture:
        """返回个股研究 Mock 原始数据，不在 Provider 内组装 API 响应。"""

        fixtures = STOCK_RESEARCH_FIXTURES[market]
        normalized_symbol = symbol.strip().upper() if symbol else self.get_default_stock_symbol(market)

        return fixtures.get(normalized_symbol, fixtures[self.get_default_stock_symbol(market)])

    def get_quote(self, market: MarketCode, symbol: str) -> ProviderQuote:
        """从 Mock fixture 提取标准行情快照，为真实 Provider 合同对齐做准备。"""

        fixture = self.get_stock_research_fixture(market, symbol)
        price, change, change_percent, volume, turnover = fixture["quote"]

        return {
            "price": price,
            "change": change,
            "change_percent": change_percent,
            "volume": volume,
            "turnover": turnover,
            "data_status": DataStatus.REALTIME if market is MarketCode.US else DataStatus.DELAYED,
        }

    def get_asset_profile(self, market: MarketCode, symbol: str) -> ProviderAssetProfile:
        """从 Mock fixture 提取标准标的资料，为真实 Provider 合同对齐做准备。"""

        fixture = self.get_stock_research_fixture(market, symbol)

        return {
            "symbol": fixture["symbol"],
            "name": fixture["name"],
            "exchange": fixture["exchange"],
            "sector": fixture["sector"],
            "industry": fixture["industry"],
        }

    def get_bars(
        self,
        market: MarketCode,
        symbol: str,
        *,
        interval: str = "1d",
        count: int = 30,
        start: date | None = None,
        end: date | None = None,
    ) -> list[ProviderBar]:
        """基于 Mock seed 生成标准 K 线序列；时间边界参数保留给真实 Provider 使用。"""

        fixture = self.get_stock_research_fixture(market, symbol)
        base_price, daily_step = fixture["kline_seed"]
        latest_volume = fixture["quote"][3]
        bars: list[ProviderBar] = []

        for index in range(count):
            trend_price = base_price + index * daily_step
            step_size = max(abs(daily_step), base_price * 0.006)
            cycle_wave = ((index % 7) - 3) * step_size * 0.42
            pulse_wave = (1 if index % 11 in {3, 4} else -1 if index % 11 in {8, 9} else 0) * step_size * 1.15
            open_price = trend_price + cycle_wave * 0.72 - pulse_wave * 0.18
            close_price = trend_price + daily_step * 0.35 + pulse_wave + cycle_wave * 0.32
            wick_size = step_size * (0.85 + (index % 4) * 0.18)
            high_price = max(open_price, close_price) + wick_size
            low_price = min(open_price, close_price) - wick_size * 0.78

            bars.append(
                {
                    "offset": count - 1 - index,
                    "open": round(open_price, 2),
                    "high": round(high_price, 2),
                    "low": round(max(low_price, 0.01), 2),
                    "close": round(close_price, 2),
                    "volume": max(int(latest_volume * (0.72 + index / 90)), 0),
                }
            )

        return bars

    def get_financials(self, market: MarketCode, symbol: str) -> ProviderFinancials:
        """从 Mock fixture 提取标准财务指标，为 service 脱离 fixture 解包做准备。"""

        fixture = self.get_stock_research_fixture(market, symbol)
        pe_ttm, pb, ps_ttm, pfcf_ttm = fixture["valuation"]
        roe_ttm, roic_ttm, gross_margin_ttm, operating_margin_ttm = fixture["profitability"]
        fcf_ttm, operating_cash_flow_ttm, capex_ttm = fixture["cash_flow"]

        return {
            "pe_ttm": pe_ttm,
            "pb": pb,
            "ps_ttm": ps_ttm,
            "pfcf_ttm": pfcf_ttm,
            "roe_ttm": roe_ttm,
            "roic_ttm": roic_ttm,
            "gross_margin_ttm": gross_margin_ttm,
            "operating_margin_ttm": operating_margin_ttm,
            "fcf_ttm": fcf_ttm,
            "operating_cash_flow_ttm": operating_cash_flow_ttm,
            "capex_ttm": capex_ttm,
        }

    def get_research_notes(self, market: MarketCode, symbol: str) -> ProviderResearchNotes:
        """从 Mock fixture 提取标准研究说明，并显式标记是否使用了回退数据。"""

        normalized_symbol = symbol.strip().upper()
        fixture = self.get_stock_research_fixture(market, normalized_symbol)

        return {
            "risk_flags": fixture["risk_flags"],
            "summary_points": fixture["summary_points"],
            "direction": fixture["direction"],
            "fallback_symbol": None if self.supports_symbol(market, normalized_symbol) else fixture["symbol"],
        }

    def get_market_overview_fixture(self, market: MarketCode) -> MarketOverviewFixture:
        """返回市场总览 Mock 原始数据，不在 Provider 内组装 API 响应。"""

        return MARKET_OVERVIEW_FIXTURES[market]

    def get_market_data_status(self, market: MarketCode) -> DataStatus:
        """从 Mock fixture 提取市场数据状态。"""

        return self.get_market_overview_fixture(market)["data_status"]

    def get_market_overview_data(
        self,
        market: MarketCode,
        chart_symbol: str,
        *,
        interval: str = "1d",
        count: int = 30,
    ) -> ProviderMarketOverviewData:
        """Mock 读取无需线程，保留既有指数与图表数据合同。"""

        return {
            "indices": self.get_market_indices(market),
            "bars": self.get_bars(market, chart_symbol, interval=interval, count=count),
        }

    def get_market_indices(self, market: MarketCode) -> list[ProviderMarketIndex]:
        """从 Mock fixture 提取标准指数快照。"""

        return [
            {
                "name": name,
                "symbol": symbol,
                "value": value,
                "change_percent": change_percent,
            }
            for name, symbol, value, change_percent in self.get_market_overview_fixture(market)["indices"]
        ]

    def get_market_breadth(self, market: MarketCode) -> ProviderMarketBreadth:
        """从 Mock fixture 提取标准市场宽度。"""

        (
            advancers_percent,
            decliners_percent,
            unchanged_percent,
            new_highs,
            new_lows,
        ) = self.get_market_overview_fixture(market)["breadth"]

        return {
            "advancers_percent": advancers_percent,
            "decliners_percent": decliners_percent,
            "unchanged_percent": unchanged_percent,
            "new_highs": new_highs,
            "new_lows": new_lows,
            "source": "mock_provider",
            "data_status": self.get_market_data_status(market),
        }

    def get_sector_performance(self, market: MarketCode) -> list[ProviderSectorPerformance]:
        """从 Mock fixture 提取标准行业表现。"""

        return [
            {
                "name": name,
                "change_percent": change_percent,
                "source": "mock_provider",
                "data_status": self.get_market_data_status(market),
            }
            for name, change_percent in self.get_market_overview_fixture(market)["sectors"]
        ]

    def get_market_events(self, market: MarketCode) -> list[ProviderMarketEvent]:
        """从 Mock fixture 提取标准市场事件。"""

        return [
            {
                "source": source,
                "origin": MarketEventOrigin.MOCK_SAMPLE,
                "title": title,
                "impact": impact,
                "confidence": confidence,
            }
            for source, title, impact, confidence in self.get_market_overview_fixture(market)["events"]
        ]

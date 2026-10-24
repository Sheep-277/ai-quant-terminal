from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class MarketCode(StrEnum):
    US = "US"
    HK = "HK"
    CN = "CN"


class MarketContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    market: MarketCode
    timezone: str
    currency: str
    benchmark: str
    trading_calendar: str


MARKET_CONTEXTS: dict[MarketCode, MarketContext] = {
    MarketCode.US: MarketContext(
        market=MarketCode.US,
        timezone="America/New_York",
        currency="USD",
        benchmark="S&P 500",
        trading_calendar="XNYS",
    ),
    MarketCode.HK: MarketContext(
        market=MarketCode.HK,
        timezone="Asia/Hong_Kong",
        currency="HKD",
        benchmark="Hang Seng Index",
        trading_calendar="XHKG",
    ),
    MarketCode.CN: MarketContext(
        market=MarketCode.CN,
        timezone="Asia/Shanghai",
        currency="CNY",
        benchmark="CSI 300",
        trading_calendar="XSHG/XSHE",
    ),
}


def get_market_context(market: MarketCode) -> MarketContext:
    return MARKET_CONTEXTS[market]

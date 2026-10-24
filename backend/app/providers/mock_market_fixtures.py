from typing import TypedDict

from app.core.market import MarketCode
from app.schemas.market import DataStatus, Direction


class StockResearchFixture(TypedDict):
    """Mock Provider 内部使用的个股研究原始数据，不能泄漏到通用 Provider 合同。"""

    symbol: str
    name: str
    exchange: str
    sector: str
    industry: str
    quote: tuple[float, float, float, int, float]
    valuation: tuple[float, float, float, float]
    profitability: tuple[float, float, float, float]
    cash_flow: tuple[float, float, float]
    risk_flags: list[str]
    summary_points: list[str]
    direction: Direction
    kline_seed: tuple[float, float]


class MarketOverviewFixture(TypedDict):
    """Mock Provider 内部使用的市场总览原始数据，不能泄漏到通用 Provider 合同。"""

    data_status: DataStatus
    indices: list[tuple[str, str, float, float]]
    breadth: tuple[float, float, float, int, int]
    sectors: list[tuple[str, float]]
    events: list[tuple[str, str, str, float]]


DEFAULT_STOCK_SYMBOLS: dict[MarketCode, str] = {
    MarketCode.US: "NVDA",
    MarketCode.HK: "00700.HK",
    MarketCode.CN: "600519.SH",
}


MARKET_OVERVIEW_FIXTURES: dict[MarketCode, MarketOverviewFixture] = {
    MarketCode.US: {
        "data_status": DataStatus.REALTIME,
        "indices": [
            ("S&P 500", "SPX", 6184.22, 0.0042),
            ("NASDAQ 100", "NDX", 22958.14, 0.0068),
            ("VIX", "VIX", 14.8, -0.031),
        ],
        "breadth": (0.61, 0.34, 0.05, 118, 24),
        "sectors": [
            ("Semiconductors", 0.0134),
            ("Software", 0.0071),
            ("Banks", -0.0028),
            ("Energy", -0.0063),
        ],
        "events": [
            ("FAST_PATH", "NVDA 成交量比率突破 1.8x", "日内偏强", 0.92),
            ("AI_PATH", "芯片出口相关新闻与板块波动同时出现", "中等风险", 0.78),
        ],
    },
    MarketCode.HK: {
        "data_status": DataStatus.DELAYED,
        "indices": [
            ("Hang Seng Index", "HSI", 25921.3, 0.0031),
            ("Hang Seng TECH", "HSTECH", 5812.77, 0.0094),
            ("HS Volatility Index", "VHSI", 19.2, -0.018),
        ],
        "breadth": (0.54, 0.39, 0.07, 63, 18),
        "sectors": [
            ("Internet", 0.0108),
            ("Property", -0.0082),
            ("Banks", 0.0024),
            ("Biotech", -0.0044),
        ],
        "events": [
            ("FAST_PATH", "恒生科技指数接近盘中高位", "短线偏强", 0.84),
            ("PROVIDER", "部分港股小盘股基本面数据存在延迟", "数据提示", 1.0),
        ],
    },
    MarketCode.CN: {
        "data_status": DataStatus.DELAYED,
        "indices": [
            ("CSI 300", "000300.SH", 4112.65, -0.0018),
            ("SSE Composite", "000001.SH", 3286.4, 0.0005),
            ("ChiNext Index", "399006.SZ", 2189.73, -0.0042),
        ],
        "breadth": (0.48, 0.46, 0.06, 41, 27),
        "sectors": [
            ("EV Chain", 0.0076),
            ("Brokerage", 0.0033),
            ("Liquor", -0.0069),
            ("AI Hardware", 0.0112),
        ],
        "events": [
            ("FAST_PATH", "AI 硬件组合相对强度扩大", "短线偏强", 0.81),
            ("MARKET_RULES", "涨停标的已从入场模拟中排除", "执行约束", 1.0),
        ],
    },
}


STOCK_RESEARCH_FIXTURES: dict[MarketCode, dict[str, StockResearchFixture]] = {
    MarketCode.US: {
        "NVDA": {
            "symbol": "NVDA",
            "name": "NVIDIA Corporation",
            "exchange": "NASDAQ",
            "sector": "Technology",
            "industry": "Semiconductors",
            "quote": (181.42, 2.38, 0.0133, 218_430_000, 39_612_000_000),
            "valuation": (48.6, 41.2, 25.4, 65.8),
            "profitability": (0.91, 0.57, 0.754, 0.626),
            "cash_flow": (62_100_000_000, 69_300_000_000, 7_200_000_000),
            "risk_flags": ["估值处于高位", "AI 芯片需求预期波动较大"],
            "summary_points": [
                "趋势和动量仍偏强，但 RSI 已接近偏热区间。",
                "ROE 和 ROIC 显示资本回报效率较高。",
                "估值倍数较高，后续需要关注盈利增速能否兑现。",
            ],
            "direction": Direction.POSITIVE,
            "kline_seed": (172.8, 1.8),
        },
        "AAPL": {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "exchange": "NASDAQ",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "quote": (232.18, -0.56, -0.0024, 18_540_000, 4_304_000_000),
            "valuation": (31.4, 49.8, 8.2, 29.6),
            "profitability": (1.38, 0.61, 0.462, 0.318),
            "cash_flow": (104_200_000_000, 118_300_000_000, 14_100_000_000),
            "risk_flags": ["收入增长进入成熟阶段", "硬件换机周期对短期业绩影响较大"],
            "summary_points": [
                "价格短期动量偏弱，但现金流质量仍较稳定。",
                "PB 较高，市场对品牌和回购能力给出较高溢价。",
                "需要关注新产品周期与服务业务增长能否抵消硬件波动。",
            ],
            "direction": Direction.NEUTRAL,
            "kline_seed": (228.4, 0.42),
        },
    },
    MarketCode.HK: {
        "00700.HK": {
            "symbol": "00700.HK",
            "name": "Tencent Holdings Ltd.",
            "exchange": "HKEX",
            "sector": "Communication Services",
            "industry": "Internet Content & Services",
            "quote": (642.5, -4.5, -0.007, 18_640_000, 11_978_000_000),
            "valuation": (24.8, 4.9, 6.8, 21.5),
            "profitability": (0.218, 0.174, 0.501, 0.329),
            "cash_flow": (186_000_000_000, 212_000_000_000, 26_000_000_000),
            "risk_flags": ["港股数据为延迟行情", "互联网板块受政策和流动性影响较大"],
            "summary_points": [
                "价格短期震荡，动量不如美股半导体强。",
                "自由现金流仍较稳健，估值相对成长股更温和。",
                "需要关注港股整体流动性和外资风险偏好。",
            ],
            "direction": Direction.NEUTRAL,
            "kline_seed": (628.0, 5.2),
        },
        "03690.HK": {
            "symbol": "03690.HK",
            "name": "Meituan",
            "exchange": "HKEX",
            "sector": "Consumer Discretionary",
            "industry": "Internet Retail",
            "quote": (102.7, 1.8, 0.0178, 37_200_000, 3_820_000_000),
            "valuation": (19.7, 3.4, 2.1, 18.2),
            "profitability": (0.162, 0.121, 0.389, 0.094),
            "cash_flow": (28_600_000_000, 35_400_000_000, 6_800_000_000),
            "risk_flags": ["港股数据为延迟行情", "本地生活竞争会影响利润率修复"],
            "summary_points": [
                "平台经济标的对消费复苏和竞争格局更敏感。",
                "估值较互联网龙头更低，但盈利稳定性也更需要验证。",
                "短期需要观察成交量放大是否能持续。",
            ],
            "direction": Direction.POSITIVE,
            "kline_seed": (96.4, 0.76),
        },
    },
    MarketCode.CN: {
        "600519.SH": {
            "symbol": "600519.SH",
            "name": "贵州茅台",
            "exchange": "SSE",
            "sector": "Consumer Staples",
            "industry": "Distillers & Vintners",
            "quote": (1486.12, 12.31, 0.0084, 4_210_000, 6_257_000_000),
            "valuation": (21.6, 7.4, 10.2, 28.9),
            "profitability": (0.342, 0.298, 0.913, 0.702),
            "cash_flow": (72_800_000_000, 78_400_000_000, 5_600_000_000),
            "risk_flags": ["A 股行情为延迟数据", "消费需求修复节奏仍需观察"],
            "summary_points": [
                "价格相对强于消费板块，短期趋势偏稳。",
                "毛利率和 ROE 仍处在较高水平。",
                "估值不极端，但业绩增长弹性可能低于高成长行业。",
            ],
            "direction": Direction.POSITIVE,
            "kline_seed": (1458.0, 10.5),
        },
        "300750.SZ": {
            "symbol": "300750.SZ",
            "name": "宁德时代",
            "exchange": "SZSE",
            "sector": "Industrials",
            "industry": "Electrical Components & Equipment",
            "quote": (286.35, -3.42, -0.0118, 23_180_000, 6_638_000_000),
            "valuation": (25.2, 5.1, 3.8, 31.4),
            "profitability": (0.226, 0.183, 0.274, 0.143),
            "cash_flow": (39_600_000_000, 61_200_000_000, 21_600_000_000),
            "risk_flags": ["A 股行情为延迟数据", "新能源产业链价格周期会影响利润率"],
            "summary_points": [
                "短期价格承压，动量信号弱于消费龙头。",
                "ROIC 仍高于多数制造业公司，但资本开支压力较大。",
                "需要跟踪电池价格、海外需求和产业链库存。",
            ],
            "direction": Direction.NEGATIVE,
            "kline_seed": (301.2, -0.92),
        },
    },
}

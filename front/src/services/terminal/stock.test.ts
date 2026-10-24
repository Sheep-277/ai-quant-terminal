import { request } from '@umijs/max';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { StockResearchResponse } from '@/features/terminal/apiTypes';
import type { MarketCode } from '@/features/terminal/types';
import { getStockResearch } from './stock';

vi.mock('@umijs/max', () => ({
  request: vi.fn(),
}));

const stockResearchResponse: StockResearchResponse = {
  profile: {
    market: 'US',
    symbol: 'AAPL',
    name: 'Apple Inc.',
    asset_type: 'common_stock',
    exchange: 'NASDAQ',
    currency: 'USD',
    timezone: 'America/New_York',
    sector: 'Technology',
    industry: 'Consumer Electronics',
  },
  quote: {
    price: 232.18,
    change: 2.31,
    change_percent: 0.01005,
    volume: 48_500_000,
    turnover: 11_260_000_000,
    timestamp: '2026-10-16T20:00:00Z',
    data_status: 'delayed',
  },
  valuation: {
    pe_ttm: 34.2,
    pb: 51.3,
    ps_ttm: 8.7,
    pfcf_ttm: 31.8,
  },
  profitability: {
    roe_ttm: 1.57,
    roic_ttm: 0.62,
    gross_margin_ttm: 0.47,
    operating_margin_ttm: 0.32,
  },
  cash_flow: {
    fcf_ttm: 108_000_000_000,
    operating_cash_flow_ttm: 125_000_000_000,
    capex_ttm: -17_000_000_000,
  },
  technical: {
    rsi_14: 58.4,
    macd: 2.16,
    macd_signal: 1.92,
    macd_histogram: 0.24,
  },
  technical_data_source: {
    source: 'quant_pipeline',
    detail: 'YahooFinance K线计算',
    fallback_active: false,
    data_status: 'delayed',
  },
  factor_snapshot: {
    momentum_20d: 0.081,
    trend_strength: 0.72,
    volatility_20d: 0.19,
    quality_score: 0.88,
    composite_score: 0.81,
  },
  quant_signals: [],
  quote_data_source: {
    source: 'yahoo_finance',
    detail: 'YahooFinance 公开行情',
    fallback_active: false,
    data_status: 'delayed',
  },
  kline: {
    interval: '1d',
    data_status: 'delayed',
    bars: [
      {
        timestamp: '2026-10-16T04:00:00Z',
        open: 229.7,
        high: 233.1,
        low: 228.9,
        close: 232.18,
        volume: 48_500_000,
      },
    ],
  },
  kline_data_source: {
    source: 'yahoo_finance',
    detail: 'YahooFinance 日线',
    fallback_active: false,
    data_status: 'delayed',
  },
  risk_flags: ['20D annualized volatility elevated'],
  summary_points: ['动量保持正值', '估值处于较高区间'],
  summary_data_source: {
    source: 'quant_pipeline',
    detail: '确定性量化摘要',
    fallback_active: false,
    data_status: 'delayed',
  },
  direction: 'positive',
};

describe('stock service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('按市场和股票代码获取研究快照并保留数据源状态', async () => {
    vi.mocked(request).mockResolvedValue(stockResearchResponse);

    const response = await getStockResearch({ market: 'US', symbol: 'AAPL' });

    expect(response).toEqual(stockResearchResponse);
    expect(request).toHaveBeenCalledWith('/api/v1/stock/research', {
      method: 'GET',
      params: { market: 'US', symbol: 'AAPL' },
    });
    expect(response.quote_data_source).toMatchObject({
      source: 'yahoo_finance',
      data_status: 'delayed',
    });
    expect(response.kline_data_source).toMatchObject({
      source: 'yahoo_finance',
      data_status: 'delayed',
    });
  });

  it.each<[MarketCode, string]>([
    ['US', 'AAPL'],
    ['HK', '00700.HK'],
    ['CN', '600519.SH'],
  ])('显式传递 %s 市场和 %s 股票代码', async (market, symbol) => {
    vi.mocked(request).mockResolvedValue({
      ...stockResearchResponse,
      profile: {
        ...stockResearchResponse.profile,
        market,
        symbol,
      },
    });

    await getStockResearch({ market, symbol });

    expect(request).toHaveBeenCalledWith('/api/v1/stock/research', {
      method: 'GET',
      params: { market, symbol },
    });
  });

  it('未指定股票代码时保留可选参数供后端选择默认标的', async () => {
    vi.mocked(request).mockResolvedValue(stockResearchResponse);

    await getStockResearch({ market: 'US' });

    expect(request).toHaveBeenCalledWith('/api/v1/stock/research', {
      method: 'GET',
      params: { market: 'US', symbol: undefined },
    });
  });

  it('保留个股研究请求错误供页面统一处理', async () => {
    const requestError = new Error('stock research unavailable');
    vi.mocked(request).mockRejectedValue(requestError);

    await expect(
      getStockResearch({ market: 'HK', symbol: '00700.HK' }),
    ).rejects.toBe(requestError);
  });
});

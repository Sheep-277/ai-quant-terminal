import { cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PortfolioResponse, StockResearchResponse } from './apiTypes';
import { marketSnapshots } from './mockData';
import type { MarketCode } from './types';
import { useTerminalPageData } from './useTerminalPageData';

const dependencyMocks = vi.hoisted(() => ({
  useAIResearchLLMStatus: vi.fn(),
  useAIResearchTask: vi.fn(),
  useBacktestResult: vi.fn(),
  useCreateAIResearchTask: vi.fn(),
  useCreateBacktestTask: vi.fn(),
  useCreatePaperOrder: vi.fn(),
  useCreateStrategyDraft: vi.fn(),
  useMarket: vi.fn(),
  useMarketOverview: vi.fn(),
  useMonitorStream: vi.fn(),
  usePortfolioSummary: vi.fn(),
  usePreTradeRiskCheck: vi.fn(),
  useProviderStatus: vi.fn(),
  useStockResearch: vi.fn(),
  useStrategyLab: vi.fn(),
}));

vi.mock('./MarketContext', () => ({
  useMarket: dependencyMocks.useMarket,
}));

vi.mock('./useAIResearchTask', () => ({
  useAIResearchLLMStatus: dependencyMocks.useAIResearchLLMStatus,
  useAIResearchTask: dependencyMocks.useAIResearchTask,
  useCreateAIResearchTask: dependencyMocks.useCreateAIResearchTask,
}));

vi.mock('./useBacktestResult', () => ({
  useBacktestResult: dependencyMocks.useBacktestResult,
  useCreateBacktestTask: dependencyMocks.useCreateBacktestTask,
}));

vi.mock('./useMarketOverview', () => ({
  useMarketOverview: dependencyMocks.useMarketOverview,
}));

vi.mock('./useMonitorStream', () => ({
  useMonitorStream: dependencyMocks.useMonitorStream,
}));

vi.mock('./usePortfolioSummary', () => ({
  useCreatePaperOrder: dependencyMocks.useCreatePaperOrder,
  usePortfolioSummary: dependencyMocks.usePortfolioSummary,
}));

vi.mock('./usePreTradeRiskCheck', () => ({
  usePreTradeRiskCheck: dependencyMocks.usePreTradeRiskCheck,
}));

vi.mock('./useProviderStatus', () => ({
  useProviderStatus: dependencyMocks.useProviderStatus,
}));

vi.mock('./useStockResearch', () => ({
  useStockResearch: dependencyMocks.useStockResearch,
}));

vi.mock('./useStrategyLab', () => ({
  useCreateStrategyDraft: dependencyMocks.useCreateStrategyDraft,
  useStrategyLab: dependencyMocks.useStrategyLab,
}));

const portfolioResponse: PortfolioResponse = {
  market: 'HK',
  timestamp: '2026-10-16T02:00:00Z',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  data_mode: 'paper',
  account: {
    account_id: 'paper-hk-001',
    market: 'HK',
    currency: 'HKD',
    nav: 100000,
    cash: 25000,
    market_value: 75000,
    daily_pnl: 800,
    total_pnl: 5000,
    total_return: 0.05,
    updated_at: '2026-10-16T02:00:00Z',
  },
  positions: [
    {
      market: 'HK',
      symbol: '00700.HK',
      name: '腾讯控股',
      quantity: 100,
      average_cost: 580,
      last_price: 610,
      market_value: 61000,
      weight: 0.61,
      unrealized_pnl: 3000,
      unrealized_pnl_percent: 0.0517,
    },
  ],
  orders: [],
  risk: {
    gross_exposure: 0.75,
    net_exposure: 0.75,
    largest_position_weight: 0.61,
    cash_weight: 0.25,
    risk_flags: ['单一持仓权重超过 30%'],
  },
};

const buildStockResearch = (
  market: MarketCode,
  symbol: string,
): StockResearchResponse => ({
  profile: {
    market,
    symbol,
    name: symbol,
    asset_type: 'common_stock',
    exchange: market === 'US' ? 'NASDAQ' : market === 'HK' ? 'HKEX' : 'SSE',
    currency: marketSnapshots[market].currency,
    timezone: marketSnapshots[market].timezone,
    sector: 'Technology',
    industry: 'Research Fixture',
  },
  quote: {
    price: 100,
    change: 1,
    change_percent: 0.01,
    volume: 1_000_000,
    turnover: 100_000_000,
    timestamp: '2026-10-19T01:30:00Z',
    data_status: 'delayed',
  },
  valuation: { pe_ttm: 20, pb: 3, ps_ttm: 4, pfcf_ttm: 18 },
  profitability: {
    roe_ttm: 0.18,
    roic_ttm: 0.14,
    gross_margin_ttm: 0.4,
    operating_margin_ttm: 0.2,
  },
  cash_flow: {
    fcf_ttm: 10_000_000,
    operating_cash_flow_ttm: 12_000_000,
    capex_ttm: -2_000_000,
  },
  fundamental_data_status: {
    source: 'database',
    completeness: 'complete',
    available_sections: ['valuation', 'profitability', 'cash_flow'],
    missing_sections: [],
  },
  technical: { rsi_14: 55, macd: 1.2, macd_signal: 1, macd_histogram: 0.2 },
  technical_data_source: {
    source: 'quant_pipeline',
    detail: 'K线计算结果',
    fallback_active: false,
    data_status: 'delayed',
  },
  factor_snapshot: {
    momentum_20d: 0.08,
    trend_strength: 0.7,
    volatility_20d: 0.2,
    quality_score: 0.8,
    composite_score: 0.75,
  },
  quant_signals: [],
  quote_data_source: {
    source: 'yahoo_finance',
    detail: 'YahooFinance 公开行情',
    fallback_active: false,
    data_status: 'delayed',
  },
  kline: { interval: '1d', data_status: 'delayed', bars: [] },
  kline_data_source: {
    source: 'yahoo_finance',
    detail: 'YahooFinance 日线',
    fallback_active: false,
    data_status: 'delayed',
  },
  risk_flags: [],
  summary_points: [`${symbol} 量化摘要`],
  summary_data_source: {
    source: 'quant_pipeline',
    detail: '确定性量化摘要',
    fallback_active: false,
    data_status: 'delayed',
  },
  direction: 'positive',
});

type QueryStub<T = unknown> = {
  data: T | undefined;
  refetch: ReturnType<typeof vi.fn>;
};

const emptyQuery = <T = unknown>(): QueryStub<T> => ({
  data: undefined,
  refetch: vi.fn(),
});
const mutation = () => ({ mutateAsync: vi.fn() });

let portfolioQuery: QueryStub<PortfolioResponse>;
let stockQuery: QueryStub<StockResearchResponse> & {
  isFetching: boolean;
  isError: boolean;
  error: Error | null;
};

beforeEach(() => {
  vi.clearAllMocks();

  dependencyMocks.useMarket.mockReturnValue({
    market: 'HK',
    selectedSymbol: '00700.HK',
    snapshot: marketSnapshots.HK,
  });

  dependencyMocks.useProviderStatus.mockReturnValue(emptyQuery());
  dependencyMocks.useMarketOverview.mockReturnValue(emptyQuery());
  stockQuery = {
    ...emptyQuery<StockResearchResponse>(),
    isFetching: false,
    isError: false,
    error: null,
  };
  dependencyMocks.useStockResearch.mockReturnValue(stockQuery);
  dependencyMocks.useStrategyLab.mockReturnValue(emptyQuery());
  dependencyMocks.useBacktestResult.mockReturnValue(emptyQuery());
  dependencyMocks.useAIResearchLLMStatus.mockReturnValue(emptyQuery());
  dependencyMocks.useAIResearchTask.mockReturnValue(emptyQuery());
  dependencyMocks.useMonitorStream.mockReturnValue(emptyQuery());

  dependencyMocks.useCreateStrategyDraft.mockReturnValue(mutation());
  dependencyMocks.useCreateBacktestTask.mockReturnValue(mutation());
  dependencyMocks.useCreateAIResearchTask.mockReturnValue(mutation());
  dependencyMocks.useCreatePaperOrder.mockReturnValue(mutation());
  dependencyMocks.usePreTradeRiskCheck.mockReturnValue(mutation());

  portfolioQuery = { ...emptyQuery(), data: portfolioResponse };
  dependencyMocks.usePortfolioSummary.mockReturnValue(portfolioQuery);
});

afterEach(() => {
  cleanup();
});

describe('useTerminalPageData portfolio flow', () => {
  it('组合页只启用组合查询并转换为页面模型', () => {
    const { result } = renderHook(() => useTerminalPageData('portfolio'));

    expect(dependencyMocks.usePortfolioSummary).toHaveBeenCalledWith({
      market: 'HK',
      enabled: true,
    });
    expect(dependencyMocks.useMarketOverview).toHaveBeenCalledWith('HK', {
      enabled: false,
    });
    expect(dependencyMocks.useStockResearch).toHaveBeenCalledWith({
      market: 'HK',
      symbol: '00700.HK',
      enabled: false,
    });
    expect(dependencyMocks.useStrategyLab).toHaveBeenCalledWith({
      market: 'HK',
      enabled: false,
    });
    expect(dependencyMocks.useBacktestResult).toHaveBeenCalledWith({
      market: 'HK',
      enabled: false,
    });
    expect(dependencyMocks.useAIResearchLLMStatus).toHaveBeenCalledWith(false);
    expect(dependencyMocks.useAIResearchTask).toHaveBeenCalledWith({
      market: 'HK',
      enabled: false,
    });
    expect(dependencyMocks.useMonitorStream).toHaveBeenCalledWith({
      market: 'HK',
      enabled: false,
    });

    expect(result.current.market).toBe('HK');
    expect(result.current.selectedSymbol).toBe('00700.HK');
    expect(result.current.snapshot).toBe(marketSnapshots.HK);
    expect(result.current.portfolioQuery).toBe(portfolioQuery);
    expect(result.current.portfolio).toMatchObject({
      market: 'HK',
      dataMode: 'paper',
      account: {
        accountId: 'paper-hk-001',
        marketValue: 75000,
      },
      positions: [
        {
          key: 'HK-00700.HK',
          symbol: '00700.HK',
          averageCost: 580,
          unrealizedPnl: 3000,
        },
      ],
      riskFlags: ['单一持仓权重超过 30%'],
    });
  });

  it('组合接口尚未返回时保留查询状态且不构造空组合', () => {
    portfolioQuery = emptyQuery<PortfolioResponse>();
    dependencyMocks.usePortfolioSummary.mockReturnValue(portfolioQuery);

    const { result } = renderHook(() => useTerminalPageData('portfolio'));

    expect(result.current.portfolio).toBeUndefined();
    expect(result.current.portfolioQuery).toBe(portfolioQuery);
  });
});

describe('useTerminalPageData stock research flow', () => {
  it('个股页启用当前市场和标的查询并保留真实适配后的来源与时间', () => {
    stockQuery.data = buildStockResearch('HK', '00700.HK');
    const { result } = renderHook(() => useTerminalPageData('stock-research'));

    expect(dependencyMocks.useStockResearch).toHaveBeenCalledWith({
      market: 'HK',
      symbol: '00700.HK',
      enabled: true,
    });
    expect(dependencyMocks.useMarketOverview).toHaveBeenCalledWith('HK', {
      enabled: false,
    });
    expect(dependencyMocks.usePortfolioSummary).toHaveBeenCalledWith({
      market: 'HK',
      enabled: false,
    });
    expect(result.current.snapshot).toBe(marketSnapshots.HK);
    expect(result.current.stockResearchQuery).toBe(stockQuery);
    expect(result.current.stockResearch).toMatchObject({
      market: 'HK',
      symbol: '00700.HK',
      currency: 'HKD',
      timezone: 'Asia/Hong_Kong',
      dataStatus: 'delayed',
      quote: {
        price: 100,
        changePercent: 0.01,
        timestamp: '2026-10-19T01:30:00Z',
      },
      quoteDataSource: {
        source: 'yahoo_finance',
        fallbackActive: false,
        dataStatus: 'delayed',
      },
      summaryPoints: ['00700.HK 量化摘要'],
    });
  });

  it.each([
    ['HK', '09988.HK'],
    ['CN', '600519.SH'],
  ] as const)('切换到 %s/%s 后加载或失败期间不沿用旧股票快照', (market, symbol) => {
    stockQuery.data = buildStockResearch('HK', '00700.HK');
    const { result, rerender } = renderHook(() =>
      useTerminalPageData('stock-research'),
    );
    expect(result.current.stockResearch?.symbol).toBe('00700.HK');

    dependencyMocks.useMarket.mockReturnValue({
      market,
      selectedSymbol: symbol,
      snapshot: marketSnapshots[market],
    });
    stockQuery = {
      ...emptyQuery<StockResearchResponse>(),
      isFetching: true,
      isError: false,
      error: null,
    };
    dependencyMocks.useStockResearch.mockReturnValue(stockQuery);
    rerender();

    expect(result.current.market).toBe(market);
    expect(result.current.selectedSymbol).toBe(symbol);
    expect(result.current.snapshot).toBe(marketSnapshots[market]);
    expect(result.current.stockResearch).toBeUndefined();
    expect(result.current.stockResearchQuery.isFetching).toBe(true);
    expect(dependencyMocks.useStockResearch).toHaveBeenLastCalledWith({
      market,
      symbol,
      enabled: true,
    });

    const error = new Error('当前标的数据读取失败');
    stockQuery.isFetching = false;
    stockQuery.isError = true;
    stockQuery.error = error;
    rerender();
    expect(result.current.stockResearch).toBeUndefined();
    expect(result.current.stockResearchQuery.isError).toBe(true);
    expect(result.current.stockResearchQuery.error).toBe(error);
    expect(result.current.stockResearchQuery.refetch).toBe(stockQuery.refetch);

    // 保留真实适配器，验证缺失值标记能从响应一路传到页面模型。
    const response = buildStockResearch(market, symbol);
    response.quote.price = 200;
    response.valuation.pe_ttm = null;
    response.profitability.roe_ttm = 0;
    stockQuery.data = response;
    stockQuery.isError = false;
    stockQuery.error = null;
    rerender();

    expect(result.current.stockResearch).toMatchObject({
      market,
      symbol,
      currency: marketSnapshots[market].currency,
      timezone: marketSnapshots[market].timezone,
      quote: { price: 200 },
      summaryPoints: [`${symbol} 量化摘要`],
    });
    const metrics = result.current.stockResearch?.metricGroups.flatMap(
      (group) => group.metrics,
    );
    expect(
      metrics?.find((metric) => metric.labelId === 'terminal.metric.peTtm'),
    ).toMatchObject({
      dataSource: { source: 'database', status: 'unavailable' },
    });
    const roe = metrics?.find(
      (metric) => metric.labelId === 'terminal.metric.roeTtm',
    );
    expect(roe?.value).toBe(0);
    expect(roe?.dataSource?.status).not.toBe('unavailable');
  });

  it('未手动选择股票时保留默认标的请求并展示后端实际返回的股票', () => {
    dependencyMocks.useMarket.mockReturnValue({
      market: 'HK',
      selectedSymbol: undefined,
      snapshot: marketSnapshots.HK,
    });
    stockQuery.data = buildStockResearch('HK', '00700.HK');
    const { result } = renderHook(() => useTerminalPageData('stock-research'));

    expect(dependencyMocks.useStockResearch).toHaveBeenCalledWith({
      market: 'HK',
      symbol: undefined,
      enabled: true,
    });
    expect(result.current.selectedSymbol).toBeUndefined();
    expect(result.current.stockResearch?.symbol).toBe('00700.HK');
    expect(result.current.stockResearch?.market).toBe('HK');
  });

  it('同一股票后台刷新期间保留已有快照和原始数据时间', () => {
    const response = buildStockResearch('HK', '00700.HK');
    stockQuery.data = response;
    const { result, rerender } = renderHook(() =>
      useTerminalPageData('stock-research'),
    );
    const initialSnapshot = result.current.stockResearch;

    stockQuery.isFetching = true;
    rerender();
    expect(result.current.stockResearchQuery.isFetching).toBe(true);
    expect(result.current.stockResearch).toEqual(initialSnapshot);
    expect(result.current.stockResearch?.quote.timestamp).toBe(
      response.quote.timestamp,
    );

    stockQuery.data = {
      ...response,
      quote: {
        ...response.quote,
        price: 105,
        timestamp: '2026-10-19T01:35:00Z',
      },
    };
    stockQuery.isFetching = false;
    rerender();
    expect(result.current.stockResearch?.quote.price).toBe(105);
    expect(result.current.stockResearch?.quote.timestamp).toBe(
      '2026-10-19T01:35:00Z',
    );
    expect(result.current.stockResearchQuery.isFetching).toBe(false);
  });
});

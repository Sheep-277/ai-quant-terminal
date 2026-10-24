import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { createElement, type PropsWithChildren } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { StockResearchResponse } from './apiTypes';
import type { MarketCode } from './types';
import { stockResearchQueryKey, useStockResearch } from './useStockResearch';

const serviceMocks = vi.hoisted(() => ({
  request: vi.fn(),
}));

// 保留真实 Service，只替换 HTTP 边界，连同路径和查询参数一起验证。
vi.mock('@umijs/max', () => serviceMocks);

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
    currency: market === 'US' ? 'USD' : market === 'HK' ? 'HKD' : 'CNY',
    timezone:
      market === 'US'
        ? 'America/New_York'
        : market === 'HK'
          ? 'Asia/Hong_Kong'
          : 'Asia/Shanghai',
    sector: 'Technology',
    industry: 'Research Fixture',
  },
  quote: {
    price: 100,
    change: 1,
    change_percent: 0.01,
    volume: 1_000_000,
    turnover: 100_000_000,
    timestamp: '2026-10-17T01:30:00Z',
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
  technical: {
    rsi_14: 55,
    macd: 1.2,
    macd_signal: 1,
    macd_histogram: 0.2,
  },
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
  kline: {
    interval: '1d',
    data_status: 'delayed',
    bars: [],
  },
  kline_data_source: {
    source: 'yahoo_finance',
    detail: 'YahooFinance 日线',
    fallback_active: false,
    data_status: 'delayed',
  },
  risk_flags: [],
  summary_points: [],
  summary_data_source: {
    source: 'quant_pipeline',
    detail: '确定性量化摘要',
    fallback_active: false,
    data_status: 'delayed',
  },
  direction: 'positive',
});

let queryClient: QueryClient;

const wrapper = ({ children }: PropsWithChildren) =>
  createElement(QueryClientProvider, { client: queryClient }, children);

type StockResearchQueryRuntimeOptions = {
  enabled?: boolean;
  refetchInterval?: number | false;
  staleTime?: number;
};

const getStockResearchQueryOptions = (market: MarketCode, symbol?: string) =>
  queryClient.getQueryCache().find({
    queryKey: stockResearchQueryKey(market, symbol),
  })?.options as StockResearchQueryRuntimeOptions | undefined;

// 手动决定请求完成顺序，稳定复现快速切换股票时的乱序响应。
const createResearchRequest = () => {
  let resolve!: (response: StockResearchResponse) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<StockResearchResponse>(
    (resolvePromise, rejectPromise) => {
      resolve = resolvePromise;
      reject = rejectPromise;
    },
  );
  return { promise, resolve, reject };
};

describe('useStockResearch', () => {
  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    serviceMocks.request.mockReset();
  });

  afterEach(() => {
    cleanup();
    queryClient.clear();
  });

  it('按市场和股票代码生成稳定缓存键', () => {
    expect(stockResearchQueryKey('US', 'AAPL')).toEqual([
      'terminal',
      'stock-research',
      'US',
      'AAPL',
    ]);
    expect(stockResearchQueryKey('HK', '00700.HK')).toEqual([
      'terminal',
      'stock-research',
      'HK',
      '00700.HK',
    ]);
    expect(stockResearchQueryKey('CN')).toEqual([
      'terminal',
      'stock-research',
      'CN',
      'default',
    ]);
  });

  it('按显式标的加载研究快照并允许手动刷新', async () => {
    const response = buildStockResearch('HK', '00700.HK');
    serviceMocks.request.mockResolvedValue(response);
    const { result } = renderHook(
      () => useStockResearch({ market: 'HK', symbol: '00700.HK' }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(response);
    expect(serviceMocks.request).toHaveBeenCalledWith(
      '/api/v1/stock/research',
      {
        method: 'GET',
        params: { market: 'HK', symbol: '00700.HK' },
      },
    );

    await act(async () => {
      await result.current.refetch();
    });
    expect(serviceMocks.request).toHaveBeenCalledTimes(2);
  });

  it('相同代码在不同市场拥有独立请求和缓存', async () => {
    const usResponse = buildStockResearch('US', 'SAME');
    const hkResponse = buildStockResearch('HK', 'SAME');
    hkResponse.quote.price = 200;
    const hkRequest = createResearchRequest();
    serviceMocks.request
      .mockResolvedValueOnce(usResponse)
      .mockReturnValueOnce(hkRequest.promise);
    const { result, rerender } = renderHook(
      ({ market }: { market: MarketCode }) =>
        useStockResearch({ market, symbol: 'SAME' }),
      { initialProps: { market: 'US' as MarketCode }, wrapper },
    );
    await waitFor(() => expect(result.current.data).toEqual(usResponse));
    rerender({ market: 'HK' });
    expect(result.current.data).toBeUndefined();
    expect(serviceMocks.request).toHaveBeenLastCalledWith(
      '/api/v1/stock/research',
      {
        method: 'GET',
        params: { market: 'HK', symbol: 'SAME' },
      },
    );
    await act(async () => hkRequest.resolve(hkResponse));
    await waitFor(() => expect(result.current.data).toEqual(hkResponse));
    expect(
      queryClient.getQueryData(stockResearchQueryKey('US', 'SAME')),
    ).toEqual(usResponse);
    expect(
      queryClient.getQueryData(stockResearchQueryKey('HK', 'SAME')),
    ).toEqual(hkResponse);
  });

  it('默认标的和手选同一股票使用独立缓存，不把空时间填成旧时间', async () => {
    const defaultResponse = buildStockResearch('US', 'NVDA');
    defaultResponse.quote.timestamp = null;
    const explicitResponse = buildStockResearch('US', 'NVDA');
    explicitResponse.quote.price = 125;
    serviceMocks.request
      .mockResolvedValueOnce(defaultResponse)
      .mockResolvedValueOnce(explicitResponse);
    const initialProps: { symbol?: string } = {};
    const { result, rerender } = renderHook(
      ({ symbol }: { symbol?: string }) =>
        useStockResearch({ market: 'US', symbol }),
      { initialProps, wrapper },
    );
    await waitFor(() => expect(result.current.data).toEqual(defaultResponse));
    expect(serviceMocks.request).toHaveBeenLastCalledWith(
      '/api/v1/stock/research',
      {
        method: 'GET',
        params: { market: 'US', symbol: undefined },
      },
    );
    rerender({ symbol: 'NVDA' });
    await waitFor(() => expect(result.current.data).toEqual(explicitResponse));
    rerender({});
    await waitFor(() => expect(result.current.data).toEqual(defaultResponse));
    expect(result.current.data?.quote.timestamp).toBeNull();
    expect(serviceMocks.request).toHaveBeenCalledTimes(2);
    expect(
      queryClient.getQueryData(stockResearchQueryKey('US', 'NVDA')),
    ).toEqual(explicitResponse);
  });

  it('缓存刷新失败保留原报价，恢复后同步更新价格、空时间和回退来源', async () => {
    const previous = buildStockResearch('CN', '600519.SH');
    const recovered = buildStockResearch('CN', '600519.SH');
    recovered.quote.price = 90;
    recovered.quote.timestamp = null;
    recovered.quote.data_status = 'unavailable';
    recovered.quote_data_source = {
      source: 'mock_fallback',
      detail: '报价读取失败后的样例回退',
      fallback_active: true,
      data_status: 'unavailable',
    };
    const recoveryRequest = createResearchRequest();
    const refreshError = new Error('刷新请求失败');
    serviceMocks.request
      .mockResolvedValueOnce(previous)
      .mockRejectedValueOnce(refreshError)
      .mockReturnValueOnce(recoveryRequest.promise);
    const { result } = renderHook(
      () => useStockResearch({ market: 'CN', symbol: '600519.SH' }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    await act(async () => {
      await result.current.refetch();
    });
    await waitFor(() => expect(result.current.isRefetchError).toBe(true));
    expect(result.current.data).toEqual(previous);
    expect(result.current.error).toBe(refreshError);

    let recovery: Promise<unknown>;
    act(() => {
      recovery = result.current.refetch();
    });
    expect(result.current.data).toEqual(previous);
    await act(async () => {
      recoveryRequest.resolve(recovered);
      await recovery;
    });
    await waitFor(() => expect(result.current.data).toEqual(recovered));
    expect(result.current.isSuccess).toBe(true);
    expect(result.current.isRefetchError).toBe(false);
    expect(result.current.error).toBeNull();
    expect(
      queryClient.getQueryData(stockResearchQueryKey('CN', '600519.SH')),
    ).toEqual(recovered);
    expect(serviceMocks.request).toHaveBeenCalledTimes(3);
  });

  it('跨市场新请求失败时不展示旧市场缓存，切回后恢复旧市场独立快照', async () => {
    const previous = buildStockResearch('HK', '00700.HK');
    const currentRequest = createResearchRequest();
    serviceMocks.request
      .mockResolvedValueOnce(previous)
      .mockReturnValueOnce(currentRequest.promise);
    const { result, rerender } = renderHook(
      (params: { market: MarketCode; symbol: string }) =>
        useStockResearch(params),
      { initialProps: { market: 'HK', symbol: '00700.HK' }, wrapper },
    );
    await waitFor(() => expect(result.current.data).toEqual(previous));
    rerender({ market: 'CN', symbol: '600519.SH' });
    expect(result.current.data).toBeUndefined();
    // 与加载界面一样订阅状态字段，避免仅跟踪 data 时漏掉 undefined → error 的通知。
    expect(result.current.isPending).toBe(true);
    expect(result.current.isError).toBe(false);
    const error = new Error('新市场请求失败');
    await act(async () => currentRequest.reject(error));
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBe(error);
    rerender({ market: 'HK', symbol: '00700.HK' });
    await waitFor(() => expect(result.current.data).toEqual(previous));
    expect(result.current.isSuccess).toBe(true);
    expect(result.current.error).toBeNull();
    expect(serviceMocks.request).toHaveBeenCalledTimes(2);
  });

  it('启用时配置十五秒新鲜期和三十秒轮询', async () => {
    serviceMocks.request.mockResolvedValue(buildStockResearch('US', 'AAPL'));
    const { result } = renderHook(
      () => useStockResearch({ market: 'US', symbol: 'AAPL' }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const options = getStockResearchQueryOptions('US', 'AAPL');

    expect(options?.staleTime).toBe(15_000);
    expect(options?.refetchInterval).toBe(30_000);
  });

  it('页面未启用时不请求研究数据并关闭轮询', () => {
    const { result } = renderHook(
      () =>
        useStockResearch({ market: 'CN', symbol: '600519.SH', enabled: false }),
      { wrapper },
    );
    const options = getStockResearchQueryOptions('CN', '600519.SH');

    expect(result.current.fetchStatus).toBe('idle');
    expect(serviceMocks.request).not.toHaveBeenCalled();
    expect(options?.enabled).toBe(false);
    expect(options?.refetchInterval).toBe(false);
  });

  it('切换市场和股票后请求新标的并保留独立缓存', async () => {
    serviceMocks.request.mockImplementation(
      async (
        _url: string,
        {
          params: { market, symbol },
        }: { params: { market: MarketCode; symbol?: string } },
      ) => buildStockResearch(market, symbol ?? 'DEFAULT'),
    );
    const { result, rerender } = renderHook(
      ({ market, symbol }) => useStockResearch({ market, symbol }),
      {
        initialProps: {
          market: 'US' as MarketCode,
          symbol: 'AAPL',
        },
        wrapper,
      },
    );

    await waitFor(() =>
      expect(result.current.data?.profile.symbol).toBe('AAPL'),
    );
    rerender({ market: 'HK', symbol: '00700.HK' });
    await waitFor(() =>
      expect(result.current.data?.profile.symbol).toBe('00700.HK'),
    );

    expect(serviceMocks.request).toHaveBeenNthCalledWith(
      1,
      '/api/v1/stock/research',
      {
        method: 'GET',
        params: { market: 'US', symbol: 'AAPL' },
      },
    );
    expect(serviceMocks.request).toHaveBeenNthCalledWith(
      2,
      '/api/v1/stock/research',
      {
        method: 'GET',
        params: { market: 'HK', symbol: '00700.HK' },
      },
    );
    expect(
      queryClient.getQueryData(stockResearchQueryKey('US', 'AAPL')),
    ).toMatchObject({ profile: { market: 'US', symbol: 'AAPL' } });
    expect(
      queryClient.getQueryData(stockResearchQueryKey('HK', '00700.HK')),
    ).toMatchObject({ profile: { market: 'HK', symbol: '00700.HK' } });
  });

  it.each([
    ['US', 'MSFT'],
    ['HK', '00700.HK'],
  ] as const)('切换到 %s/%s 后旧股票的迟到响应只更新独立缓存', async (market, symbol) => {
    const previousRequest = createResearchRequest();
    const currentRequest = createResearchRequest();
    const previousResponse = buildStockResearch('US', 'AAPL');
    const currentResponse = buildStockResearch(market, symbol);
    serviceMocks.request
      .mockReturnValueOnce(previousRequest.promise)
      .mockReturnValueOnce(currentRequest.promise);

    const { result, rerender } = renderHook(
      (params: { market: MarketCode; symbol: string }) =>
        useStockResearch(params),
      { initialProps: { market: 'US', symbol: 'AAPL' }, wrapper },
    );
    rerender({ market, symbol });

    expect(result.current.data).toBeUndefined();
    expect(result.current.isPending).toBe(true);
    await act(async () => currentRequest.resolve(currentResponse));
    await waitFor(() => expect(result.current.data).toEqual(currentResponse));

    await act(async () => previousRequest.resolve(previousResponse));
    await waitFor(() =>
      expect(
        queryClient.getQueryData(stockResearchQueryKey('US', 'AAPL')),
      ).toEqual(previousResponse),
    );

    expect(result.current.data).toEqual(currentResponse);
    expect(result.current.isSuccess).toBe(true);
    expect(
      queryClient.getQueryData(stockResearchQueryKey(market, symbol)),
    ).toEqual(currentResponse);
    expect(serviceMocks.request).toHaveBeenNthCalledWith(
      2,
      '/api/v1/stock/research',
      {
        method: 'GET',
        params: { market, symbol },
      },
    );

    rerender({ market: 'US', symbol: 'AAPL' });
    await waitFor(() => expect(result.current.data).toEqual(previousResponse));
    expect(serviceMocks.request).toHaveBeenCalledTimes(2);
  });

  it.each([
    [2, 1, 0],
    [0, 1, 2],
  ])('连续切换三个市场后按 %j 顺序返回仍只展示当前请求', async (...order) => {
    // 使用相同代码，验证隔离依赖显式市场，而不是猜测股票代码所属市场。
    const markets: MarketCode[] = ['US', 'HK', 'CN'];
    const requests = markets.map(() => createResearchRequest());
    const responses = markets.map(market => buildStockResearch(market, 'SAME'));
    for (const request of requests) serviceMocks.request.mockReturnValueOnce(request.promise);
    const { result, rerender } = renderHook(
      ({ market }: { market: MarketCode }) => useStockResearch({ market, symbol: 'SAME' }),
      { initialProps: { market: 'US' }, wrapper },
    );
    rerender({ market: 'HK' });
    rerender({ market: 'CN' });
    expect(serviceMocks.request).toHaveBeenCalledTimes(3);

    let currentResolved = false;
    for (const index of order) {
      await act(async () => requests[index].resolve(responses[index]));
      await waitFor(() => expect(
        queryClient.getQueryData(stockResearchQueryKey(markets[index], 'SAME')),
      ).toEqual(responses[index]));
      currentResolved ||= index === 2;
      if (currentResolved) {
        await waitFor(() => expect(result.current.data).toEqual(responses[2]));
        expect(result.current.isSuccess).toBe(true);
      } else {
        expect(result.current.data).toBeUndefined();
        expect(result.current.isPending).toBe(true);
      }
    }
    expect(result.current.data?.profile.market).toBe('CN');
    expect(serviceMocks.request).toHaveBeenCalledTimes(3);
  });

  it('默认请求迟到返回相同股票代码时仍与手选请求保持独立', async () => {
    const defaultRequest = createResearchRequest();
    const selectedRequest = createResearchRequest();
    const selectedResponse = buildStockResearch('US', 'NVDA');
    const defaultResponse = {
      ...buildStockResearch('US', 'NVDA'),
      quote: { ...selectedResponse.quote, price: selectedResponse.quote.price + 1 },
    };
    serviceMocks.request.mockReturnValueOnce(defaultRequest.promise).mockReturnValueOnce(selectedRequest.promise);
    const { result, rerender } = renderHook(
      ({ symbol }: { symbol?: string }) => useStockResearch({ market: 'US', symbol }),
      { initialProps: { symbol: undefined as string | undefined }, wrapper },
    );
    rerender({ symbol: 'NVDA' });
    await act(async () => selectedRequest.resolve(selectedResponse));
    await waitFor(() => expect(result.current.data).toEqual(selectedResponse));
    await act(async () => defaultRequest.resolve(defaultResponse));
    await waitFor(() => expect(queryClient.getQueryData(stockResearchQueryKey('US'))).toEqual(defaultResponse));
    expect(result.current.data).toEqual(selectedResponse);
    expect(queryClient.getQueryData(stockResearchQueryKey('US', 'NVDA'))).toEqual(selectedResponse);

    rerender({ symbol: undefined });
    await waitFor(() => expect(result.current.data).toEqual(defaultResponse));
    expect(serviceMocks.request).toHaveBeenCalledTimes(2);
  });

  it('旧股票请求迟到失败不会污染当前股票的成功状态', async () => {
    const previousRequest = createResearchRequest();
    const currentResponse = buildStockResearch('US', 'MSFT');
    const previousError = new Error('旧股票请求失败');
    serviceMocks.request
      .mockReturnValueOnce(previousRequest.promise)
      .mockResolvedValueOnce(currentResponse);
    const { result, rerender } = renderHook(
      ({ symbol }) => useStockResearch({ market: 'US', symbol }),
      { initialProps: { symbol: 'AAPL' }, wrapper },
    );

    rerender({ symbol: 'MSFT' });
    await waitFor(() => expect(result.current.data).toEqual(currentResponse));
    await act(async () => previousRequest.reject(previousError));
    await waitFor(() =>
      expect(
        queryClient.getQueryState(stockResearchQueryKey('US', 'AAPL'))?.status,
      ).toBe('error'),
    );

    expect(result.current.isSuccess).toBe(true);
    expect(result.current.error).toBeNull();
    expect(result.current.data).toEqual(currentResponse);
  });

  it('当前股票请求失败后旧股票成功返回也不会伪装成当前结果', async () => {
    const previousRequest = createResearchRequest();
    const currentRequest = createResearchRequest();
    const previousResponse = buildStockResearch('US', 'AAPL');
    const currentError = new Error('当前股票数据不可用');
    serviceMocks.request
      .mockReturnValueOnce(previousRequest.promise)
      .mockReturnValueOnce(currentRequest.promise);
    const { result, rerender } = renderHook(
      ({ symbol }) => useStockResearch({ market: 'US', symbol }),
      { initialProps: { symbol: 'AAPL' }, wrapper },
    );

    rerender({ symbol: 'MSFT' });
    await act(async () => currentRequest.reject(currentError));
    await waitFor(() => expect(result.current.isError).toBe(true));
    await act(async () => previousRequest.resolve(previousResponse));
    await waitFor(() =>
      expect(
        queryClient.getQueryData(stockResearchQueryKey('US', 'AAPL')),
      ).toEqual(previousResponse),
    );

    expect(result.current.isError).toBe(true);
    expect(result.current.error).toBe(currentError);
    expect(result.current.data).toBeUndefined();
    expect(
      queryClient.getQueryData(stockResearchQueryKey('US', 'MSFT')),
    ).toBeUndefined();
  });

  it('新股票加载时不借用旧数据，切回缓存股票后迟到响应仍不覆盖当前结果', async () => {
    const previousResponse = buildStockResearch('US', 'AAPL');
    const pendingRequest = createResearchRequest();
    serviceMocks.request
      .mockResolvedValueOnce(previousResponse)
      .mockReturnValueOnce(pendingRequest.promise);
    const { result, rerender } = renderHook(
      ({ symbol }) => useStockResearch({ market: 'US', symbol }),
      { initialProps: { symbol: 'AAPL' }, wrapper },
    );
    await waitFor(() => expect(result.current.data).toEqual(previousResponse));

    rerender({ symbol: 'MSFT' });
    expect(result.current.isPending).toBe(true);
    expect(result.current.data).toBeUndefined();

    rerender({ symbol: 'AAPL' });
    await waitFor(() => expect(result.current.data).toEqual(previousResponse));
    expect(serviceMocks.request).toHaveBeenCalledTimes(2);

    const pendingResponse = buildStockResearch('US', 'MSFT');
    await act(async () => pendingRequest.resolve(pendingResponse));
    await waitFor(() =>
      expect(
        queryClient.getQueryData(stockResearchQueryKey('US', 'MSFT')),
      ).toEqual(pendingResponse),
    );

    expect(result.current.data).toEqual(previousResponse);
    expect(result.current.isSuccess).toBe(true);
    expect(serviceMocks.request).toHaveBeenCalledTimes(2);
  });
});

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { createElement, type PropsWithChildren } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarketOverviewResponse } from './apiTypes';
import type { MarketCode } from './types';
import { marketOverviewQueryKey, useMarketOverview } from './useMarketOverview';

const serviceMocks = vi.hoisted(() => ({
  getMarketOverview: vi.fn(),
}));

vi.mock('@/services/terminal/market', () => serviceMocks);

const marketOverviewResponse: MarketOverviewResponse = {
  market: 'HK',
  timestamp: '2026-10-17T01:30:00Z',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  benchmark: 'Hang Seng Index',
  data_status: 'delayed',
  indices: [],
  breadth: {
    advancers_percent: 0.42,
    decliners_percent: 0.51,
    unchanged_percent: 0.07,
    new_highs: 38,
    new_lows: 54,
    source: 'YahooFinance',
    status: 'delayed',
    timestamp: '2026-10-17T01:29:00Z',
  },
  chart_bars: [],
  sectors: [],
  events: [],
};

let queryClient: QueryClient;

const wrapper = ({ children }: PropsWithChildren) =>
  createElement(QueryClientProvider, { client: queryClient }, children);

type MarketOverviewQueryRuntimeOptions = {
  enabled?: boolean;
  refetchInterval?: number | false;
  staleTime?: number;
};

const getMarketOverviewQueryOptions = (market: MarketCode) =>
  queryClient.getQueryCache().find({
    queryKey: marketOverviewQueryKey(market),
  })?.options as MarketOverviewQueryRuntimeOptions | undefined;

describe('useMarketOverview', () => {
  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    queryClient.clear();
  });

  it('按市场生成稳定且相互隔离的缓存键', () => {
    expect(marketOverviewQueryKey('US')).toEqual([
      'terminal',
      'market-overview',
      'US',
    ]);
    expect(marketOverviewQueryKey('HK')).toEqual([
      'terminal',
      'market-overview',
      'HK',
    ]);
    expect(marketOverviewQueryKey('CN')).toEqual([
      'terminal',
      'market-overview',
      'CN',
    ]);
  });

  it('按显式市场加载总览并允许手动刷新', async () => {
    serviceMocks.getMarketOverview.mockResolvedValue(marketOverviewResponse);
    const { result } = renderHook(() => useMarketOverview('HK'), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(marketOverviewResponse);
    expect(serviceMocks.getMarketOverview).toHaveBeenCalledWith('HK');

    await act(async () => {
      await result.current.refetch();
    });
    expect(serviceMocks.getMarketOverview).toHaveBeenCalledTimes(2);
  });

  it('启用时配置十五秒新鲜期和三十秒轮询', async () => {
    serviceMocks.getMarketOverview.mockResolvedValue(marketOverviewResponse);
    const { result } = renderHook(() => useMarketOverview('HK'), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const options = getMarketOverviewQueryOptions('HK');

    expect(options?.staleTime).toBe(15_000);
    expect(options?.refetchInterval).toBe(30_000);
  });

  it('页面未启用时不请求总览并关闭轮询', () => {
    const { result } = renderHook(
      () => useMarketOverview('CN', { enabled: false }),
      { wrapper },
    );
    const options = getMarketOverviewQueryOptions('CN');

    expect(result.current.fetchStatus).toBe('idle');
    expect(serviceMocks.getMarketOverview).not.toHaveBeenCalled();
    expect(options?.enabled).toBe(false);
    expect(options?.refetchInterval).toBe(false);
  });

  it('切换市场后请求新市场并保留独立缓存', async () => {
    serviceMocks.getMarketOverview.mockImplementation(async (market) => ({
      ...marketOverviewResponse,
      market,
    }));
    const { result, rerender } = renderHook(
      ({ market }) => useMarketOverview(market),
      { initialProps: { market: 'US' as MarketCode }, wrapper },
    );

    await waitFor(() => expect(result.current.data?.market).toBe('US'));
    rerender({ market: 'HK' });
    await waitFor(() => expect(result.current.data?.market).toBe('HK'));

    expect(serviceMocks.getMarketOverview).toHaveBeenNthCalledWith(1, 'US');
    expect(serviceMocks.getMarketOverview).toHaveBeenNthCalledWith(2, 'HK');
    expect(
      queryClient.getQueryData(marketOverviewQueryKey('US')),
    ).toMatchObject({ market: 'US' });
    expect(
      queryClient.getQueryData(marketOverviewQueryKey('HK')),
    ).toMatchObject({ market: 'HK' });
  });
});

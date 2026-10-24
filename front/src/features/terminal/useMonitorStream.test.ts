import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { createElement, type PropsWithChildren } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MonitorResponse } from './apiTypes';
import type { MarketCode } from './types';
import { monitorStreamQueryKey, useMonitorStream } from './useMonitorStream';

const serviceMocks = vi.hoisted(() => ({
  getMonitorStream: vi.fn(),
}));

vi.mock('@/services/terminal/monitor', () => serviceMocks);

const monitorResponse: MonitorResponse = {
  market: 'HK',
  timestamp: '2026-10-16T02:10:00Z',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  stream: {
    status: 'connected',
    latency_ms: 86,
    last_heartbeat_at: '2026-10-16T02:09:58Z',
    reconnect_attempts: 0,
    data_status: 'realtime',
  },
  signals: [],
  events: [],
};

let queryClient: QueryClient;

const wrapper = ({ children }: PropsWithChildren) =>
  createElement(QueryClientProvider, { client: queryClient }, children);

type MonitorQueryRuntimeOptions = {
  enabled?: boolean;
  refetchInterval?: number | false;
  staleTime?: number;
};

const getMonitorQueryOptions = (market: MarketCode) =>
  queryClient.getQueryCache().find({
    queryKey: monitorStreamQueryKey(market),
  })?.options as MonitorQueryRuntimeOptions | undefined;

describe('useMonitorStream', () => {
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
    expect(monitorStreamQueryKey('US')).toEqual(['terminal', 'monitor', 'US']);
    expect(monitorStreamQueryKey('HK')).toEqual(['terminal', 'monitor', 'HK']);
    expect(monitorStreamQueryKey('CN')).toEqual(['terminal', 'monitor', 'CN']);
  });

  it('按显式市场加载监控快照并允许手动刷新', async () => {
    serviceMocks.getMonitorStream.mockResolvedValue(monitorResponse);
    const { result } = renderHook(() => useMonitorStream({ market: 'HK' }), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(monitorResponse);
    expect(serviceMocks.getMonitorStream).toHaveBeenCalledWith({
      market: 'HK',
    });

    await act(async () => {
      await result.current.refetch();
    });
    expect(serviceMocks.getMonitorStream).toHaveBeenCalledTimes(2);
  });

  it('启用时配置五秒新鲜期和十秒轮询', async () => {
    serviceMocks.getMonitorStream.mockResolvedValue(monitorResponse);
    const { result } = renderHook(() => useMonitorStream({ market: 'HK' }), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const options = getMonitorQueryOptions('HK');

    expect(options?.staleTime).toBe(5_000);
    expect(options?.refetchInterval).toBe(10_000);
  });

  it('刷新失败保留旧快照和原始时间，不把历史连接状态更新成当前状态', async () => {
    serviceMocks.getMonitorStream.mockResolvedValueOnce(monitorResponse);
    const { result } = renderHook(() => useMonitorStream({ market: 'HK' }), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const lastSuccessTime = result.current.dataUpdatedAt;
    serviceMocks.getMonitorStream.mockRejectedValueOnce(new Error('poll failed'));

    await act(async () => { await result.current.refetch(); });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toEqual(monitorResponse);
    expect(result.current.data?.timestamp).toBe(monitorResponse.timestamp);
    expect(result.current.data?.stream.last_heartbeat_at).toBe(monitorResponse.stream.last_heartbeat_at);
    expect(result.current.dataUpdatedAt).toBe(lastSuccessTime);
  });

  it('页面未启用时不请求数据并关闭轮询', () => {
    const { result } = renderHook(
      () => useMonitorStream({ market: 'CN', enabled: false }),
      { wrapper },
    );
    const options = getMonitorQueryOptions('CN');

    expect(result.current.fetchStatus).toBe('idle');
    expect(serviceMocks.getMonitorStream).not.toHaveBeenCalled();
    expect(options?.enabled).toBe(false);
    expect(options?.refetchInterval).toBe(false);
  });

  it('切换市场后请求新市场并保留独立缓存', async () => {
    serviceMocks.getMonitorStream.mockImplementation(async ({ market }) => ({
      ...monitorResponse,
      market,
    }));
    const { result, rerender } = renderHook(
      ({ market }) => useMonitorStream({ market }),
      { initialProps: { market: 'US' as MarketCode }, wrapper },
    );

    await waitFor(() => expect(result.current.data?.market).toBe('US'));
    rerender({ market: 'HK' });
    await waitFor(() => expect(result.current.data?.market).toBe('HK'));

    expect(serviceMocks.getMonitorStream).toHaveBeenNthCalledWith(1, {
      market: 'US',
    });
    expect(serviceMocks.getMonitorStream).toHaveBeenNthCalledWith(2, {
      market: 'HK',
    });
    expect(queryClient.getQueryData(monitorStreamQueryKey('US'))).toMatchObject(
      {
        market: 'US',
      },
    );
    expect(queryClient.getQueryData(monitorStreamQueryKey('HK'))).toMatchObject(
      {
        market: 'HK',
      },
    );
  });
});

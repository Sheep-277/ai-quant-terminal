import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { createElement, type PropsWithChildren } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { GetMonitorCalculatedSignalsParams } from '@/services/terminal/monitor';
import type { MonitorCalculatedSignalsResponse } from './apiTypes';
import { monitorCalculatedSignalsQueryKey, useMonitorCalculatedSignals } from './useMonitorCalculatedSignals';

const serviceMocks = vi.hoisted(() => ({ getMonitorCalculatedSignals: vi.fn() }));
vi.mock('@/services/terminal/monitor', () => serviceMocks);

const response: MonitorCalculatedSignalsResponse = {
  market: 'US', symbol: 'NVDA', timezone: 'America/New_York', currency: 'USD',
  source: 'yahoo_finance', data_status: 'delayed', timestamp: '2026-10-20T13:30:00Z',
  bar_count: 65, calculation_scope: 'price_only', signals: [],
};
const initial: GetMonitorCalculatedSignalsParams = { market: 'US', symbol: 'NVDA' };
let client: QueryClient;
const wrapper = ({ children }: PropsWithChildren) => createElement(QueryClientProvider, { client }, children);

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((complete) => { resolve = complete; });
  return { promise, resolve };
}

beforeEach(() => {
  // 即使全局允许重试，新 Hook 也必须维持单次按需请求。
  client = new QueryClient({ defaultOptions: { queries: { retry: 3 } } });
  vi.resetAllMocks();
});
afterEach(() => { cleanup(); client.clear(); });

describe('useMonitorCalculatedSignals', () => {
  it('规范化缓存键并与市场、股票及快照查询隔离', () => {
    expect(monitorCalculatedSignalsQueryKey({ market: 'US', symbol: ' nvda ' })).toEqual([
      'terminal', 'monitor-calculated-signals', 'US', 'NVDA',
    ]);
    expect(monitorCalculatedSignalsQueryKey({ market: 'HK', symbol: 'NVDA' })).not.toEqual(monitorCalculatedSignalsQueryKey(initial));
    expect(monitorCalculatedSignalsQueryKey({ market: 'US', symbol: 'AAPL' })).not.toEqual(monitorCalculatedSignalsQueryKey(initial));
  });

  it('挂载时保持未请求状态，关闭自动请求和重试', () => {
    const { result } = renderHook(() => useMonitorCalculatedSignals(initial), { wrapper });
    expect(result.current.isFetching).toBe(false);
    expect(result.current.data).toBeUndefined();
    expect(serviceMocks.getMonitorCalculatedSignals).not.toHaveBeenCalled();
    expect(client.getQueryCache().find({ queryKey: monitorCalculatedSignalsQueryKey(initial) })?.options).toMatchObject({
      enabled: false, retry: false, refetchInterval: false,
      refetchOnMount: false, refetchOnWindowFocus: false, refetchOnReconnect: false, networkMode: 'always',
    });
  });

  it('仅手动触发请求，透传取消信号并保留行情时间和空结果', async () => {
    const pending = deferred<MonitorCalculatedSignalsResponse>();
    serviceMocks.getMonitorCalculatedSignals.mockReturnValue(pending.promise);
    const { result } = renderHook(() => useMonitorCalculatedSignals({ ...initial, symbol: ' nvda ' }), { wrapper });
    let request!: Promise<unknown>;
    act(() => { request = result.current.refetch(); });
    await waitFor(() => expect(result.current.isFetching).toBe(true));
    expect(serviceMocks.getMonitorCalculatedSignals).toHaveBeenCalledWith(initial, { signal: expect.any(AbortSignal) });
    await act(async () => { pending.resolve(response); await request; });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(response);
    expect(result.current.isFetching).toBe(false);
  });

  it('请求失败直接暴露错误，不重试、不创建模拟结果', async () => {
    const error = new Error('monitor_public_data_unavailable');
    serviceMocks.getMonitorCalculatedSignals.mockRejectedValue(error);
    const { result } = renderHook(() => useMonitorCalculatedSignals(initial), { wrapper });
    await act(async () => { await result.current.refetch(); });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(error);
    expect(result.current.data).toBeUndefined();
    expect(serviceMocks.getMonitorCalculatedSignals).toHaveBeenCalledTimes(1);
  });

  it('空标的手动触发时本地拒绝，不调用服务', async () => {
    const { result } = renderHook(() => useMonitorCalculatedSignals({ ...initial, symbol: ' ' }), { wrapper });
    await act(async () => { await result.current.refetch(); });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe('monitor_symbol_required');
    expect(serviceMocks.getMonitorCalculatedSignals).not.toHaveBeenCalled();
  });

  it('主动取消后晚到的结果不能进入缓存', async () => {
    const pending = deferred<MonitorCalculatedSignalsResponse>();
    serviceMocks.getMonitorCalculatedSignals.mockReturnValue(pending.promise);
    const { result } = renderHook(() => useMonitorCalculatedSignals(initial), { wrapper });
    act(() => { void result.current.refetch(); });
    await waitFor(() => expect(result.current.isFetching).toBe(true));
    const signal = serviceMocks.getMonitorCalculatedSignals.mock.calls[0][1].signal as AbortSignal;
    await act(async () => { await result.current.cancel(); });
    expect(signal.aborted).toBe(true);
    await act(async () => { pending.resolve(response); await pending.promise; });
    expect(result.current.data).toBeUndefined();
    await waitFor(() => expect(result.current.isFetching).toBe(false));
    expect(result.current.isError).toBe(false);
  });

  it.each<GetMonitorCalculatedSignalsParams>([
    { market: 'US', symbol: 'AAPL' },
    { market: 'HK', symbol: '00700.HK' },
  ])('切换到 $market / $symbol 取消旧请求，不自动请求新标的，旧结果不覆盖新结果', async (target) => {
    const old = deferred<MonitorCalculatedSignalsResponse>();
    const next = { ...response, ...target };
    serviceMocks.getMonitorCalculatedSignals.mockReturnValueOnce(old.promise).mockResolvedValueOnce(next);
    const { result, rerender } = renderHook((params: GetMonitorCalculatedSignalsParams) => useMonitorCalculatedSignals(params), { wrapper, initialProps: initial });
    act(() => { void result.current.refetch(); });
    await waitFor(() => expect(result.current.isFetching).toBe(true));
    const signal = serviceMocks.getMonitorCalculatedSignals.mock.calls[0][1].signal as AbortSignal;
    rerender(target);
    expect(signal.aborted).toBe(true);
    expect(result.current.data).toBeUndefined();
    expect(serviceMocks.getMonitorCalculatedSignals).toHaveBeenCalledTimes(1);
    await act(async () => { await result.current.refetch(); });
    await waitFor(() => expect(result.current.data).toEqual(next));
    await act(async () => { old.resolve(response); await old.promise; });
    expect(result.current.data).toEqual(next);
    expect(client.getQueryData(monitorCalculatedSignalsQueryKey(initial))).toBeUndefined();
  });

  it('卸载时取消正在等待的请求', async () => {
    const pending = deferred<MonitorCalculatedSignalsResponse>();
    serviceMocks.getMonitorCalculatedSignals.mockReturnValue(pending.promise);
    const { result, unmount } = renderHook(() => useMonitorCalculatedSignals(initial), { wrapper });
    act(() => { void result.current.refetch(); });
    await waitFor(() => expect(result.current.isFetching).toBe(true));
    const signal = serviceMocks.getMonitorCalculatedSignals.mock.calls[0][1].signal as AbortSignal;
    unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => { pending.resolve(response); await pending.promise; });
    expect(client.getQueryData(monitorCalculatedSignalsQueryKey(initial))).toBeUndefined();
  });

  it('同一标的刷新失败时保留原结果和时间，同时暴露错误', async () => {
    const error = new Error('timeout');
    serviceMocks.getMonitorCalculatedSignals.mockResolvedValueOnce(response).mockRejectedValueOnce(error);
    const { result } = renderHook(() => useMonitorCalculatedSignals(initial), { wrapper });
    await act(async () => { await result.current.refetch(); });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    await act(async () => { await result.current.refetch(); });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toEqual(response);
    expect(result.current.data?.timestamp).toBe(response.timestamp);
    expect(result.current.error).toBe(error);
  });
});

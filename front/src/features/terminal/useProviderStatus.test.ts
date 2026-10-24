import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { createElement, type PropsWithChildren } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  ProviderStatusLogListResponse,
  ProviderStatusResponse,
} from './apiTypes';
import {
  providerStatusLogsQueryKey,
  providerStatusQueryKey,
  useProviderStatus,
  useProviderStatusLogs,
} from './useProviderStatus';

const serviceMocks = vi.hoisted(() => ({
  getProviderStatus: vi.fn(),
  getProviderStatusLogs: vi.fn(),
}));

vi.mock('@/services/terminal/provider', () => serviceMocks);

const providerStatusResponse: ProviderStatusResponse = {
  provider_name: 'YahooFinance',
  mode: 'real',
  ready: true,
  data_status: 'delayed',
  fallback_active: false,
  fallback_reason: null,
  active_source: 'yahoo_finance',
};

const providerStatusLogsResponse: ProviderStatusLogListResponse = {
  items: [
    {
      id: 1,
      provider_name: 'YahooFinance',
      mode: 'real',
      ready: true,
      data_status: 'delayed',
      fallback_active: false,
      fallback_reason: null,
      checked_at: '2026-10-17T02:00:00Z',
    },
  ],
  total: 1,
  database_available: true,
  fallback_reason: null,
};

let queryClient: QueryClient;

const wrapper = ({ children }: PropsWithChildren) =>
  createElement(QueryClientProvider, { client: queryClient }, children);

type ProviderQueryRuntimeOptions = {
  enabled?: boolean;
  refetchInterval?: number | false;
  staleTime?: number;
};

const getProviderQueryOptions = (queryKey: readonly unknown[]) =>
  queryClient.getQueryCache().find({ queryKey })?.options as
    | ProviderQueryRuntimeOptions
    | undefined;

describe('useProviderStatus', () => {
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

  it('为当前状态和不同日志筛选生成稳定缓存键', () => {
    expect(providerStatusQueryKey).toEqual(['terminal', 'provider-status']);
    expect(providerStatusLogsQueryKey(20)).toEqual([
      'terminal',
      'provider-status-logs',
      20,
      'all',
    ]);
    expect(providerStatusLogsQueryKey(50, 'YahooFinance')).toEqual([
      'terminal',
      'provider-status-logs',
      50,
      'YahooFinance',
    ]);
  });

  it('加载当前 Provider 状态并允许手动刷新', async () => {
    serviceMocks.getProviderStatus.mockResolvedValue(providerStatusResponse);
    const { result } = renderHook(() => useProviderStatus(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(providerStatusResponse);
    expect(serviceMocks.getProviderStatus).toHaveBeenCalledTimes(1);

    await act(async () => {
      await result.current.refetch();
    });
    expect(serviceMocks.getProviderStatus).toHaveBeenCalledTimes(2);
  });

  it('当前状态使用十五秒新鲜期和三十秒轮询', async () => {
    serviceMocks.getProviderStatus.mockResolvedValue(providerStatusResponse);
    const { result } = renderHook(() => useProviderStatus(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const options = getProviderQueryOptions(providerStatusQueryKey);

    expect(options?.staleTime).toBe(15_000);
    expect(options?.refetchInterval).toBe(30_000);
  });

  it('日志弹窗关闭时不发送请求', () => {
    const { result } = renderHook(
      () => useProviderStatusLogs({ enabled: false }),
      { wrapper },
    );
    const options = getProviderQueryOptions(providerStatusLogsQueryKey(20));

    expect(result.current.fetchStatus).toBe('idle');
    expect(serviceMocks.getProviderStatusLogs).not.toHaveBeenCalled();
    expect(options?.enabled).toBe(false);
  });

  it('日志弹窗打开时使用默认条数和十秒新鲜期', async () => {
    serviceMocks.getProviderStatusLogs.mockResolvedValue(
      providerStatusLogsResponse,
    );
    const { result } = renderHook(
      () => useProviderStatusLogs({ enabled: true }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(providerStatusLogsResponse);
    expect(serviceMocks.getProviderStatusLogs).toHaveBeenCalledWith({
      limit: 20,
      providerName: undefined,
    });
    expect(
      getProviderQueryOptions(providerStatusLogsQueryKey(20))?.staleTime,
    ).toBe(10_000);
  });

  it('切换 Provider 筛选后请求新日志并保留独立缓存', async () => {
    serviceMocks.getProviderStatusLogs.mockImplementation(
      async ({ providerName }) => ({
        ...providerStatusLogsResponse,
        items: providerStatusLogsResponse.items.map((item) => ({
          ...item,
          provider_name: providerName ?? 'AllProvider',
        })),
      }),
    );
    const { result, rerender } = renderHook(
      ({ providerName }) =>
        useProviderStatusLogs({ enabled: true, limit: 20, providerName }),
      {
        initialProps: { providerName: undefined as string | undefined },
        wrapper,
      },
    );

    await waitFor(() =>
      expect(result.current.data?.items[0].provider_name).toBe('AllProvider'),
    );
    rerender({ providerName: 'YahooFinance' });
    await waitFor(() =>
      expect(result.current.data?.items[0].provider_name).toBe('YahooFinance'),
    );

    expect(serviceMocks.getProviderStatusLogs).toHaveBeenNthCalledWith(1, {
      limit: 20,
      providerName: undefined,
    });
    expect(serviceMocks.getProviderStatusLogs).toHaveBeenNthCalledWith(2, {
      limit: 20,
      providerName: 'YahooFinance',
    });
    expect(
      queryClient.getQueryData(providerStatusLogsQueryKey(20)),
    ).toMatchObject({ items: [{ provider_name: 'AllProvider' }] });
    expect(
      queryClient.getQueryData(providerStatusLogsQueryKey(20, 'YahooFinance')),
    ).toMatchObject({ items: [{ provider_name: 'YahooFinance' }] });
  });
});

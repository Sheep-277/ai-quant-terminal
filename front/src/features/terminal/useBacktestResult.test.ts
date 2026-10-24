import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { createElement, type PropsWithChildren } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  BacktestRequest,
  BacktestResponse,
  BacktestTaskCreateResponse,
} from './apiTypes';
import {
  backtestByIdQueryKey,
  backtestByPollUrlQueryKey,
  backtestResultQueryKey,
  backtestTaskCreateMutationKey,
  useBacktestById,
  useBacktestByPollUrl,
  useBacktestResult,
  useCreateBacktestTask,
} from './useBacktestResult';

const serviceMocks = vi.hoisted(() => ({
  createBacktestTask: vi.fn(),
  getBacktestById: vi.fn(),
  getBacktestByPollUrl: vi.fn(),
  getBacktestResult: vi.fn(),
}));

vi.mock('@/services/terminal/backtest', () => serviceMocks);

const backtestResponse: BacktestResponse = {
  backtest_id: 'backtest-hk-001',
  strategy_id: 'strategy-hk-quality-001',
  market: 'HK',
  status: 'completed',
  data_mode: 'historical',
  timestamp: '2026-10-16T02:00:00Z',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  benchmark: 'Hang Seng TECH',
  start_date: '2025-01-01',
  end_date: '2025-12-31',
  performance: {
    initial_capital: 500_000,
    final_value: 560_000,
    total_return: 0.12,
    annualized_return: 0.12,
    benchmark_return: 0.08,
    maximum_drawdown: 0.09,
    sharpe_ratio: 1.35,
    win_rate: 0.58,
    trade_count: 24,
  },
  equity_curve: [],
  trades: [],
  assumptions: ['已计入交易费用与滑点'],
};

const backtestPayload: BacktestRequest = {
  market: 'HK',
  strategy_id: 'strategy-hk-quality-001',
  strategy_status: 'confirmed',
  data_mode: 'historical',
  start_date: '2025-01-01',
  end_date: '2025-12-31',
  sample_split_at: null,
  initial_capital: 500_000,
  benchmark: 'Hang Seng TECH',
  transaction_fee_rate: 0.0005,
  slippage_rate: 0.0005,
};

const taskResponse: BacktestTaskCreateResponse = {
  backtest_id: 'backtest-hk-001',
  strategy_id: 'strategy-hk-quality-001',
  market: 'HK',
  status: 'pending',
  accepted_at: '2026-10-16T02:00:00Z',
  data_mode: 'historical',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  poll_url: '/api/v1/backtests/backtest-hk-001',
  data_status: 'delayed',
  fallback_active: false,
  fallback_reason: null,
  storage_source: 'database',
  result_data_mode: null,
};

let queryClient: QueryClient;

const wrapper = ({ children }: PropsWithChildren) =>
  createElement(QueryClientProvider, { client: queryClient }, children);

describe('useBacktestResult', () => {
  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        mutations: { retry: false },
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    queryClient.clear();
  });

  it('为市场结果、任务详情、轮询地址和任务创建生成稳定缓存键', () => {
    expect(backtestResultQueryKey('HK')).toEqual([
      'terminal',
      'backtest',
      'HK',
    ]);
    expect(backtestByIdQueryKey('backtest-hk-001')).toEqual([
      'terminal',
      'backtest',
      'task',
      'backtest-hk-001',
    ]);
    expect(backtestByPollUrlQueryKey('/api/v1/backtests/backtest-hk-001')).toEqual([
      'terminal',
      'backtest',
      'poll',
      '/api/v1/backtests/backtest-hk-001',
    ]);
    expect(backtestTaskCreateMutationKey).toEqual([
      'terminal',
      'backtest',
      'create',
    ]);
  });

  it('按市场加载回测结果并允许手动刷新', async () => {
    serviceMocks.getBacktestResult.mockResolvedValue(backtestResponse);
    const { result } = renderHook(() => useBacktestResult({ market: 'HK' }), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(backtestResponse);
    expect(serviceMocks.getBacktestResult).toHaveBeenCalledWith({ market: 'HK' });

    await act(async () => {
      await result.current.refetch();
    });
    expect(serviceMocks.getBacktestResult).toHaveBeenCalledTimes(2);
  });

  it('页面未启用时不请求市场级回测结果', () => {
    const { result } = renderHook(
      () => useBacktestResult({ market: 'CN', enabled: false }),
      { wrapper },
    );

    expect(result.current.fetchStatus).toBe('idle');
    expect(serviceMocks.getBacktestResult).not.toHaveBeenCalled();
  });

  it('回测任务 ID 有效后才请求任务结果', async () => {
    serviceMocks.getBacktestById.mockResolvedValue(backtestResponse);
    const { result, rerender } = renderHook(
      ({ backtestId }) => useBacktestById({ backtestId }),
      { initialProps: { backtestId: '' }, wrapper },
    );

    expect(result.current.fetchStatus).toBe('idle');
    expect(serviceMocks.getBacktestById).not.toHaveBeenCalled();

    rerender({ backtestId: 'backtest-hk-001' });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(serviceMocks.getBacktestById).toHaveBeenCalledWith({
      backtestId: 'backtest-hk-001',
    });
  });

  it('轮询地址有效后才通过回执地址请求结果', async () => {
    const pollUrl = '/api/v1/backtests/backtest-hk-001';
    serviceMocks.getBacktestByPollUrl.mockResolvedValue(backtestResponse);
    const { result, rerender } = renderHook(
      ({ currentPollUrl }) =>
        useBacktestByPollUrl({ pollUrl: currentPollUrl }),
      { initialProps: { currentPollUrl: '' }, wrapper },
    );

    expect(result.current.fetchStatus).toBe('idle');
    expect(serviceMocks.getBacktestByPollUrl).not.toHaveBeenCalled();

    rerender({ currentPollUrl: pollUrl });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(serviceMocks.getBacktestByPollUrl).toHaveBeenCalledWith({ pollUrl });
  });

  it('将回测任务参数原样交给 backtest service', async () => {
    serviceMocks.createBacktestTask.mockResolvedValue(taskResponse);
    const { result } = renderHook(() => useCreateBacktestTask(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync(backtestPayload);
    });

    expect(serviceMocks.createBacktestTask).toHaveBeenCalledWith(backtestPayload);
    await waitFor(() => expect(result.current.data).toEqual(taskResponse));
  });
});

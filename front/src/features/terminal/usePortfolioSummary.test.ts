import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { createElement, type PropsWithChildren } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  PaperOrderCreateResponse,
  PaperOrderRequest,
  PortfolioResponse,
} from './apiTypes';
import {
  createPaperOrderMutationKey,
  portfolioAccountSummaryQueryKey,
  portfolioSummaryQueryKey,
  useCreatePaperOrder,
  usePortfolioAccountSummary,
  usePortfolioSummary,
} from './usePortfolioSummary';

const serviceMocks = vi.hoisted(() => ({
  createPaperOrder: vi.fn(),
  getPortfolioAccountSummary: vi.fn(),
  getPortfolioSummary: vi.fn(),
}));

vi.mock('@/services/terminal/portfolio', () => serviceMocks);

const portfolioResponse: PortfolioResponse = {
  market: 'HK',
  timestamp: '2026-10-15T02:00:00Z',
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
    updated_at: '2026-10-15T02:00:00Z',
  },
  positions: [],
  orders: [],
  risk: {
    gross_exposure: 0.75,
    net_exposure: 0.75,
    largest_position_weight: 0.4,
    cash_weight: 0.25,
    risk_flags: [],
  },
};

const paperOrderPayload: PaperOrderRequest = {
  account_id: 'paper-hk-001',
  market: 'HK',
  symbol: '00700.HK',
  side: 'buy',
  quantity: 100,
  limit_price: 610,
  paper_trading: true,
};

const paperOrderResponse: PaperOrderCreateResponse = {
  order_id: 'paper-order-001',
  account_id: 'paper-hk-001',
  market: 'HK',
  symbol: '00700.HK',
  side: 'buy',
  quantity: 100,
  limit_price: 610,
  status: 'submitted',
  submitted_at: '2026-10-15T02:00:00Z',
  currency: 'HKD',
  risk_checked: true,
  risk_decision: 'approved',
  risk_reason_codes: [],
  risk_reasons: [],
  data_status: 'delayed',
  fallback_active: false,
  fallback_reason: null,
  storage_source: 'database',
};

let queryClient: QueryClient;

const wrapper = ({ children }: PropsWithChildren) =>
  createElement(QueryClientProvider, { client: queryClient }, children);

describe('usePortfolioSummary', () => {
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

  it('为市场、账户和模拟订单生成稳定缓存键', () => {
    expect(portfolioSummaryQueryKey('HK')).toEqual(['terminal', 'portfolio', 'HK']);
    expect(portfolioAccountSummaryQueryKey('paper-hk-001')).toEqual([
      'terminal',
      'portfolio',
      'account',
      'paper-hk-001',
    ]);
    expect(createPaperOrderMutationKey).toEqual(['terminal', 'portfolio', 'paper-order']);
  });

  it('按市场加载组合摘要并允许手动刷新', async () => {
    serviceMocks.getPortfolioSummary.mockResolvedValue(portfolioResponse);
    const { result } = renderHook(() => usePortfolioSummary({ market: 'HK' }), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(portfolioResponse);
    expect(serviceMocks.getPortfolioSummary).toHaveBeenCalledWith({ market: 'HK' });

    await act(async () => {
      await result.current.refetch();
    });
    expect(serviceMocks.getPortfolioSummary).toHaveBeenCalledTimes(2);
  });

  it('页面未启用时不请求市场级组合摘要', () => {
    const { result } = renderHook(
      () => usePortfolioSummary({ market: 'CN', enabled: false }),
      { wrapper },
    );

    expect(result.current.fetchStatus).toBe('idle');
    expect(serviceMocks.getPortfolioSummary).not.toHaveBeenCalled();
  });

  it('账户 ID 有效后才加载账户级组合摘要', async () => {
    serviceMocks.getPortfolioAccountSummary.mockResolvedValue(portfolioResponse);
    const { result, rerender } = renderHook(
      ({ accountId }) => usePortfolioAccountSummary({ accountId }),
      { initialProps: { accountId: '   ' }, wrapper },
    );

    expect(result.current.fetchStatus).toBe('idle');
    expect(serviceMocks.getPortfolioAccountSummary).not.toHaveBeenCalled();

    rerender({ accountId: 'paper-hk-001' });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(serviceMocks.getPortfolioAccountSummary).toHaveBeenCalledWith({
      accountId: 'paper-hk-001',
    });
  });

  it('将模拟订单参数原样交给 portfolio service', async () => {
    serviceMocks.createPaperOrder.mockResolvedValue(paperOrderResponse);
    const { result } = renderHook(() => useCreatePaperOrder(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync(paperOrderPayload);
    });

    expect(serviceMocks.createPaperOrder).toHaveBeenCalledWith(paperOrderPayload);
    await waitFor(() => expect(result.current.data).toEqual(paperOrderResponse));
  });
});

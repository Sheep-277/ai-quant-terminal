import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { createElement, type PropsWithChildren } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  PreTradeRiskCheckRequest,
  PreTradeRiskCheckResponse,
} from './apiTypes';
import {
  preTradeRiskCheckMutationKey,
  usePreTradeRiskCheck,
} from './usePreTradeRiskCheck';

const serviceMocks = vi.hoisted(() => ({
  preTradeRiskCheck: vi.fn(),
}));

vi.mock('@/services/terminal/risk', () => serviceMocks);

const riskCheckPayload: PreTradeRiskCheckRequest = {
  account_id: 'paper-hk-001',
  market: 'HK',
  symbol: '00700.HK',
  side: 'buy',
  quantity: 100,
  limit_price: 610,
  nav: 100_000,
  cash: 25_000,
  current_positions: [
    {
      market: 'HK',
      symbol: '00700.HK',
      market_value: 60_000,
      side: 'long',
    },
  ],
  max_position_weight: 0.3,
  min_cash_weight: 0.05,
  paper_trading: true,
};

const approvedResponse: PreTradeRiskCheckResponse = {
  account_id: 'paper-hk-001',
  market: 'HK',
  symbol: '00700.HK',
  side: 'buy',
  decision: 'approved',
  risk_checked: true,
  checked_at: '2026-10-17T02:00:00Z',
  projected_order_value: 61_000,
  projected_cash: 19_000,
  projected_cash_weight: 0.19,
  projected_position_weight: 0.28,
  reasons: [],
};

let queryClient: QueryClient;

const wrapper = ({ children }: PropsWithChildren) =>
  createElement(QueryClientProvider, { client: queryClient }, children);

describe('usePreTradeRiskCheck', () => {
  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        mutations: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    queryClient.clear();
  });

  it('生成稳定的下单前风险检查 Mutation 键', () => {
    expect(preTradeRiskCheckMutationKey).toEqual([
      'terminal',
      'risk',
      'pre-trade-check',
    ]);
  });

  it('将完整风险检查载荷原样交给 Risk Service', async () => {
    serviceMocks.preTradeRiskCheck.mockResolvedValue(approvedResponse);
    const { result } = renderHook(() => usePreTradeRiskCheck(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync(riskCheckPayload);
    });

    expect(serviceMocks.preTradeRiskCheck).toHaveBeenCalledWith(
      riskCheckPayload,
    );
    await waitFor(() => expect(result.current.data).toEqual(approvedResponse));
    expect(result.current.isSuccess).toBe(true);
  });

  it('将风险拒绝保留为成功返回的业务结论', async () => {
    const rejectedResponse: PreTradeRiskCheckResponse = {
      ...approvedResponse,
      decision: 'rejected',
      reasons: [
        {
          code: 'POSITION_WEIGHT_LIMIT',
          message: '预计持仓权重超过限制',
          severity: 'critical',
        },
      ],
    };
    serviceMocks.preTradeRiskCheck.mockResolvedValue(rejectedResponse);
    const { result } = renderHook(() => usePreTradeRiskCheck(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync(riskCheckPayload);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.isError).toBe(false);
    expect(result.current.data).toEqual(rejectedResponse);
  });

  it('Risk Service 异常时进入错误状态并保留原始错误', async () => {
    const requestError = new Error('pre-trade risk check unavailable');
    serviceMocks.preTradeRiskCheck.mockRejectedValue(requestError);
    const { result } = renderHook(() => usePreTradeRiskCheck(), { wrapper });

    await act(async () => {
      await expect(result.current.mutateAsync(riskCheckPayload)).rejects.toBe(
        requestError,
      );
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(requestError);
    expect(result.current.data).toBeUndefined();
  });
});

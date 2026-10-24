import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { createElement, type PropsWithChildren } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  StrategyDraftCreateRequest,
  StrategyDraftDto,
  StrategyLabResponse,
  StrategyNaturalLanguageParseRequest,
  StrategyNaturalLanguageParseResponse,
} from './apiTypes';
import {
  strategyDraftCreateMutationKey,
  strategyLabQueryKey,
  strategyNaturalLanguageParseMutationKey,
  useCreateStrategyDraft,
  useParseStrategyNaturalLanguage,
  useStrategyLab,
} from './useStrategyLab';

const serviceMocks = vi.hoisted(() => ({
  createStrategyDraft: vi.fn(),
  getStrategyLab: vi.fn(),
  parseStrategyNaturalLanguage: vi.fn(),
}));

vi.mock('@/services/terminal/strategy', () => serviceMocks);

const universe = {
  market: 'HK' as const,
  universe_type: 'index' as const,
  name: 'Hang Seng TECH',
  symbols: ['00700.HK', '09988.HK'],
};

const entryCondition = {
  field: 'momentum_20d' as const,
  operator: 'between' as const,
  value: 0.02,
  upper_value: 0.16,
  description: '20 日动量介于 2% 到 16%',
};

const exitCondition = {
  field: 'rsi_14' as const,
  operator: 'gt' as const,
  value: 78,
  upper_value: null,
  description: 'RSI 明显过热时退出',
};

const riskConstraint = {
  max_drawdown: 0.16,
  stop_loss: 0.07,
  min_liquidity: 30_000_000,
};

const draftPayload: StrategyDraftCreateRequest = {
  market: 'HK',
  name: 'HK Quality Momentum',
  description: '港股质量与动量策略',
  universe,
  entry_conditions: [entryCondition],
  exit_conditions: [exitCondition],
  position_rule: {
    max_holdings: 8,
    max_position_weight: 0.15,
    equal_weight: true,
  },
  rebalance_frequency: 'monthly',
  risk_constraints: [riskConstraint],
  created_by: 'user',
};

const draftResponse: StrategyDraftDto = {
  strategy_id: 'strategy-hk-quality-001',
  version: 1,
  status: 'draft',
  created_at: '2026-10-16T02:00:00Z',
  updated_at: '2026-10-16T02:00:00Z',
  parameters: {
    fallback_active: false,
  },
  ...draftPayload,
};

const strategyLabResponse: StrategyLabResponse = {
  market: 'HK',
  timestamp: '2026-10-16T02:00:00Z',
  default_universe: universe,
  drafts: [draftResponse],
};

const parsePayload: StrategyNaturalLanguageParseRequest = {
  market: 'HK',
  text: '选择 20 日动量大于 2% 的股票，RSI 超过 78 时退出',
  universe,
  preferred_source: 'hybrid',
  require_user_confirmation: true,
};

const parseResponse: StrategyNaturalLanguageParseResponse = {
  market: 'HK',
  source: 'hybrid',
  confidence: 0.91,
  requires_user_confirmation: true,
  parsed_at: '2026-10-16T02:01:00Z',
  raw_text: parsePayload.text,
  result: {
    entry_conditions: [entryCondition],
    exit_conditions: [exitCondition],
    risk_constraints: [riskConstraint],
    warnings: [],
  },
};

let queryClient: QueryClient;

const wrapper = ({ children }: PropsWithChildren) =>
  createElement(QueryClientProvider, { client: queryClient }, children);

describe('useStrategyLab', () => {
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

  it('为市场查询、草案创建和自然语言解析生成稳定缓存键', () => {
    expect(strategyLabQueryKey('HK')).toEqual(['terminal', 'strategy-lab', 'HK']);
    expect(strategyDraftCreateMutationKey).toEqual([
      'terminal',
      'strategy-lab',
      'create',
    ]);
    expect(strategyNaturalLanguageParseMutationKey).toEqual([
      'terminal',
      'strategy-lab',
      'parse-natural-language',
    ]);
  });

  it('按市场加载策略实验室数据并允许手动刷新', async () => {
    serviceMocks.getStrategyLab.mockResolvedValue(strategyLabResponse);
    const { result } = renderHook(() => useStrategyLab({ market: 'HK' }), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(strategyLabResponse);
    expect(serviceMocks.getStrategyLab).toHaveBeenCalledWith({ market: 'HK' });

    await act(async () => {
      await result.current.refetch();
    });
    expect(serviceMocks.getStrategyLab).toHaveBeenCalledTimes(2);
  });

  it('页面未启用时不请求策略实验室数据', () => {
    const { result } = renderHook(
      () => useStrategyLab({ market: 'CN', enabled: false }),
      { wrapper },
    );

    expect(result.current.fetchStatus).toBe('idle');
    expect(serviceMocks.getStrategyLab).not.toHaveBeenCalled();
  });

  it('将用户确认的策略草案原样交给 strategy service', async () => {
    serviceMocks.createStrategyDraft.mockResolvedValue(draftResponse);
    const { result } = renderHook(() => useCreateStrategyDraft(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync(draftPayload);
    });

    expect(serviceMocks.createStrategyDraft).toHaveBeenCalledWith(draftPayload);
    await waitFor(() => expect(result.current.data).toEqual(draftResponse));
  });

  it('将自然语言解析参数原样交给 strategy service', async () => {
    serviceMocks.parseStrategyNaturalLanguage.mockResolvedValue(parseResponse);
    const { result } = renderHook(() => useParseStrategyNaturalLanguage(), {
      wrapper,
    });

    await act(async () => {
      await result.current.mutateAsync(parsePayload);
    });

    expect(serviceMocks.parseStrategyNaturalLanguage).toHaveBeenCalledWith(
      parsePayload,
    );
    await waitFor(() => expect(result.current.data).toEqual(parseResponse));
  });
});

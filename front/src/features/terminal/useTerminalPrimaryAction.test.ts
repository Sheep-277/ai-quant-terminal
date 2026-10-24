import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook } from '@testing-library/react';
import { createElement, type PropsWithChildren } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import zhCN from '../../locales/zh-CN/terminal';
import type {
  PaperOrderCreateResponse,
  PortfolioResponse,
  PreTradeRiskCheckResponse,
} from './apiTypes';
import type { PortfolioSnapshot } from './types';
import { portfolioAccountSummaryQueryKey, portfolioSummaryQueryKey } from './usePortfolioSummary';
import { useTerminalPrimaryAction } from './useTerminalPrimaryAction';

const dependencyMocks = vi.hoisted(() => ({
  getPortfolioAccountSummary: vi.fn(),
  message: {
    error: vi.fn(),
    info: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}));

vi.mock('@/services/terminal/portfolio', () => ({
  getPortfolioAccountSummary: dependencyMocks.getPortfolioAccountSummary,
}));

vi.mock('antd', () => ({
  App: {
    useApp: () => ({ message: dependencyMocks.message }),
  },
}));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: 'zh-CN',
    formatMessage: (
      { id, defaultMessage }: { id?: string; defaultMessage?: string },
      values?: Record<string, string | number>,
    ) => {
      let message =
        (id && zhCN[id as keyof typeof zhCN]) || defaultMessage || id || '';
      for (const [key, value] of Object.entries(values ?? {})) {
        message = message.replace(`{${key}}`, String(value));
      }
      return message;
    },
  }),
}));

const portfolio: PortfolioSnapshot = {
  market: 'HK',
  timestamp: '2026-10-16T02:00:00Z',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  dataMode: 'paper',
  account: {
    accountId: 'paper-hk-001',
    market: 'HK',
    currency: 'HKD',
    nav: 100000,
    cash: 25000,
    marketValue: 75000,
    dailyPnl: 800,
    totalPnl: 5000,
    totalReturn: 0.05,
    updatedAt: '2026-10-16T02:00:00Z',
  },
  accountMetrics: [],
  positions: [
    {
      key: 'position-00700',
      market: 'HK',
      symbol: '00700.HK',
      name: '腾讯控股',
      quantity: 100,
      averageCost: 580,
      lastPrice: 610,
      marketValue: 61000,
      weight: 0.61,
      unrealizedPnl: 3000,
      unrealizedPnlPercent: 0.0517,
    },
  ],
  orders: [],
  riskMetrics: [],
  riskFlags: [],
};

const accountSummary: PortfolioResponse = {
  market: 'HK',
  timestamp: '2026-10-16T02:01:00Z',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  data_mode: 'paper',
  account: {
    account_id: 'paper-hk-001',
    market: 'HK',
    currency: 'HKD',
    nav: 100000,
    cash: 24390,
    market_value: 75610,
    daily_pnl: 800,
    total_pnl: 5000,
    total_return: 0.05,
    updated_at: '2026-10-16T02:01:00Z',
  },
  positions: [],
  orders: [],
  risk: {
    gross_exposure: 0.7561,
    net_exposure: 0.7561,
    largest_position_weight: 0.6161,
    cash_weight: 0.2439,
    risk_flags: [],
  },
};

const createRiskResponse = (
  decision: PreTradeRiskCheckResponse['decision'],
  message?: string,
): PreTradeRiskCheckResponse => ({
  account_id: 'paper-hk-001',
  market: 'HK',
  symbol: '00700.HK',
  side: 'buy',
  decision,
  risk_checked: true,
  checked_at: '2026-10-16T02:00:00Z',
  projected_order_value: 610,
  projected_cash: 24390,
  projected_cash_weight: 0.2439,
  projected_position_weight: 0.6161,
  reasons: message
    ? [{ code: 'POSITION_LIMIT', message, severity: 'warning' }]
    : [],
});

const createOrderResponse = (
  fallbackActive = false,
): PaperOrderCreateResponse => ({
  order_id: 'paper-order-001',
  account_id: 'paper-hk-001',
  market: 'HK',
  symbol: '00700.HK',
  side: 'buy',
  quantity: 1,
  limit_price: 610,
  status: 'submitted',
  submitted_at: '2026-10-16T02:00:00Z',
  currency: 'HKD',
  risk_checked: true,
  risk_decision: 'approved',
  risk_reason_codes: [],
  risk_reasons: [],
  data_status: fallbackActive ? 'unavailable' : 'delayed',
  fallback_active: fallbackActive,
  fallback_reason: fallbackActive ? 'database unavailable' : null,
  storage_source: fallbackActive ? 'mock_fallback' : 'database',
});

type PrimaryActionParams = Parameters<typeof useTerminalPrimaryAction>[0];

const refetch = () => ({ refetch: vi.fn().mockResolvedValue(undefined) });
const mutation = () => ({ mutateAsync: vi.fn() });

const createParams = (
  overrides: Partial<PrimaryActionParams> = {},
): PrimaryActionParams => ({
  pageKey: 'portfolio',
  market: 'HK',
  portfolio,
  marketOverviewQuery: refetch(),
  stockResearchQuery: refetch(),
  createStrategyDraftMutation: mutation(),
  strategyLabQuery: refetch(),
  createBacktestTaskMutation: mutation(),
  preTradeRiskCheckMutation: mutation(),
  createPaperOrderMutation: mutation(),
  portfolioQuery: refetch(),
  createAIResearchTaskMutation: mutation(),
  monitorQuery: refetch(),
  ...overrides,
});

let queryClient: QueryClient;

const wrapper = ({ children }: PropsWithChildren) =>
  createElement(QueryClientProvider, { client: queryClient }, children);

describe('useTerminalPrimaryAction portfolio flow', () => {
  beforeEach(() => {
    queryClient = new QueryClient();
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    queryClient.clear();
  });

  it('没有组合数据时阻止模拟下单', async () => {
    const params = createParams({ portfolio: undefined });
    const { result } = renderHook(() => useTerminalPrimaryAction(params), { wrapper });

    await act(async () => result.current.runPrimaryAction());

    expect(dependencyMocks.message.warning).toHaveBeenCalledWith(
      '当前没有可提交的模拟订单标的。',
    );
    expect(params.preTradeRiskCheckMutation.mutateAsync).not.toHaveBeenCalled();
    expect(params.createPaperOrderMutation.mutateAsync).not.toHaveBeenCalled();
  });

  it('风险检查拒绝后不创建订单', async () => {
    const params = createParams();
    vi.mocked(params.preTradeRiskCheckMutation.mutateAsync).mockResolvedValue(
      createRiskResponse('rejected', '单一持仓权重过高'),
    );
    const { result } = renderHook(() => useTerminalPrimaryAction(params), { wrapper });

    await act(async () => result.current.runPrimaryAction());

    expect(dependencyMocks.message.error).toHaveBeenCalledWith(
      '下单前风险检查拒绝：单一持仓权重过高',
    );
    expect(params.createPaperOrderMutation.mutateAsync).not.toHaveBeenCalled();
  });

  it('风险警告后继续提交订单并刷新账户缓存', async () => {
    const params = createParams();
    vi.mocked(params.preTradeRiskCheckMutation.mutateAsync).mockResolvedValue(
      createRiskResponse('warning', '预计持仓集中度较高'),
    );
    vi.mocked(params.createPaperOrderMutation.mutateAsync).mockResolvedValue(
      createOrderResponse(),
    );
    dependencyMocks.getPortfolioAccountSummary.mockResolvedValue(accountSummary);
    const { result } = renderHook(() => useTerminalPrimaryAction(params), { wrapper });

    await act(async () => result.current.runPrimaryAction());

    expect(dependencyMocks.message.warning).toHaveBeenCalledWith(
      '下单前风险检查提示：预计持仓集中度较高',
    );
    expect(dependencyMocks.message.success).toHaveBeenCalledWith(
      'Mock 模拟订单已提交：paper-order-001，标的：00700.HK',
    );
    expect(dependencyMocks.getPortfolioAccountSummary).toHaveBeenCalledWith({
      accountId: 'paper-hk-001',
    });
    expect(
      queryClient.getQueryData(portfolioAccountSummaryQueryKey('paper-hk-001')),
    ).toEqual(accountSummary);
    expect(queryClient.getQueryData(portfolioSummaryQueryKey('HK'))).toEqual(
      accountSummary,
    );
    expect(params.portfolioQuery.refetch).not.toHaveBeenCalled();
  });

  it('账户级刷新失败时回退市场级刷新', async () => {
    const params = createParams();
    vi.mocked(params.preTradeRiskCheckMutation.mutateAsync).mockResolvedValue(
      createRiskResponse('approved'),
    );
    vi.mocked(params.createPaperOrderMutation.mutateAsync).mockResolvedValue(
      createOrderResponse(),
    );
    dependencyMocks.getPortfolioAccountSummary.mockRejectedValue(
      new Error('database reads disabled'),
    );
    const { result } = renderHook(() => useTerminalPrimaryAction(params), { wrapper });

    await act(async () => result.current.runPrimaryAction());

    expect(dependencyMocks.message.success).toHaveBeenCalledWith(
      '下单前风险检查通过。',
    );
    expect(params.portfolioQuery.refetch).toHaveBeenCalledTimes(1);
  });

  it('订单进入 Mock fallback 时保留回执但不刷新账户', async () => {
    const params = createParams();
    vi.mocked(params.preTradeRiskCheckMutation.mutateAsync).mockResolvedValue(
      createRiskResponse('approved'),
    );
    vi.mocked(params.createPaperOrderMutation.mutateAsync).mockResolvedValue(
      createOrderResponse(true),
    );
    const { result } = renderHook(() => useTerminalPrimaryAction(params), { wrapper });

    await act(async () => result.current.runPrimaryAction());

    expect(dependencyMocks.message.warning).toHaveBeenCalledWith(
      '模拟订单已生成但未写入数据库：paper-order-001，标的：00700.HK',
    );
    expect(dependencyMocks.getPortfolioAccountSummary).not.toHaveBeenCalled();
    expect(params.portfolioQuery.refetch).not.toHaveBeenCalled();
  });
});

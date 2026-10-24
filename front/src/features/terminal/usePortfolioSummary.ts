import { useMutation, useQuery } from '@tanstack/react-query';
import {
  createPaperOrder,
  getPortfolioAccountSummary,
  getPortfolioSummary,
  type CreatePaperOrderParams,
  type GetPortfolioAccountSummaryParams,
  type GetPortfolioSummaryParams,
} from '@/services/terminal/portfolio';
import type { MarketCode } from './types';

type UsePortfolioSummaryParams = GetPortfolioSummaryParams & {
  enabled?: boolean;
};

type UsePortfolioAccountSummaryParams = GetPortfolioAccountSummaryParams & {
  enabled?: boolean;
};

export const portfolioSummaryQueryKey = (market: MarketCode) => [
  'terminal',
  'portfolio',
  market,
];

export const portfolioAccountSummaryQueryKey = (accountId: string) => [
  'terminal',
  'portfolio',
  'account',
  accountId,
];

export const createPaperOrderMutationKey = ['terminal', 'portfolio', 'paper-order'];

export const usePortfolioSummary = ({
  market,
  enabled = true,
}: UsePortfolioSummaryParams) => {
  // 模拟组合当前来自 Mock API，先用统一 hook 管理缓存和请求状态。
  return useQuery({
    queryKey: portfolioSummaryQueryKey(market),
    queryFn: () => getPortfolioSummary({ market }),
    enabled,
    staleTime: 30_000,
    refetchInterval: enabled ? 60_000 : false,
  });
};

export const usePortfolioAccountSummary = ({
  accountId,
  enabled = true,
}: UsePortfolioAccountSummaryParams) => {
  // 账户级快照用于下单后精确刷新当前模拟账户，不和市场级 Mock 回退缓存混用。
  return useQuery({
    queryKey: portfolioAccountSummaryQueryKey(accountId),
    queryFn: () => getPortfolioAccountSummary({ accountId }),
    enabled: enabled && accountId.trim().length > 0,
    staleTime: 15_000,
    refetchInterval: false,
  });
};

export const useCreatePaperOrder = () => {
  // 模拟订单属于写操作，用 mutation 承接提交状态和错误状态。
  return useMutation({
    mutationKey: createPaperOrderMutationKey,
    mutationFn: (payload: CreatePaperOrderParams) => createPaperOrder(payload),
  });
};

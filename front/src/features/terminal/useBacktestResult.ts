import { useMutation, useQuery } from '@tanstack/react-query';
import {
  createBacktestTask,
  getBacktestById,
  getBacktestByPollUrl,
  getBacktestResult,
  type CreateBacktestTaskParams,
  type GetBacktestByIdParams,
  type GetBacktestByPollUrlParams,
  type GetBacktestResultParams,
} from '@/services/terminal/backtest';
import type { MarketCode } from './types';

type UseBacktestResultParams = GetBacktestResultParams & {
  enabled?: boolean;
};

type UseBacktestByIdParams = GetBacktestByIdParams & {
  enabled?: boolean;
};

type UseBacktestByPollUrlParams = GetBacktestByPollUrlParams & {
  enabled?: boolean;
};

export const backtestResultQueryKey = (market: MarketCode) => [
  'terminal',
  'backtest',
  market,
];

export const backtestByIdQueryKey = (backtestId: string) => [
  'terminal',
  'backtest',
  'task',
  backtestId,
];

export const backtestByPollUrlQueryKey = (pollUrl: string) => [
  'terminal',
  'backtest',
  'poll',
  pollUrl,
];

export const backtestTaskCreateMutationKey = ['terminal', 'backtest', 'create'];

export const useCreateBacktestTask = () => {
  // 当前只提交 Mock 回测任务创建请求，页面层后续决定是否刷新或轮询回测结果。
  return useMutation({
    mutationKey: backtestTaskCreateMutationKey,
    mutationFn: (payload: CreateBacktestTaskParams) => createBacktestTask(payload),
  });
};

export const useBacktestResult = ({
  market,
  enabled = true,
}: UseBacktestResultParams) => {
  // 回测结果在原型阶段来自 Mock API，先用统一 hook 管理缓存和请求状态。
  return useQuery({
    queryKey: backtestResultQueryKey(market),
    queryFn: () => getBacktestResult({ market }),
    enabled,
    staleTime: 60_000,
    refetchInterval: enabled ? 120_000 : false,
  });
};

export const useBacktestById = ({
  backtestId,
  enabled = true,
}: UseBacktestByIdParams) => {
  // 查询某一次回测任务的结果，供创建任务后的结果轮询或详情展示使用。
  return useQuery({
    queryKey: backtestByIdQueryKey(backtestId),
    queryFn: () => getBacktestById({ backtestId }),
    enabled: enabled && backtestId.length > 0,
    retry: false,
    staleTime: 30_000,
    refetchInterval: enabled ? 30_000 : false,
  });
};

export const useBacktestByPollUrl = ({
  pollUrl,
  enabled = true,
}: UseBacktestByPollUrlParams) => {
  // 直接复用后端回执里的轮询地址，避免页面层拆解 API 路径。
  return useQuery({
    queryKey: backtestByPollUrlQueryKey(pollUrl),
    queryFn: () => getBacktestByPollUrl({ pollUrl }),
    enabled: enabled && pollUrl.length > 0,
    retry: false,
    staleTime: 30_000,
    refetchInterval: enabled ? 30_000 : false,
  });
};

import { useMutation, useQuery } from '@tanstack/react-query';
import {
  createStrategyDraft,
  getStrategyLab,
  parseStrategyNaturalLanguage,
  type CreateStrategyDraftParams,
  type GetStrategyLabParams,
  type ParseStrategyNaturalLanguageParams,
} from '@/services/terminal/strategy';
import type { MarketCode } from './types';

type UseStrategyLabParams = GetStrategyLabParams & {
  enabled?: boolean;
};

export const strategyLabQueryKey = (market: MarketCode) => [
  'terminal',
  'strategy-lab',
  market,
];

export const strategyDraftCreateMutationKey = ['terminal', 'strategy-lab', 'create'];

export const strategyNaturalLanguageParseMutationKey = [
  'terminal',
  'strategy-lab',
  'parse-natural-language',
];

export const useParseStrategyNaturalLanguage = () => {
  // 只解析为可编辑条件，不保存草案；页面层拿到结果后再决定是否应用到当前草案。
  return useMutation({
    mutationKey: strategyNaturalLanguageParseMutationKey,
    mutationFn: (payload: ParseStrategyNaturalLanguageParams) =>
      parseStrategyNaturalLanguage(payload),
  });
};

export const useCreateStrategyDraft = () => {
  // 当前只提交 Mock 策略草案创建请求，页面层后续决定是否刷新 Strategy Lab 数据。
  return useMutation({
    mutationKey: strategyDraftCreateMutationKey,
    mutationFn: (payload: CreateStrategyDraftParams) => createStrategyDraft(payload),
  });
};

export const useStrategyLab = ({ market, enabled = true }: UseStrategyLabParams) => {
  // 策略实验室当前使用 Mock API，先用统一 hook 固定请求状态和缓存入口。
  return useQuery({
    queryKey: strategyLabQueryKey(market),
    queryFn: () => getStrategyLab({ market }),
    enabled,
    staleTime: 30_000,
    refetchInterval: enabled ? 60_000 : false,
  });
};

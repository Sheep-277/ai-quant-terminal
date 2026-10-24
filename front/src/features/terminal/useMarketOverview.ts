import { useQuery } from '@tanstack/react-query';
import { getMarketOverview } from '@/services/terminal/market';
import type { MarketCode } from './types';

type UseMarketOverviewOptions = {
  enabled?: boolean;
};

export const marketOverviewQueryKey = (market: MarketCode) => [
  'terminal',
  'market-overview',
  market,
];

export const useMarketOverview = (market: MarketCode, { enabled = true }: UseMarketOverviewOptions = {}) => {
  // React Query 负责缓存、加载态和错误态，后续页面接入时不用手写请求状态。
  return useQuery({
    queryKey: marketOverviewQueryKey(market),
    queryFn: () => getMarketOverview(market),
    enabled,
    staleTime: 15_000,
    refetchInterval: enabled ? 30_000 : false,
  });
};

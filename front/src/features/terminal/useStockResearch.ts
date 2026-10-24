import { useQuery } from '@tanstack/react-query';
import {
  getStockResearch,
  type GetStockResearchParams,
} from '@/services/terminal/stock';
import type { MarketCode } from './types';

type UseStockResearchParams = GetStockResearchParams & {
  enabled?: boolean;
};

export const stockResearchQueryKey = (market: MarketCode, symbol?: string) => [
  'terminal',
  'stock-research',
  market,
  symbol ?? 'default',
];

export const useStockResearch = ({ market, symbol, enabled = true }: UseStockResearchParams) => {
  // 个股研究数据变化频率低于行情流，这里先用轮询保持原型阶段数据联通。
  return useQuery({
    queryKey: stockResearchQueryKey(market, symbol),
    queryFn: () => getStockResearch({ market, symbol }),
    enabled,
    staleTime: 15_000,
    refetchInterval: enabled ? 30_000 : false,
  });
};

import { request } from '@umijs/max';
import type { StockResearchResponse } from '@/features/terminal/apiTypes';
import type { MarketCode } from '@/features/terminal/types';

export type GetStockResearchParams = {
  market: MarketCode;
  symbol?: string;
};

export async function getStockResearch({ market, symbol }: GetStockResearchParams) {
  // 统一从服务层访问后端接口，避免页面组件散落 API 路径和查询参数。
  return request<StockResearchResponse>('/api/v1/stock/research', {
    method: 'GET',
    params: { market, symbol },
  });
}

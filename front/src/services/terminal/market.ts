import { request } from '@umijs/max';
import type { MarketOverviewResponse } from '@/features/terminal/apiTypes';
import type { MarketCode } from '@/features/terminal/types';

export async function getMarketOverview(market: MarketCode) {
  // 统一从前端服务层访问后端 API，页面组件不直接拼 URL。
  return request<MarketOverviewResponse>('/api/v1/market/overview', {
    method: 'GET',
    params: { market },
  });
}

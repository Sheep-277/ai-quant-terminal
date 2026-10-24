import { request } from '@umijs/max';
import type {
  PaperOrderCreateResponse,
  PaperOrderRequest,
  PortfolioResponse,
} from '@/features/terminal/apiTypes';
import type { MarketCode } from '@/features/terminal/types';

export type GetPortfolioSummaryParams = {
  market: MarketCode;
};

export type GetPortfolioAccountSummaryParams = {
  accountId: string;
};

export async function getPortfolioSummary({ market }: GetPortfolioSummaryParams) {
  // Portfolio 页面通过服务层访问后端，避免组件直接维护 API 路径。
  return request<PortfolioResponse>('/api/v1/portfolio/summary', {
    method: 'GET',
    params: { market },
  });
}

export async function getPortfolioAccountSummary({ accountId }: GetPortfolioAccountSummaryParams) {
  // 账户级读取只用于已存在的本地模拟账户，不用市场 Mock 数据顶替具体账户。
  return request<PortfolioResponse>(`/api/v1/portfolio/accounts/${encodeURIComponent(accountId)}/summary`, {
    method: 'GET',
  });
}

export type CreatePaperOrderParams = PaperOrderRequest;

export async function createPaperOrder(payload: CreatePaperOrderParams) {
  // 当前只提交模拟订单，paper_trading 由调用方显式传入并由后端再次校验。
  return request<PaperOrderCreateResponse>('/api/v1/paper/orders', {
    method: 'POST',
    data: payload,
  });
}

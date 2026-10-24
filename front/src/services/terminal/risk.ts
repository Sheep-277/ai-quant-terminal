import { request } from '@umijs/max';
import type {
  PreTradeRiskCheckRequest,
  PreTradeRiskCheckResponse,
} from '@/features/terminal/apiTypes';

export type PreTradeRiskCheckParams = PreTradeRiskCheckRequest;

export async function preTradeRiskCheck(payload: PreTradeRiskCheckParams) {
  // 这里只做下单前风险检查，不创建订单，也不连接真实券商。
  return request<PreTradeRiskCheckResponse>('/api/v1/risk/pre-trade-check', {
    method: 'POST',
    data: payload,
  });
}

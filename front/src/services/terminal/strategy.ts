import { request } from '@umijs/max';
import type {
  StrategyDraftCreateRequest,
  StrategyDraftDto,
  StrategyLabResponse,
  StrategyNaturalLanguageParseRequest,
  StrategyNaturalLanguageParseResponse,
} from '@/features/terminal/apiTypes';
import type { MarketCode } from '@/features/terminal/types';

export type GetStrategyLabParams = {
  market: MarketCode;
};

export type CreateStrategyDraftParams = StrategyDraftCreateRequest;

export type ParseStrategyNaturalLanguageParams = StrategyNaturalLanguageParseRequest;

export async function parseStrategyNaturalLanguage(
  payload: ParseStrategyNaturalLanguageParams,
) {
  // 只请求后端解析预览，不保存草案、不触发回测；用户确认后再走 createStrategyDraft。
  return request<StrategyNaturalLanguageParseResponse>(
    '/api/v1/strategy/parse-natural-language',
    {
      method: 'POST',
      data: payload,
    },
  );
}

export async function createStrategyDraft(payload: CreateStrategyDraftParams) {
  // 当前 POST 只创建 Mock 策略草案，不落库、不触发回测，也不进入模拟交易。
  return request<StrategyDraftDto>('/api/v1/strategies', {
    method: 'POST',
    data: payload,
  });
}

export async function getStrategyLab({ market }: GetStrategyLabParams) {
  // Strategy Lab 的页面和 hook 只调用服务函数，不直接维护后端路径。
  return request<StrategyLabResponse>('/api/v1/strategy/lab', {
    method: 'GET',
    params: { market },
  });
}

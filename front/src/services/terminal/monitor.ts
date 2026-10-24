import { request } from '@umijs/max';
import type { MonitorCalculatedSignalsResponse, MonitorResponse } from '@/features/terminal/apiTypes';
import type { MarketCode } from '@/features/terminal/types';

export type GetMonitorStreamParams = {
  market: MarketCode;
};

export type GetMonitorCalculatedSignalsParams = {
  market: MarketCode;
  symbol: string;
};

export type MonitorCalculationRequestOptions = {
  signal?: AbortSignal;
};

export async function getMonitorCalculatedSignals(
  { market, symbol }: GetMonitorCalculatedSignalsParams,
  { signal }: MonitorCalculationRequestOptions = {},
): Promise<MonitorCalculatedSignalsResponse> {
  // 单次按需计算独立于快照轮询；失败和取消交给调用方处理，不重试或拼接 Mock。
  return request<MonitorCalculatedSignalsResponse>('/api/v1/monitor/signals', {
    method: 'GET',
    params: { market, symbol },
    timeout: 60_000,
    signal,
    skipErrorHandler: true,
  });
}

export async function getMonitorStream({ market }: GetMonitorStreamParams) {
  // Monitor 页面通过服务层访问后端，后续替换实时流实现时保持组件调用稳定。
  return request<MonitorResponse>('/api/v1/monitor/stream', {
    method: 'GET',
    params: { market },
  });
}

import { useQuery } from '@tanstack/react-query';
import {
  getMonitorStream,
  type GetMonitorStreamParams,
} from '@/services/terminal/monitor';
import type { MarketCode } from './types';

type UseMonitorStreamParams = GetMonitorStreamParams & {
  enabled?: boolean;
};

export const monitorStreamQueryKey = (market: MarketCode) => [
  'terminal',
  'monitor',
  market,
];

export const useMonitorStream = ({
  market,
  enabled = true,
}: UseMonitorStreamParams) => {
  // REST 请求成功不代表实时行情已连接；保留响应中的快照状态和原始数据时间。
  return useQuery({
    queryKey: monitorStreamQueryKey(market),
    queryFn: () => getMonitorStream({ market }),
    enabled,
    staleTime: 5_000,
    refetchInterval: enabled ? 10_000 : false,
  });
};

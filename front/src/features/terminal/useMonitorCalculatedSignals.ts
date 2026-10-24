import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getMonitorCalculatedSignals,
  type GetMonitorCalculatedSignalsParams,
} from '@/services/terminal/monitor';

export const monitorCalculatedSignalsQueryKey = ({ market, symbol }: GetMonitorCalculatedSignalsParams) => [
  'terminal',
  'monitor-calculated-signals',
  market,
  symbol.trim().toUpperCase(),
] as const;

export const useMonitorCalculatedSignals = ({ market, symbol }: GetMonitorCalculatedSignalsParams) => {
  const queryClient = useQueryClient();
  const normalizedSymbol = symbol.trim().toUpperCase();
  const queryKey = monitorCalculatedSignalsQueryKey({ market, symbol: normalizedSymbol });
  const query = useQuery({
    queryKey,
    queryFn: ({ signal }) => {
      if (!normalizedSymbol) {
        throw new Error('monitor_symbol_required');
      }
      // 消费 Query 的 signal，取消、换标的或卸载时中止客户端等待。
      return getMonitorCalculatedSignals({ market, symbol: normalizedSymbol }, { signal });
    },
    enabled: false,
    retry: false,
    refetchInterval: false,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    // 手动操作立即执行或失败，不在离线队列里等待重连后悄悄发起。
    networkMode: 'always',
  });

  return {
    ...query,
    cancel: () => queryClient.cancelQueries({ queryKey, exact: true }),
  };
};

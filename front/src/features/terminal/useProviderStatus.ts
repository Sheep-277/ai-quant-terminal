import { useQuery } from '@tanstack/react-query';
import { getProviderStatus, getProviderStatusLogs } from '@/services/terminal/provider';

export const providerStatusQueryKey = ['terminal', 'provider-status'];
export const providerStatusLogsQueryKey = (limit: number, providerName?: string) => [
  'terminal',
  'provider-status-logs',
  limit,
  providerName ?? 'all',
];

export const useProviderStatus = () =>
  useQuery({
    queryKey: providerStatusQueryKey,
    queryFn: getProviderStatus,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });

export const useProviderStatusLogs = ({
  enabled,
  limit = 20,
  providerName,
}: {
  enabled: boolean;
  limit?: number;
  providerName?: string;
}) =>
  useQuery({
    queryKey: providerStatusLogsQueryKey(limit, providerName),
    queryFn: () => getProviderStatusLogs({ limit, providerName }),
    enabled,
    staleTime: 10_000,
  });

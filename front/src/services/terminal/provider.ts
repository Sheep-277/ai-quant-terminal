import { request } from '@umijs/max';
import type { ProviderStatusLogListResponse, ProviderStatusResponse } from '@/features/terminal/apiTypes';

export async function getProviderStatus() {
  return request<ProviderStatusResponse>('/api/v1/provider/status', {
    method: 'GET',
  });
}

export async function getProviderStatusLogs(params: { limit?: number; providerName?: string } = {}) {
  return request<ProviderStatusLogListResponse>('/api/v1/provider/status/logs', {
    method: 'GET',
    params: {
      limit: params.limit ?? 20,
      provider_name: params.providerName,
    },
  });
}

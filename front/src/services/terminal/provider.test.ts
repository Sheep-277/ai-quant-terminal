import { request } from '@umijs/max';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  ProviderStatusLogListResponse,
  ProviderStatusResponse,
} from '@/features/terminal/apiTypes';
import { getProviderStatus, getProviderStatusLogs } from './provider';

vi.mock('@umijs/max', () => ({
  request: vi.fn(),
}));

const providerStatusResponse: ProviderStatusResponse = {
  provider_name: 'YahooFinance',
  mode: 'real',
  ready: true,
  data_status: 'delayed',
  fallback_active: false,
  fallback_reason: null,
  source_type: 'provider',
  active_source: 'yahoo_finance',
  missing_configuration: [],
  next_action: null,
  last_logged_at: '2026-10-17T01:30:00Z',
  recent_log_count: 2,
};

const providerStatusLogsResponse: ProviderStatusLogListResponse = {
  items: [
    {
      id: 1,
      provider_name: 'YahooFinance',
      mode: 'real',
      ready: true,
      data_status: 'delayed',
      fallback_active: false,
      fallback_reason: null,
      checked_at: '2026-10-17T01:30:00Z',
    },
    {
      id: 2,
      provider_name: 'MockProvider',
      mode: 'mock',
      ready: true,
      data_status: 'delayed',
      fallback_active: true,
      fallback_reason: 'public provider unavailable',
      checked_at: '2026-10-17T01:20:00Z',
    },
  ],
  total: 2,
  database_available: true,
  fallback_reason: null,
};

describe('provider service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('通过 Provider 状态路径获取当前状态并透传数据来源', async () => {
    vi.mocked(request).mockResolvedValue(providerStatusResponse);

    const response = await getProviderStatus();

    expect(response).toEqual(providerStatusResponse);
    expect(request).toHaveBeenCalledWith('/api/v1/provider/status', {
      method: 'GET',
    });
    expect(response).toMatchObject({
      provider_name: 'YahooFinance',
      mode: 'real',
      data_status: 'delayed',
      fallback_active: false,
    });
  });

  it('未指定日志参数时默认请求最近二十条记录', async () => {
    vi.mocked(request).mockResolvedValue(providerStatusLogsResponse);

    await expect(getProviderStatusLogs()).resolves.toEqual(
      providerStatusLogsResponse,
    );
    expect(request).toHaveBeenCalledWith('/api/v1/provider/status/logs', {
      method: 'GET',
      params: {
        limit: 20,
        provider_name: undefined,
      },
    });
  });

  it('将日志条数和 Provider 名称转换为后端查询参数', async () => {
    vi.mocked(request).mockResolvedValue(providerStatusLogsResponse);

    await getProviderStatusLogs({
      limit: 50,
      providerName: 'YahooFinance',
    });

    expect(request).toHaveBeenCalledWith('/api/v1/provider/status/logs', {
      method: 'GET',
      params: {
        limit: 50,
        provider_name: 'YahooFinance',
      },
    });
  });

  it('保留 Provider 当前状态请求错误供页面统一处理', async () => {
    const requestError = new Error('provider status unavailable');
    vi.mocked(request).mockRejectedValue(requestError);

    await expect(getProviderStatus()).rejects.toBe(requestError);
  });

  it('保留 Provider 日志请求错误供页面统一处理', async () => {
    const requestError = new Error('provider logs unavailable');
    vi.mocked(request).mockRejectedValue(requestError);

    await expect(
      getProviderStatusLogs({ providerName: 'YahooFinance' }),
    ).rejects.toBe(requestError);
  });
});

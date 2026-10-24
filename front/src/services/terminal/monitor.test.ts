import { request } from '@umijs/max';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MonitorCalculatedSignalsResponse, MonitorResponse } from '@/features/terminal/apiTypes';
import type { MarketCode } from '@/features/terminal/types';
import { getMonitorCalculatedSignals, getMonitorStream } from './monitor';

vi.mock('@umijs/max', () => ({
  request: vi.fn(),
}));

const monitorResponse: MonitorResponse = {
  market: 'HK',
  timestamp: '2026-10-16T02:10:00Z',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  stream: {
    status: 'connected',
    latency_ms: 86,
    last_heartbeat_at: '2026-10-16T02:09:58Z',
    reconnect_attempts: 0,
    data_status: 'realtime',
  },
  signals: [],
  events: [],
};

describe('monitor service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('通过监控流路径获取快照并透传响应', async () => {
    vi.mocked(request).mockResolvedValue(monitorResponse);

    await expect(getMonitorStream({ market: 'HK' })).resolves.toEqual(
      monitorResponse,
    );
    expect(request).toHaveBeenCalledWith('/api/v1/monitor/stream', {
      method: 'GET',
      params: { market: 'HK' },
    });
  });

  it.each<MarketCode>(['US', 'HK', 'CN'])('显式传递 %s 市场参数', async (market) => {
    vi.mocked(request).mockResolvedValue({
      ...monitorResponse,
      market,
    });

    await getMonitorStream({ market });

    expect(request).toHaveBeenCalledWith('/api/v1/monitor/stream', {
      method: 'GET',
      params: { market },
    });
  });

  it('保留监控请求错误供页面统一错误处理', async () => {
    const requestError = new Error('monitor stream unavailable');
    vi.mocked(request).mockRejectedValue(requestError);

    await expect(getMonitorStream({ market: 'CN' })).rejects.toBe(requestError);
  });
});

describe('monitor calculated signals service', () => {
  const response: MonitorCalculatedSignalsResponse = {
    market: 'US', symbol: 'NVDA', timezone: 'America/New_York', currency: 'USD',
    source: 'yahoo_finance', data_status: 'delayed', timestamp: '2026-10-20T13:30:00Z',
    bar_count: 65, calculation_scope: 'price_only',
    signals: [{ code: 'momentum_weakness', title: '20D momentum weakened', direction: 'negative', severity: 'warning', score: 0.6, evidence: ['momentum_20d=-0.05'] }],
  };

  beforeEach(() => { vi.clearAllMocks(); });

  it.each<{ market: MarketCode; symbol: string }>([
    { market: 'US', symbol: 'NVDA' },
    { market: 'HK', symbol: '00700.HK' },
    { market: 'CN', symbol: '300750.SZ' },
  ])('显式传递 $market 标的，不访问原监控快照路径', async ({ market, symbol }) => {
    vi.mocked(request).mockResolvedValue({ ...response, market, symbol });
    await getMonitorCalculatedSignals({ market, symbol });
    expect(request).toHaveBeenCalledTimes(1);
    expect(request).toHaveBeenCalledWith('/api/v1/monitor/signals', {
      method: 'GET', params: { market, symbol }, timeout: 60_000, signal: undefined, skipErrorHandler: true,
    });
  });

  it('透传来源、行情时间和计算证据，不创建模拟连接或事件', async () => {
    vi.mocked(request).mockResolvedValue(response);
    const result = await getMonitorCalculatedSignals({ market: 'US', symbol: 'NVDA' });
    expect(result).toBe(response);
    expect(result).not.toHaveProperty('stream');
    expect(result).not.toHaveProperty('events');
    expect(result.timestamp).toBe('2026-10-20T13:30:00Z');
  });

  it('空信号成功时不填入样例记录', async () => {
    vi.mocked(request).mockResolvedValue({ ...response, signals: [] });
    await expect(getMonitorCalculatedSignals({ market: 'US', symbol: 'NVDA' })).resolves.toMatchObject({ signals: [] });
  });

  it('将取消信号交给请求层', async () => {
    const controller = new AbortController();
    vi.mocked(request).mockResolvedValue(response);
    await getMonitorCalculatedSignals({ market: 'US', symbol: 'NVDA' }, { signal: controller.signal });
    expect(request).toHaveBeenCalledWith('/api/v1/monitor/signals', expect.objectContaining({ signal: controller.signal }));
  });

  it.each([
    { response: { status: 503, data: { detail: { code: 'monitor_public_data_unavailable' } } } },
    { response: { status: 422 } },
    { code: 'ECONNABORTED' },
    { code: 'ERR_CANCELED' },
  ])('HTTP失败、超时或取消原样抛出，不重试或回退', async (error) => {
    vi.mocked(request).mockRejectedValue(error);
    await expect(getMonitorCalculatedSignals({ market: 'US', symbol: 'NVDA' })).rejects.toBe(error);
    expect(request).toHaveBeenCalledTimes(1);
  });
});

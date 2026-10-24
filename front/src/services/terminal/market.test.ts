import { request } from '@umijs/max';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarketOverviewResponse } from '@/features/terminal/apiTypes';
import type { MarketCode } from '@/features/terminal/types';
import { getMarketOverview } from './market';

vi.mock('@umijs/max', () => ({
  request: vi.fn(),
}));

const marketOverviewResponse: MarketOverviewResponse = {
  market: 'HK',
  timestamp: '2026-10-16T02:10:00Z',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  benchmark: 'Hang Seng Index',
  data_status: 'delayed',
  indices: [
    {
      name: 'Hang Seng Index',
      symbol: '^HSI',
      value: 25_642.31,
      change_percent: -0.0042,
      status: 'delayed',
      source: 'YahooFinance',
      timestamp: '2026-10-16T02:09:00Z',
    },
  ],
  breadth: {
    advancers_percent: 0.42,
    decliners_percent: 0.51,
    unchanged_percent: 0.07,
    new_highs: 38,
    new_lows: 54,
    source: 'YahooFinance',
    status: 'delayed',
    timestamp: '2026-10-16T02:09:00Z',
  },
  chart_bars: [
    {
      timestamp: '2026-10-15T08:00:00Z',
      open: 25_800,
      high: 25_930,
      low: 25_580,
      close: 25_642.31,
      volume: 1_580_000_000,
      data_status: 'delayed',
      source: 'YahooFinance',
    },
  ],
  sectors: [
    {
      name: '互联网',
      change_percent: -0.0081,
      direction: 'negative',
      source: 'YahooFinance',
      status: 'delayed',
      timestamp: '2026-10-16T02:09:00Z',
    },
  ],
  events: [
    {
      timestamp: '2026-10-16T02:08:00Z',
      source: 'PROVIDER',
      origin: 'system',
      title: '公开行情已更新',
      impact: '中性',
      confidence: 1,
    },
  ],
};

describe('market service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('通过市场总览路径获取快照并保留数据源状态', async () => {
    vi.mocked(request).mockResolvedValue(marketOverviewResponse);

    const response = await getMarketOverview('HK');

    expect(response).toEqual(marketOverviewResponse);
    expect(request).toHaveBeenCalledWith('/api/v1/market/overview', {
      method: 'GET',
      params: { market: 'HK' },
    });
    expect(response.indices[0]).toMatchObject({
      source: 'YahooFinance',
      status: 'delayed',
    });
  });

  it.each<MarketCode>(['US', 'HK', 'CN'])('显式传递 %s 市场参数', async (market) => {
    vi.mocked(request).mockResolvedValue({
      ...marketOverviewResponse,
      market,
    });

    await getMarketOverview(market);

    expect(request).toHaveBeenCalledWith('/api/v1/market/overview', {
      method: 'GET',
      params: { market },
    });
  });

  it('保留市场总览请求错误供页面统一处理', async () => {
    const requestError = new Error('market overview unavailable');
    vi.mocked(request).mockRejectedValue(requestError);

    await expect(getMarketOverview('US')).rejects.toBe(requestError);
  });
});

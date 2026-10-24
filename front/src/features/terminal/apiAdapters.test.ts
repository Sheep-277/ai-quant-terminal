import { describe, expect, it } from 'vitest';
import {
  mergeMarketOverviewSnapshot,
  toMonitorSnapshot,
  toStockResearchSnapshot,
} from './apiAdapters';
import type {
  MarketOverviewResponse,
  MonitorResponse,
  StockResearchResponse,
} from './apiTypes';
import { marketSnapshots } from './mockData';
import type { MarketCode } from './types';

describe('toMonitorSnapshot provenance', () => {
  const response: MonitorResponse = {
    market: 'US', timestamp: '2026-10-11T02:03:09Z', timezone: 'America/New_York', currency: 'USD',
    stream: { status: 'connected', latency_ms: 82, reconnect_attempts: 0, last_heartbeat_at: '2026-10-11T02:03:09Z', data_status: 'delayed' },
    signals: [], events: [],
  };

  it('将数据库信号来源与 Mock 连接来源分开，保留原始时间', () => {
    const snapshot = toMonitorSnapshot({ ...response, provenance: {
      transport: 'rest_polling', stream_source: 'mock', signal_source: 'database', event_source: 'mixed', heartbeat_basis: 'latest_signal',
    } });
    expect(snapshot.provenance).toEqual({
      transport: 'rest_polling', streamSource: 'mock', signalSource: 'database', eventSource: 'mixed', heartbeatBasis: 'latest_signal',
    });
    expect(snapshot.timestamp).toBe(response.timestamp);
    expect(snapshot.stream.lastHeartbeatAt).toBe(response.stream.last_heartbeat_at);
  });

  it('保留完整 Mock 来源', () => {
    const mockResponse: MonitorResponse = { ...response, stream: { ...response.stream, data_status: 'mock' }, provenance: {
      transport: 'rest_polling', stream_source: 'mock', signal_source: 'mock', event_source: 'mock', heartbeat_basis: 'mock_clock',
    } };
    expect(toMonitorSnapshot(mockResponse).stream.dataStatus).toBe('mock');
    expect(toMonitorSnapshot(mockResponse).provenance).toEqual({
      transport: 'rest_polling', streamSource: 'mock', signalSource: 'mock', eventSource: 'mock', heartbeatBasis: 'mock_clock',
    });
  });

  it('旧响应来源缺失时不根据事件文本猜测', () => {
    const legacy = { ...response, events: [{
      event_id: 'legacy', market: 'US' as const, source: 'PROVIDER' as const,
      title: 'YahooFinance', summary: '信号来自数据库 signals 表', impact: 'neutral' as const,
      confidence: 1, created_at: response.timestamp,
    }] };
    expect(Object.values(toMonitorSnapshot(legacy).provenance ?? {})).toEqual(Array(5).fill('unknown'));
    expect(legacy).not.toHaveProperty('provenance');
  });

  it('映射逐条来源，旧信号不根据证据或原始来源补造分类', () => {
    const base: MonitorResponse['signals'][number] = {
      signal_id: 'seed', market: 'US', symbol: 'NVDA', title: '信号', direction: 'neutral',
      severity: 'info', score: 0.5, triggered_at: response.timestamp, evidence: ['source=mock_seed'],
    };
    const result = toMonitorSnapshot({ ...response, signals: [
      { ...base, source: 'mock_seed', data_origin: 'seed' },
      { ...base, signal_id: 'mock', source: 'mock_quant_pipeline', data_origin: 'mock' },
      { ...base, signal_id: 'legacy', source: 'mock_seed' },
      { ...base, signal_id: 'missing' },
    ] });
    expect(result.signals.map(({ source, dataOrigin }) => ({ source, dataOrigin }))).toEqual([
      { source: 'mock_seed', dataOrigin: 'seed' },
      { source: 'mock_quant_pipeline', dataOrigin: 'mock' },
      { source: 'mock_seed', dataOrigin: 'unknown' },
      { source: null, dataOrigin: 'unknown' },
    ]);
  });
});

const buildOverview = (
  market: MarketCode,
  indices: MarketOverviewResponse['indices'],
): MarketOverviewResponse => ({
  market,
  timestamp: '2026-10-14T01:00:00Z',
  currency: marketSnapshots[market].currency,
  timezone: marketSnapshots[market].timezone,
  benchmark: marketSnapshots[market].benchmark,
  data_status: 'delayed',
  indices,
  breadth: {
    advancers_percent: 0.5,
    decliners_percent: 0.5,
    unchanged_percent: 0,
    new_highs: 0,
    new_lows: 0,
    source: 'mock_fallback',
    status: 'unavailable',
    timestamp: null,
  },
  chart_bars: [],
  sectors: [],
  events: [],
});

const indexQuote = (symbol: string, value = 6500): MarketOverviewResponse['indices'][number] => ({
  symbol,
  name: symbol,
  value,
  change_percent: 0.01,
  status: 'delayed',
});

const buildStockResearch = (): StockResearchResponse => ({
  profile: {
    market: 'US',
    symbol: 'AAPL',
    name: 'Apple Inc.',
    asset_type: 'common_stock',
    exchange: 'NASDAQ',
    currency: 'USD',
    timezone: 'America/New_York',
    sector: 'Technology',
    industry: 'Consumer Electronics',
  },
  quote: {
    price: 232.18,
    change: 2.31,
    change_percent: 0.01005,
    volume: 48_500_000,
    turnover: 11_260_000_000,
    timestamp: '2026-10-14T20:00:00Z',
    data_status: 'delayed',
  },
  valuation: {
    pe_ttm: 34.2,
    pb: 51.3,
    ps_ttm: 8.7,
    pfcf_ttm: 31.8,
  },
  profitability: {
    roe_ttm: 1.57,
    roic_ttm: 0.62,
    gross_margin_ttm: 0.47,
    operating_margin_ttm: 0.32,
  },
  cash_flow: {
    fcf_ttm: 108_000_000_000,
    operating_cash_flow_ttm: 125_000_000_000,
    capex_ttm: -17_000_000_000,
  },
  fundamental_data_status: {
    source: 'database',
    completeness: 'complete',
    available_sections: ['valuation', 'profitability', 'cash_flow'],
    missing_sections: [],
  },
  technical: {
    rsi_14: 58.4,
    macd: 2.16,
    macd_signal: 1.92,
    macd_histogram: 0.24,
  },
  technical_data_source: {
    source: 'quant_pipeline',
    detail: 'YahooFinance K线计算',
    fallback_active: false,
    data_status: 'delayed',
  },
  factor_snapshot: {
    momentum_20d: 0.081,
    trend_strength: 0.72,
    volatility_20d: 0.19,
    quality_score: 0.88,
    composite_score: 0.81,
  },
  factor_data_status: {
    source: 'quant_pipeline',
    completeness: 'computed',
    available_factors: ['momentum_20d', 'trend_strength'],
    missing_factors: [],
  },
  quant_signals: [],
  signal_data_status: {
    source: 'quant_pipeline',
    completeness: 'computed',
    signal_count: 0,
  },
  quote_data_source: {
    source: 'yahoo_finance',
    detail: 'YahooFinance 公开行情',
    fallback_active: false,
    data_status: 'delayed',
  },
  kline: {
    interval: '1d',
    data_status: 'delayed',
    bars: [
      {
        timestamp: '2026-10-14T04:00:00Z',
        open: 229.7,
        high: 233.1,
        low: 228.9,
        close: 232.18,
        volume: 48_500_000,
      },
    ],
  },
  kline_data_source: {
    source: 'yahoo_finance',
    detail: 'YahooFinance 日线',
    fallback_active: false,
    data_status: 'delayed',
  },
  risk_flags: ['20D annualized volatility elevated'],
  summary_points: ['动量保持正值', '估值处于较高区间'],
  summary_data_source: {
    source: 'quant_pipeline',
    detail: '确定性量化摘要',
    fallback_active: false,
    data_status: 'delayed',
  },
  direction: 'positive',
});

describe('market overview index mapping', () => {
  it('does not label stock prices or unknown symbols as the first index', () => {
    const overview = buildOverview('US', [indexQuote('AAPL', 232.18), indexQuote('NVDA', 181.42), indexQuote('UNKNOWN')]);
    const result = mergeMarketOverviewSnapshot(marketSnapshots.US, overview);

    expect(result.indices).toEqual([]);
  });

  it('renders a known index once when canonical and provider symbols both appear', () => {
    const overview = buildOverview('US', [indexQuote('SPX'), indexQuote('^GSPC', 6600), indexQuote('NDX', 22000)]);
    const result = mergeMarketOverviewSnapshot(marketSnapshots.US, overview);

    expect(result.indices.map((index) => index.labelId)).toEqual(['terminal.metric.sp500', 'terminal.metric.nasdaq100']);
    expect(result.indices[0].value).toBe(6500);
    expect(new Set(result.indices.map((index) => index.labelId)).size).toBe(result.indices.length);
  });

  it.each([
    ['US', '^NDX', 'terminal.metric.nasdaq100'],
    ['US', '^VIX', 'terminal.metric.vix'],
    ['HK', '^HSI', 'terminal.metric.hsi'],
    ['HK', 'HSTECH', 'terminal.metric.hstech'],
    ['HK', 'VHSI', 'terminal.metric.volIndex'],
    ['CN', '000300.SS', 'terminal.metric.csi300'],
    ['CN', '000001.SS', 'terminal.metric.sseComposite'],
    ['CN', '399006.SZ', 'terminal.metric.chiNext'],
  ] as const)('maps %s symbol %s to its own index', (market, symbol, labelId) => {
    const result = mergeMarketOverviewSnapshot(marketSnapshots[market], buildOverview(market, [indexQuote(symbol)]));

    expect(result.indices).toHaveLength(1);
    expect(result.indices[0].labelId).toBe(labelId);
  });

  it('does not display an index from a different market', () => {
    const result = mergeMarketOverviewSnapshot(marketSnapshots.HK, buildOverview('HK', [indexQuote('SPX')]));

    expect(result.indices).toEqual([]);
  });

  it('uses neutral tone for an unchanged index', () => {
    const quote = { ...indexQuote('SPX'), change_percent: 0 };
    const result = mergeMarketOverviewSnapshot(marketSnapshots.US, buildOverview('US', [quote]));

    expect(result.indices[0].tone).toBe('neutral');
  });

  it('retains the original snapshot when no response is available', () => {
    expect(mergeMarketOverviewSnapshot(marketSnapshots.US)).toBe(marketSnapshots.US);
  });

  it('preserves index provenance and timestamp for the card tooltip', () => {
    const quote = { ...indexQuote('SPX'), source: 'yahoo_finance', timestamp: '2026-10-14T01:00:00Z' };
    const result = mergeMarketOverviewSnapshot(marketSnapshots.US, buildOverview('US', [quote]));
    expect(result.indices[0].dataSource).toEqual({ source: 'yahoo_finance', status: 'delayed', timestamp: quote.timestamp });
  });

  it('marks a missing index unavailable instead of displaying zero as a price', () => {
    const quote = { ...indexQuote('SPX'), value: null, change_percent: null, status: 'unavailable' as const, source: 'yahoo_finance', timestamp: null };
    const result = mergeMarketOverviewSnapshot(marketSnapshots.US, buildOverview('US', [quote]));
    expect(result.indices[0].dataSource?.status).toBe('unavailable');
    expect(result.indices[0].change).toBeUndefined();
  });

  it('preserves the event origin instead of inferring it from the title', () => {
    const overview = {
      ...buildOverview('US', []),
      events: [{
        timestamp: '2026-10-14T01:00:00Z',
        source: 'DATABASE',
        origin: 'system' as const,
        title: '数据库行情已读取',
        impact: '数据状态提示',
        confidence: 1,
      }],
    };

    const result = mergeMarketOverviewSnapshot(marketSnapshots.US, overview);

    expect(result.events[0].eventOrigin).toBe('system');
  });

  it('keeps breadth and sector provenance independent from the index provider', () => {
    const overview = {
      ...buildOverview('US', [indexQuote('SPX')]),
      breadth: {
        advancers_percent: 0.6,
        decliners_percent: 0.3,
        unchanged_percent: 0.1,
        new_highs: 4,
        new_lows: 2,
        source: 'database',
        status: 'delayed' as const,
        timestamp: '2026-10-14T01:00:00Z',
      },
      sectors: [{
        name: 'Software',
        change_percent: 0.01,
        direction: 'positive' as const,
        source: 'mock_fallback',
        status: 'unavailable' as const,
        timestamp: null,
      }],
    };

    const result = mergeMarketOverviewSnapshot(marketSnapshots.US, overview);

    expect(result.breadthDataSource).toMatchObject({ source: 'database', fallbackActive: false, dataStatus: 'delayed' });
    expect(result.sectorDataSource).toMatchObject({ source: 'mock_fallback', fallbackActive: true, dataStatus: 'unavailable' });
  });
});

describe('stock research mapping', () => {
  it.each([null, 0])('distinguishes missing values from genuine zero across all stock metric groups: %s', value => {
    const response = buildStockResearch();
    response.valuation = { pe_ttm: value, pb: value, ps_ttm: value, pfcf_ttm: value };
    response.profitability = { roe_ttm: value, roic_ttm: value, gross_margin_ttm: value, operating_margin_ttm: value };
    response.cash_flow = { fcf_ttm: value, operating_cash_flow_ttm: value, capex_ttm: value };
    response.factor_snapshot = { momentum_20d: value, trend_strength: value, volatility_20d: value, quality_score: value, composite_score: value };
    response.technical = { rsi_14: value, macd: value, macd_signal: value, macd_histogram: value };
    const result = toStockResearchSnapshot(response);
    const expectedSources = {
      valuation: response.fundamental_data_status?.source,
      profitability: response.fundamental_data_status?.source,
      'cash-flow': response.fundamental_data_status?.source,
      factors: response.factor_data_status?.source,
      technical: response.technical_data_source.source,
    };
    expect(result.metricGroups.map(group => [group.key, group.metrics.length])).toEqual([
      ['valuation', 4], ['profitability', 4], ['cash-flow', 3], ['factors', 5], ['technical', 4],
    ]);
    for (const group of result.metricGroups) {
      for (const metric of group.metrics) {
        // Metric 的数值占位仍为 0，页面必须靠不可用标记区分空值与真实零值。
        expect(metric.value).toBe(0);
        if (value === null) {
          expect(metric.dataSource).toEqual({
            source: expectedSources[group.key as keyof typeof expectedSources], status: 'unavailable',
          });
        } else {
          expect(metric.dataSource?.status).not.toBe('unavailable');
        }
      }
    }
    expect(result.factorSnapshot).toEqual({
      momentum20d: value, trendStrength: value, volatility20d: value, qualityScore: value, compositeScore: value,
    });
  });

  it.each([
    ['US', 'AAPL', 'USD', 'America/New_York'],
    ['HK', '00700.HK', 'HKD', 'Asia/Hong_Kong'],
    ['CN', '600519.SH', 'CNY', 'Asia/Shanghai'],
  ] as const)('preserves %s identity and empty research content without sample backfill', (market, symbol, currency, timezone) => {
    const response = buildStockResearch();
    response.profile = { ...response.profile, market, symbol, currency, timezone };
    response.quote.timestamp = null;
    response.kline.bars = [];
    response.quant_signals = [];
    response.summary_points = [];
    response.risk_flags = [];
    const original = structuredClone(response);
    const result = toStockResearchSnapshot(response);
    expect(result).toMatchObject({ market, symbol, currency, timezone });
    expect(result.quote.timestamp).toBeNull();
    expect(result.kline.bars).toEqual([]);
    expect(result.quantSignals).toEqual([]);
    expect(result.summaryPoints).toEqual([]);
    expect(result.riskFlags).toEqual([]);
    expect(response).toEqual(original);
  });

  it('保留缺失的报价时间，不以市场快照时间填充', () => {
    const response = buildStockResearch();
    response.quote.timestamp = null;
    expect(toStockResearchSnapshot(response).quote.timestamp).toBeNull();
  });

  it('preserves the public quote and K-line provenance independently', () => {
    const result = toStockResearchSnapshot(buildStockResearch());

    expect(result.dataStatus).toBe('delayed');
    expect(result.quote).toMatchObject({
      price: 232.18,
      changePercent: 0.01005,
      timestamp: '2026-10-14T20:00:00Z',
    });
    expect(result.quoteDataSource).toEqual({
      source: 'yahoo_finance',
      detail: 'YahooFinance 公开行情',
      fallbackActive: false,
      dataStatus: 'delayed',
    });
    expect(result.klineDataSource).toEqual({
      source: 'yahoo_finance',
      detail: 'YahooFinance 日线',
      fallbackActive: false,
      dataStatus: 'delayed',
    });
    expect(result.kline.bars[0]).toMatchObject({
      open: 229.7,
      close: 232.18,
      volume: 48_500_000,
    });
  });

  it('maps technical indicators and their calculation source', () => {
    const result = toStockResearchSnapshot(buildStockResearch());
    const technicalMetrics = result.metricGroups.find(
      (group) => group.key === 'technical',
    )?.metrics;

    expect(technicalMetrics?.map(({ labelId, value }) => ({ labelId, value }))).toEqual([
      { labelId: 'terminal.metric.rsi14', value: 58.4 },
      { labelId: 'terminal.metric.macd', value: 2.16 },
      { labelId: 'terminal.metric.macdSignal', value: 1.92 },
      { labelId: 'terminal.metric.macdHistogram', value: 0.24 },
    ]);
    expect(result.technicalDataSource).toEqual({
      source: 'quant_pipeline',
      detail: 'YahooFinance K线计算',
      fallbackActive: false,
      dataStatus: 'delayed',
    });
  });

  it('marks missing stock metrics unavailable while preserving their source', () => {
    const response = buildStockResearch();
    response.valuation.pe_ttm = null;
    response.profitability.roe_ttm = null;
    response.cash_flow.fcf_ttm = null;
    response.factor_snapshot.momentum_20d = null;
    response.technical.rsi_14 = null;

    const metrics = toStockResearchSnapshot(response).metricGroups.flatMap(
      (group) => group.metrics,
    );

    for (const [labelId, source] of [
      ['terminal.metric.peTtm', 'database'],
      ['terminal.metric.roeTtm', 'database'],
      ['terminal.metric.fcfTtm', 'database'],
      ['terminal.metric.momentum20d', 'quant_pipeline'],
      ['terminal.metric.rsi14', 'quant_pipeline'],
    ]) {
      expect(metrics.find((metric) => metric.labelId === labelId)).toMatchObject({
        dataSource: { source, status: 'unavailable' },
      });
    }
  });

  it('keeps genuine zero stock metrics available', () => {
    const response = buildStockResearch();
    response.valuation.pe_ttm = 0;
    response.profitability.roe_ttm = 0;
    response.cash_flow.fcf_ttm = 0;
    response.factor_snapshot.momentum_20d = 0;
    response.technical.rsi_14 = 0;

    const metrics = toStockResearchSnapshot(response).metricGroups.flatMap(
      (group) => group.metrics,
    );

    for (const labelId of [
      'terminal.metric.peTtm',
      'terminal.metric.roeTtm',
      'terminal.metric.fcfTtm',
      'terminal.metric.momentum20d',
      'terminal.metric.rsi14',
    ]) {
      const metric = metrics.find((item) => item.labelId === labelId);
      expect(metric?.value).toBe(0);
      expect(metric?.dataSource?.status).not.toBe('unavailable');
    }
  });

  it('uses existing fallback sources for missing fields in older responses', () => {
    const response = buildStockResearch();
    response.fundamental_data_status = undefined;
    response.factor_data_status = undefined;
    response.valuation.pb = null;
    response.factor_snapshot.composite_score = null;

    const metrics = toStockResearchSnapshot(response).metricGroups.flatMap(
      (group) => group.metrics,
    );

    expect(metrics.find((metric) => metric.labelId === 'terminal.metric.pb'))
      .toMatchObject({ dataSource: { source: 'mock_provider', status: 'unavailable' } });
    expect(metrics.find((metric) => metric.labelId === 'terminal.metric.compositeScore'))
      .toMatchObject({ dataSource: { source: 'quant_pipeline', status: 'unavailable' } });
  });

  it('preserves structured summary content and provenance', () => {
    const result = toStockResearchSnapshot(buildStockResearch());

    expect(result.summaryPoints).toEqual([
      '动量保持正值',
      '估值处于较高区间',
    ]);
    expect(result.summaryDataSource).toEqual({
      source: 'quant_pipeline',
      detail: '确定性量化摘要',
      fallbackActive: false,
      dataStatus: 'delayed',
    });
  });
});

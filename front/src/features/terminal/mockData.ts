import type { DataSourceStatus, MarketCode, MarketSnapshot, PageDefinition, TerminalPageKey } from './types';

const mockSectionSource = (dataStatus: DataSourceStatus['dataStatus']): DataSourceStatus => ({
  source: 'mock_provider',
  detail: '',
  fallbackActive: false,
  dataStatus,
  timestamp: null,
});

export const pageDefinitions: Record<TerminalPageKey, PageDefinition> = {
  dashboard: { key: 'dashboard', title: 'terminal.page.dashboard.title', subtitle: 'terminal.page.dashboard.subtitle', primaryAction: 'terminal.primaryAction.explainMarket' },
  'stock-research': { key: 'stock-research', title: 'terminal.page.stockResearch.title', subtitle: 'terminal.page.stockResearch.subtitle', primaryAction: 'terminal.primaryAction.deepResearch' },
  'ai-research': { key: 'ai-research', title: 'terminal.page.aiResearch.title', subtitle: 'terminal.page.aiResearch.subtitle', primaryAction: 'terminal.primaryAction.createResearchTask' },
  'strategy-lab': { key: 'strategy-lab', title: 'terminal.page.strategyLab.title', subtitle: 'terminal.page.strategyLab.subtitle', primaryAction: 'terminal.primaryAction.saveStrategyDraft' },
  backtest: { key: 'backtest', title: 'terminal.page.backtest.title', subtitle: 'terminal.page.backtest.subtitle', primaryAction: 'terminal.primaryAction.createBacktestTask' },
  portfolio: { key: 'portfolio', title: 'terminal.page.portfolio.title', subtitle: 'terminal.page.portfolio.subtitle', primaryAction: 'terminal.primaryAction.submitPaperOrder' },
  monitor: { key: 'monitor', title: 'terminal.page.monitor.title', subtitle: 'terminal.page.monitor.subtitle', primaryAction: 'terminal.primaryAction.refreshMonitor' },
};

export const marketSnapshots: Record<MarketCode, MarketSnapshot> = {
  US: {
    code: 'US',
    labelId: 'terminal.market.us',
    currency: 'USD',
    timezone: 'America/New_York',
    benchmark: 'S&P 500',
    status: 'Open',
    updatedAt: '2026-09-02T14:42:16Z',
    indices: [
      { labelId: 'terminal.metric.sp500', value: 6184.22, change: 0.0042, changeFormat: 'percent', tone: 'positive' },
      { labelId: 'terminal.metric.nasdaq100', value: 22958.14, change: 0.0068, changeFormat: 'percent', tone: 'positive' },
      { labelId: 'terminal.metric.vix', value: 14.8, change: -0.031, changeFormat: 'percent', tone: 'positive' },
      { labelId: 'terminal.metric.tenYearYield', value: 0.0409, valueFormat: 'percent', change: 4, changeFormat: 'basisPoint', tone: 'warning' },
    ],
    breadth: [
      { labelId: 'terminal.metric.advancers', value: 0.61, valueFormat: 'percent', tone: 'positive' },
      { labelId: 'terminal.metric.decliners', value: 0.34, valueFormat: 'percent', tone: 'negative' },
      { labelId: 'terminal.metric.newHighs', value: 118, tone: 'positive' },
      { labelId: 'terminal.metric.signalQueue', value: 27, tone: 'accent' },
    ],
    breadthDataSource: mockSectionSource('realtime'),
    chartBars: [],
    sectors: [
      { labelId: 'terminal.sector.semis', value: 0.0134, valueFormat: 'percent', tone: 'positive' },
      { labelId: 'terminal.sector.software', value: 0.0071, valueFormat: 'percent', tone: 'positive' },
      { labelId: 'terminal.sector.banks', value: -0.0028, valueFormat: 'percent', tone: 'negative' },
      { labelId: 'terminal.sector.energy', value: -0.0063, valueFormat: 'percent', tone: 'negative' },
      { labelId: 'terminal.sector.healthcare', value: 0.0019, valueFormat: 'percent', tone: 'neutral' },
    ],
    sectorDataSource: mockSectionSource('realtime'),
    watchlist: [
      { key: 'NVDA', symbol: 'NVDA', nameId: 'terminal.stock.nvda', price: 128.44, changePercent: 0.0182, volume: 42100000, signalId: 'terminal.signal.momentumLong', riskId: 'terminal.risk.normal' },
      { key: 'AAPL', symbol: 'AAPL', nameId: 'terminal.stock.aapl', price: 232.18, changePercent: -0.0024, volume: 18500000, signalId: 'terminal.signal.hold', riskId: 'terminal.risk.normal' },
      { key: 'AMD', symbol: 'AMD', nameId: 'terminal.stock.amd', price: 174.02, changePercent: -0.0216, volume: 31700000, signalId: 'terminal.signal.volSpike', riskId: 'terminal.risk.elevated' },
      { key: 'MSFT', symbol: 'MSFT', nameId: 'terminal.stock.msft', price: 517.66, changePercent: 0.0039, volume: 9400000, signalId: 'terminal.signal.quality', riskId: 'terminal.risk.low' },
    ],
    events: [
      { key: 'e1', time: '2026-09-02T14:39:00Z', sourceId: 'terminal.source.fastPath', eventOrigin: 'mock_sample', eventTitle: 'NVDA 成交量比率突破 1.8x', impactLabel: '日内偏强', confidence: 0.92 },
      { key: 'e2', time: '2026-09-02T14:31:00Z', sourceId: 'terminal.source.aiPath', eventOrigin: 'mock_sample', eventTitle: '芯片出口相关新闻与板块波动同时出现', impactLabel: '中等风险', confidence: 0.78 },
      { key: 'e3', time: '2026-09-02T14:12:00Z', sourceId: 'terminal.source.riskAgent', eventOrigin: 'mock_sample', eventTitle: '半导体敞口超过模型护栏', impactLabel: '建议再平衡', confidence: 0.88 },
    ],
  },
  HK: {
    code: 'HK',
    labelId: 'terminal.market.hk',
    currency: 'HKD',
    timezone: 'Asia/Hong_Kong',
    benchmark: '恒生指数 HSI',
    status: 'Closed',
    updatedAt: '2026-09-02T08:08:44Z',
    indices: [
      { labelId: 'terminal.metric.hsi', value: 25921.3, change: 0.0031, changeFormat: 'percent', tone: 'positive' },
      { labelId: 'terminal.metric.hstech', value: 5812.77, change: 0.0094, changeFormat: 'percent', tone: 'positive' },
      { labelId: 'terminal.metric.volIndex', value: 19.2, change: -0.018, changeFormat: 'percent', tone: 'positive' },
      { labelId: 'terminal.metric.cnh', value: 7.12, change: -0.0004, changeFormat: 'percent', tone: 'neutral' },
    ],
    breadth: [
      { labelId: 'terminal.metric.advancers', value: 0.54, valueFormat: 'percent', tone: 'positive' },
      { labelId: 'terminal.metric.decliners', value: 0.39, valueFormat: 'percent', tone: 'negative' },
      { labelId: 'terminal.metric.delayedFields', value: 2, tone: 'warning' },
      { labelId: 'terminal.metric.signalQueue', value: 14, tone: 'accent' },
    ],
    breadthDataSource: mockSectionSource('delayed'),
    chartBars: [],
    sectors: [
      { labelId: 'terminal.sector.internet', value: 0.0108, valueFormat: 'percent', tone: 'positive' },
      { labelId: 'terminal.sector.property', value: -0.0082, valueFormat: 'percent', tone: 'negative' },
      { labelId: 'terminal.sector.banks', value: 0.0024, valueFormat: 'percent', tone: 'positive' },
      { labelId: 'terminal.sector.biotech', value: -0.0044, valueFormat: 'percent', tone: 'negative' },
      { labelId: 'terminal.sector.consumer', value: 0.0017, valueFormat: 'percent', tone: 'neutral' },
    ],
    sectorDataSource: mockSectionSource('delayed'),
    watchlist: [
      { key: '00700.HK', symbol: '00700.HK', nameId: 'terminal.stock.tencent', price: 421.6, changePercent: 0.0145, volume: 18200000, signalId: 'terminal.signal.trendUp', riskId: 'terminal.risk.normal' },
      { key: '09988.HK', symbol: '09988.HK', nameId: 'terminal.stock.alibabaHk', price: 96.35, changePercent: 0.0084, volume: 24100000, signalId: 'terminal.signal.momentumWatch', riskId: 'terminal.risk.normal' },
      { key: '03690.HK', symbol: '03690.HK', nameId: 'terminal.stock.meituan', price: 118.2, changePercent: -0.0102, volume: 13600000, signalId: 'terminal.signal.hold', riskId: 'terminal.risk.elevated' },
      { key: '00005.HK', symbol: '00005.HK', nameId: 'terminal.stock.hsbc', price: 92.1, changePercent: 0.0011, volume: 8800000, signalId: 'terminal.signal.quality', riskId: 'terminal.risk.low' },
    ],
    events: [
      { key: 'h1', time: '2026-09-02T07:58:00Z', sourceId: 'terminal.source.fastPath', eventOrigin: 'mock_sample', eventTitle: '恒生科技指数接近盘中高位', impactLabel: '短线偏强', confidence: 0.84 },
      { key: 'h2', time: '2026-09-02T06:36:00Z', sourceId: 'terminal.source.provider', eventOrigin: 'mock_sample', eventTitle: '部分港股小盘股基本面字段延迟', impactLabel: '数据提示', confidence: 1 },
      { key: 'h3', time: '2026-09-02T03:22:00Z', sourceId: 'terminal.source.aiPath', eventOrigin: 'mock_sample', eventTitle: '互联网新闻情绪改善', impactLabel: '中期偏正面', confidence: 0.73 },
    ],
  },
  CN: {
    code: 'CN',
    labelId: 'terminal.market.cn',
    currency: 'CNY',
    timezone: 'Asia/Shanghai',
    benchmark: '沪深300 CSI 300',
    status: 'Closed',
    updatedAt: '2026-09-02T07:01:21Z',
    indices: [
      { labelId: 'terminal.metric.csi300', value: 4112.65, change: -0.0018, changeFormat: 'percent', tone: 'negative' },
      { labelId: 'terminal.metric.sseComposite', value: 3286.4, change: 0.0005, changeFormat: 'percent', tone: 'positive' },
      { labelId: 'terminal.metric.chiNext', value: 2189.73, change: -0.0042, changeFormat: 'percent', tone: 'negative' },
      { labelId: 'terminal.metric.northbound', value: 2600000000, valueFormat: 'currency', tone: 'positive' },
    ],
    breadth: [
      { labelId: 'terminal.metric.advancers', value: 0.48, valueFormat: 'percent', tone: 'neutral' },
      { labelId: 'terminal.metric.decliners', value: 0.46, valueFormat: 'percent', tone: 'neutral' },
      { labelId: 'terminal.metric.limitUp', value: 41, tone: 'positive' },
      { labelId: 'terminal.metric.signalQueue', value: 19, tone: 'accent' },
    ],
    breadthDataSource: mockSectionSource('delayed'),
    chartBars: [],
    sectors: [
      { labelId: 'terminal.sector.evChain', value: 0.0076, valueFormat: 'percent', tone: 'positive' },
      { labelId: 'terminal.sector.brokerage', value: 0.0033, valueFormat: 'percent', tone: 'positive' },
      { labelId: 'terminal.sector.liquor', value: -0.0069, valueFormat: 'percent', tone: 'negative' },
      { labelId: 'terminal.sector.defense', value: -0.0028, valueFormat: 'percent', tone: 'negative' },
      { labelId: 'terminal.sector.aiHardware', value: 0.0112, valueFormat: 'percent', tone: 'positive' },
    ],
    sectorDataSource: mockSectionSource('delayed'),
    watchlist: [
      { key: '600519.SH', symbol: '600519.SH', nameId: 'terminal.stock.moutai', price: 1412, changePercent: -0.0064, volume: 2100000, signalId: 'terminal.signal.valueWatch', riskId: 'terminal.risk.normal' },
      { key: '300750.SZ', symbol: '300750.SZ', nameId: 'terminal.stock.catl', price: 214.88, changePercent: 0.0132, volume: 16900000, signalId: 'terminal.signal.momentumLong', riskId: 'terminal.risk.normal' },
      { key: '000001.SZ', symbol: '000001.SZ', nameId: 'terminal.stock.pab', price: 11.42, changePercent: 0.0018, volume: 75200000, signalId: 'terminal.signal.hold', riskId: 'terminal.risk.low' },
      { key: '600000.SH', symbol: '600000.SH', nameId: 'terminal.stock.spdb', price: 9.68, changePercent: -0.0021, volume: 38400000, signalId: 'terminal.signal.range', riskId: 'terminal.risk.normal' },
    ],
    events: [
      { key: 'c1', time: '2026-09-02T06:57:00Z', sourceId: 'terminal.source.fastPath', eventOrigin: 'mock_sample', eventTitle: 'AI 硬件组合相对强度扩大', impactLabel: '短线偏强', confidence: 0.81 },
      { key: 'c2', time: '2026-09-02T05:40:00Z', sourceId: 'terminal.source.marketRules', eventOrigin: 'mock_sample', eventTitle: '涨停标的已从入场模拟中排除', impactLabel: '执行约束', confidence: 1 },
      { key: 'c3', time: '2026-09-02T02:16:00Z', sourceId: 'terminal.source.aiPath', eventOrigin: 'mock_sample', eventTitle: '政策新闻映射到新能源车供应链', impactLabel: '中期偏正面', confidence: 0.69 },
    ],
  },
};

export const getToneClass = (tone?: string) => `terminal-tone-${tone ?? 'neutral'}`;

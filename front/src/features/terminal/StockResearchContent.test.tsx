import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';
import { App } from 'antd';
import { useEffect } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import enUS from '../../locales/en-US/terminal';
import zhCN from '../../locales/zh-CN/terminal';
import { marketSnapshots } from './mockData';
import { StockResearchContent } from './StockResearchContent';
import type { StockResearchSnapshot } from './types';

const localeState = vi.hoisted(() => ({ locale: 'zh-CN' }));
const chartLifecycle = vi.hoisted(() => ({ mount: vi.fn(), unmount: vi.fn() }));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: localeState.locale,
    formatMessage: (
      { id }: { id: string },
      values: Record<string, string | number> = {},
    ) => {
      const dictionary = localeState.locale === 'en-US' ? enUS : zhCN;
      return Object.entries(values).reduce(
        (text, [key, value]) => text.replaceAll(`{${key}}`, String(value)),
        dictionary[id as keyof typeof dictionary] ?? id,
      );
    },
  }),
}));

vi.mock('./StockKLineMockChart', () => ({
  StockKLineMockChart: () => {
    useEffect(() => {
      chartLifecycle.mount();
      return () => { chartLifecycle.unmount(); };
    }, []);
    return <div data-testid="stock-kline-chart" />;
  },
}));

const buildStockResearch = (
  fallbackActive: boolean,
): StockResearchSnapshot => ({
  market: 'US',
  symbol: 'AAPL',
  name: 'Apple',
  exchange: 'NASDAQ',
  currency: 'USD',
  timezone: 'America/New_York',
  sector: 'Technology',
  industry: 'Consumer Electronics',
  dataStatus: 'delayed',
  quote: {
    price: 220,
    change: 1,
    changePercent: 0.0045,
    volume: 1_000_000,
    turnover: 220_000_000,
    timestamp: '2026-10-15T01:00:00Z',
  },
  metricGroups: [
    {
      key: 'profitability',
      titleId: 'terminal.tab.fundamentals',
      metrics: [
        {
          labelId: 'terminal.metric.roeTtm',
          value: 0.18,
          valueFormat: 'percent',
        },
      ],
    },
    {
      key: 'valuation',
      titleId: 'terminal.tab.valuation',
      metrics: [{ labelId: 'terminal.metric.peTtm', value: 24.5 }],
    },
    {
      key: 'factors',
      titleId: 'terminal.metric.factorSnapshot',
      metrics: [
        {
          labelId: 'terminal.metric.momentum20d',
          value: 0.08,
          valueFormat: 'percent',
        },
      ],
    },
    {
      key: 'technical',
      titleId: 'terminal.tab.quant',
      metrics: [{ labelId: 'terminal.metric.rsi14', value: 58.4 }],
    },
    {
      key: 'cash-flow',
      titleId: 'terminal.metric.cashFlow',
      metrics: [
        {
          labelId: 'terminal.metric.fcfTtm',
          value: 1234.56,
          valueFormat: 'currency',
        },
      ],
    },
  ],
  fundamentalDataStatus: {
    source: 'database',
    completeness: 'complete',
    availableSections: [],
    missingSections: [],
  },
  quoteDataSource: {
    source: 'yahoo_finance',
    detail: 'quote',
    fallbackActive: false,
    dataStatus: 'delayed',
  },
  technicalDataSource: {
    source: 'quant_pipeline',
    detail: 'technical indicators',
    fallbackActive,
    dataStatus: fallbackActive ? 'unavailable' : 'delayed',
  },
  factorSnapshot: {
    momentum20d: null,
    trendStrength: null,
    volatility20d: null,
    qualityScore: null,
    compositeScore: null,
  },
  factorDataStatus: {
    source: 'quant_pipeline',
    completeness: 'computed',
    availableFactors: [],
    missingFactors: [],
  },
  quantSignals: [],
  signalDataStatus: {
    source: 'quant_pipeline',
    completeness: 'computed',
    signalCount: 0,
  },
  kline: {
    interval: '1d',
    dataStatus: fallbackActive ? 'unavailable' : 'delayed',
    bars: [],
  },
  klineDataSource: {
    source: fallbackActive ? 'mock_fallback' : 'yahoo_finance',
    detail: 'kline',
    fallbackActive,
    dataStatus: fallbackActive ? 'unavailable' : 'delayed',
  },
  riskFlags: [],
  summaryPoints: ['量化摘要'],
  summaryDataSource: {
    source: 'quant_pipeline',
    detail: 'research summary',
    fallbackActive: false,
    dataStatus: 'delayed',
  },
  direction: 'neutral',
});

const contentFor = (stockResearch: StockResearchSnapshot, snapshot = marketSnapshots[stockResearch.market], requestedSymbol?: string) => (
  <App>
    <StockResearchContent
      snapshot={snapshot}
      stockResearch={stockResearch}
      requestedSymbol={requestedSymbol}
      eventColumns={[{ key: 'eventTitle', dataIndex: 'eventTitle' }]}
    />
  </App>
);

describe('StockResearchContent request identity', () => {
  it.each((['US', 'HK', 'CN'] as const).flatMap(market =>
    ['zh-CN', 'en-US'].map(locale => ({ market, locale })),
  ))('withholds mismatched analysis and restores matching content in $market / $locale', ({ market, locale }) => {
    localeState.locale = locale;
    const symbol = { US: 'AAPL', HK: '00700.HK', CN: '600519.SH' }[market];
    const requested = { US: 'MSFT', HK: '09988.HK', CN: '600000.SH' }[market];
    const stock = { ...buildStockResearch(false), market, symbol };
    const view = render(contentFor(stock, marketSnapshots[market], requested));
    expect(screen.getByRole('status')).toHaveTextContent(`${market} / ${requested}`);
    expect(screen.getByRole('status')).toHaveTextContent(`${market} / ${symbol}`);
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument();
    expect(screen.queryByTestId('stock-kline-chart')).not.toBeInTheDocument();
    expect(screen.queryByText('量化摘要')).not.toBeInTheDocument();

    view.rerender(contentFor({ ...stock, symbol: requested }, marketSnapshots[market], requested));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.getByRole('tablist')).toBeInTheDocument();
    expect(screen.getByTestId('stock-kline-chart')).toBeInTheDocument();
    expect(screen.getByText('量化摘要')).toBeInTheDocument();

    // 已加载的正文也要在收到错误身份响应后移除，不能只拦截首次渲染。
    view.rerender(contentFor(stock, marketSnapshots[market], requested));
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByTestId('stock-kline-chart')).not.toBeInTheDocument();
  });

  it('withholds a different market even when the symbol text matches', () => {
    render(contentFor(buildStockResearch(false), marketSnapshots.HK, 'AAPL'));
    expect(screen.getByRole('status')).toHaveTextContent('HK / AAPL；返回标的：US / AAPL');
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument();
  });

  it('checks the market for default requests without rejecting a normal default symbol', () => {
    const stock = buildStockResearch(false);
    const view = render(contentFor(stock, marketSnapshots.HK));
    expect(screen.getByRole('status')).toHaveTextContent('HK / 默认标的');
    view.rerender(contentFor(stock, marketSnapshots.US));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.getByTestId('stock-kline-chart')).toBeInTheDocument();
  });
});

const renderContent = (fallbackActive = false) =>
  render(contentFor(buildStockResearch(fallbackActive)));

const getActiveSection = (titleId: keyof typeof zhCN): HTMLElement => {
  const dictionary = localeState.locale === 'en-US' ? enUS : zhCN;
  const section = within(screen.getByRole('tabpanel'))
    .getByText(dictionary[titleId])
    .closest('section');
  expect(section).not.toBeNull();
  return section as HTMLElement;
};

beforeEach(() => {
  localeState.locale = 'zh-CN';
  chartLifecycle.mount.mockClear();
  chartLifecycle.unmount.mockClear();
});

afterEach(cleanup);

describe('stock research quote status', () => {
  it('概览共享全宽边界，无风险时不留下空分栏', () => {
    const stock = buildStockResearch(false);
    const view = render(contentFor(stock));
    const overview = view.container.querySelector('.terminal-stock-overview');
    expect(overview?.children).toHaveLength(1);
    const primaryRow = overview?.firstElementChild;
    expect(primaryRow).toHaveClass('terminal-stock-primary-row');
    expect(primaryRow?.children).toHaveLength(2);
    expect(primaryRow?.children[0]).toHaveClass('terminal-panel');
    expect(primaryRow?.children[1]).toHaveClass('terminal-panel');
    view.rerender(contentFor({ ...stock, riskFlags: ['行情延迟'] }));
    expect(overview?.children).toHaveLength(1);
    expect(view.container.querySelector('.terminal-stock-risks')?.closest('.terminal-panel')).toBe(primaryRow?.children[1]);
    expect(screen.getByTestId('stock-kline-chart').closest('.terminal-stock-overview')).toBe(overview);
    expect(chartLifecycle.mount).toHaveBeenCalledTimes(1);
  });

  it('因子和技术指标共享主行，信号与现金流分别占行', () => {
    const { container } = renderContent();
    fireEvent.click(screen.getByRole('tab', { name: zhCN['terminal.tab.quant'] }));
    const workspace = container.querySelector('.terminal-stock-quant-workspace');
    expect(workspace?.children).toHaveLength(3);
    const row = workspace?.firstElementChild;
    expect(row).toHaveClass('terminal-stock-factor-row');
    expect(row?.children).toHaveLength(2);
    expect(getActiveSection('terminal.quant.factorSnapshot').parentElement).toBe(row);
    expect(getActiveSection('terminal.quant.technicalIndicators').parentElement).toBe(row);
    expect(getActiveSection('terminal.quant.quantSignals').parentElement).toBe(workspace);
    expect(getActiveSection('terminal.quant.cashFlowQuality').parentElement).toBe(workspace);
  });

  it.each([
    { symbol: 'MSFT' },
    { market: 'HK' as const },
  ])('remounts the chart when the research identity changes: %j', (change) => {
    const stock = buildStockResearch(false);
    const view = render(contentFor(stock));
    expect(chartLifecycle.mount).toHaveBeenCalledTimes(1);

    view.rerender(contentFor({ ...stock, ...change }));
    expect(chartLifecycle.unmount).toHaveBeenCalledTimes(1);
    expect(chartLifecycle.mount).toHaveBeenCalledTimes(2);
  });

  it('preserves the chart instance when quotes, bars or provenance refresh for the same target', () => {
    const stock = buildStockResearch(false);
    const view = render(contentFor(stock));
    const originalChart = screen.getByTestId('stock-kline-chart');
    view.rerender(contentFor({
      ...stock,
      quote: { ...stock.quote, price: 225 },
      kline: {
        ...stock.kline,
        bars: [{ timestamp: '2026-10-16T13:30:00Z', open: 220, high: 226, low: 219, close: 225, volume: 1000 }],
      },
      klineDataSource: { ...stock.klineDataSource, fallbackActive: true },
    }));
    expect(chartLifecycle.mount).toHaveBeenCalledTimes(1);
    expect(chartLifecycle.unmount).not.toHaveBeenCalled();
    expect(screen.getByTestId('stock-kline-chart')).toBe(originalChart);
  });

  it.each(['zh-CN', 'en-US'])('在 %s 展示并更新风险与数据限制，不残留上一标的提示', (locale) => {
    localeState.locale = locale;
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    const stock = buildStockResearch(false);
    stock.riskFlags = ['价格跌破 EMA 趋势线：trend_strength=-0.0490', '基本面为 Mock 样例'];
    const view = render(contentFor(stock));
    const region = screen.getByRole('region', { name: dictionary['terminal.stockResearch.riskTitle'] });
    expect(within(region).getAllByRole('listitem')).toHaveLength(2);
    expect(region).toHaveTextContent('trend_strength=-0.0490');
    expect(region).toHaveTextContent(dictionary['terminal.stockResearch.riskNote']);

    view.rerender(contentFor({ ...stock, symbol: 'MSFT', riskFlags: ['最新行情存在延迟'] }));
    expect(screen.queryByText(/trend_strength=-0.0490/)).not.toBeInTheDocument();
    expect(screen.getByText('最新行情存在延迟')).toBeInTheDocument();

    view.rerender(contentFor({ ...stock, riskFlags: [] }));
    expect(screen.queryByRole('region', { name: dictionary['terminal.stockResearch.riskTitle'] })).not.toBeInTheDocument();
  });

  it.each([
    'zh-CN',
    'en-US',
  ])('在 %s 中以文字同步展示三种状态，保留数值指标格式', (locale) => {
    localeState.locale = locale;
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    const first = buildStockResearch(false);
    const view = render(contentFor(first));

    for (const dataStatus of ['realtime', 'delayed', 'unavailable'] as const) {
      view.rerender(contentFor({ ...first, dataStatus }));
      const label = dictionary[`terminal.dataStatus.${dataStatus}`];
      const statusCard = screen
        .getByText(dictionary['terminal.metric.dataStatus'])
        .closest('.terminal-metric');
      expect(statusCard).not.toBeNull();
      expect(
        within(statusCard as HTMLElement).getByText(label),
      ).toHaveAttribute('title', label);
      expect(
        within(statusCard as HTMLElement).queryByText(/^[01]$/),
      ).not.toBeInTheDocument();
      expect(screen.getByText('$220.00')).toHaveAttribute('title', '$220.00');
      expect(screen.getByText('+0.45%')).toBeInTheDocument();
    }
  });
});

describe('stock research derived provenance', () => {
  it.each(['zh-CN', 'en-US'])('hides unavailable quote metrics and restores valid zero values in %s', locale => {
    localeState.locale = locale;
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    const first = buildStockResearch(false);
    const view = render(contentFor(first));
    const metricCard = (id: keyof typeof zhCN) => screen.getByText(dictionary[id]).closest('.terminal-metric') as HTMLElement;
    const metricIds = ['terminal.table.lastPrice', 'terminal.table.volume', 'terminal.metric.turnover'] as const;
    expect(within(metricCard(metricIds[0])).getByText('$220.00')).toBeInTheDocument();

    const unavailable = {
      ...first,
      quoteDataSource: { ...first.quoteDataSource, dataStatus: 'unavailable' as const },
    };
    view.rerender(contentFor(unavailable));
    for (const id of metricIds) {
      const card = metricCard(id);
      expect(within(card).getByText('--')).toHaveAttribute('title', dictionary['terminal.dataStatus.unavailable']);
      expect(card.querySelector('em')).toBeNull();
    }
    expect(screen.queryByText('$220.00')).not.toBeInTheDocument();
    expect(screen.queryByText('+0.45%')).not.toBeInTheDocument();
    expect(first.quote.price).toBe(220);

    // 总体与 K 线不可用不影响独立恢复的有效报价，零成交量也不代表缺失。
    view.rerender(contentFor({
      ...first,
      dataStatus: 'unavailable',
      klineDataSource: { ...first.klineDataSource, dataStatus: 'unavailable' },
      quote: { ...first.quote, changePercent: 0, volume: 0, turnover: 0 },
    }));
    expect(within(metricCard(metricIds[0])).getByText('$220.00')).toBeInTheDocument();
    expect(within(metricCard(metricIds[1])).getByText('0')).toBeInTheDocument();
    expect(within(metricCard(metricIds[2])).getByText('$0.00')).toBeInTheDocument();
    expect(screen.queryByText('--')).not.toBeInTheDocument();
  });

  it('retains explicitly labelled mock fallback quote values', () => {
    const first = buildStockResearch(false);
    render(contentFor({
      ...first,
      quoteDataSource: { source: 'mock_fallback', detail: 'sample quote', fallbackActive: true, dataStatus: 'unavailable' },
    }));
    expect(screen.getByText('$220.00')).toBeInTheDocument();
    expect(screen.getByText('+0.45%')).toBeInTheDocument();
    expect(screen.getByText('行情: Mock 回退')).toBeInTheDocument();
  });

  it('报价正常但 K 线回退时分别展示来源，且派生摘要继承回退状态', () => {
    const stock = buildStockResearch(true);
    stock.summaryDataSource = {
      ...stock.summaryDataSource,
      fallbackActive: true,
      dataStatus: 'unavailable',
    };
    stock.quoteDataSource = {
      ...stock.quoteDataSource,
      source: 'yahoo_finance',
      fallbackActive: false,
      dataStatus: 'delayed',
    };
    stock.riskFlags = ['K 线读取已回退到样例数据，不能作为真实交易依据。'];
    render(contentFor(stock));

    const quotePanel = screen.getByRole('heading', { name: 'AAPL / Apple' }).closest('section');
    expect(within(quotePanel as HTMLElement).getByText('行情: YahooFinance 公开行情')).toBeInTheDocument();
    expect(within(quotePanel as HTMLElement).getByText('K线: Mock 回退')).toBeInTheDocument();
    expect(screen.getByText('K 线读取已回退到样例数据，不能作为真实交易依据。')).toBeInTheDocument();
    const summaryPanel = screen.getByText(zhCN['terminal.panel.aiQuant']).closest('section');
    expect(within(summaryPanel as HTMLElement).getByText('Mock 回退')).toBeInTheDocument();
  });

  it('labels the AI and Quant summary as a Quant Pipeline result', () => {
    renderContent();

    const summaryPanel = screen
      .getByText(zhCN['terminal.panel.aiQuant'])
      .closest('section');
    expect(summaryPanel).not.toBeNull();
    expect(
      within(summaryPanel as HTMLElement).getByText(
        zhCN['terminal.dataSource.quantPipeline'],
      ),
    ).toBeInTheDocument();
  });

  it('propagates the K-line fallback state to technical indicators', () => {
    renderContent(true);
    fireEvent.click(screen.getByText(zhCN['terminal.tab.quant']));

    const technicalSection = screen
      .getByText(zhCN['terminal.quant.technicalIndicators'])
      .closest('section');
    expect(technicalSection).not.toBeNull();
    expect(
      within(technicalSection as HTMLElement).getByText('Mock 回退'),
    ).toBeInTheDocument();
  });
});

describe('stock research snapshot updates', () => {
  it.each(['zh-CN', 'en-US'])('labels market events without pretending to filter by symbol in %s', (locale) => {
    localeState.locale = locale;
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    const first = buildStockResearch(false);
    const view = render(contentFor(first));
    fireEvent.click(screen.getByRole('tab', { name: dictionary['terminal.tab.newsEvents'] }));
    const scopeText = (market: keyof typeof marketSnapshots, symbol: string) => dictionary['terminal.stockResearch.marketEventsScope']
      .replace('{market}', dictionary[marketSnapshots[market].labelId as keyof typeof dictionary])
      .replace('{symbol}', symbol);

    const firstSection = getActiveSection('terminal.stockResearch.marketEvents');
    expect(within(firstSection).getByText(scopeText('US', 'AAPL'))).toBeInTheDocument();
    expect(within(firstSection).getByText(`${dictionary['terminal.market.us']} / US`)).toBeInTheDocument();
    // 当前研究 AAPL 时仍保留市场事件中的 NVDA 样例，不根据标题猜测个股归属。
    expect(within(firstSection).getByText(marketSnapshots.US.events[0].eventTitle)).toBeInTheDocument();

    view.rerender(contentFor({ ...first, symbol: 'MSFT', name: 'Microsoft' }));
    const sameMarketSection = getActiveSection('terminal.stockResearch.marketEvents');
    expect(within(sameMarketSection).getByText(scopeText('US', 'MSFT'))).toBeInTheDocument();
    expect(within(sameMarketSection).queryByText(scopeText('US', 'AAPL'))).not.toBeInTheDocument();
    expect(within(sameMarketSection).getByText(marketSnapshots.US.events[0].eventTitle)).toBeInTheDocument();

    const next: StockResearchSnapshot = { ...first, market: 'HK', symbol: '00700.HK', name: 'Tencent', currency: 'HKD', timezone: 'Asia/Hong_Kong' };
    view.rerender(contentFor(next));
    const nextSection = getActiveSection('terminal.stockResearch.marketEvents');
    expect(within(nextSection).getByText(`${dictionary['terminal.market.hk']} / HK`)).toBeInTheDocument();
    expect(within(nextSection).getByText(scopeText('HK', '00700.HK'))).toBeInTheDocument();
    expect(within(nextSection).getByText(marketSnapshots.HK.events[0].eventTitle)).toBeInTheDocument();
    expect(within(nextSection).queryByText(marketSnapshots.US.events[0].eventTitle)).not.toBeInTheDocument();

    view.rerender(contentFor(next, { ...marketSnapshots.HK, events: [] }));
    const emptySection = getActiveSection('terminal.stockResearch.marketEvents');
    expect(within(emptySection).getByText(dictionary['terminal.stockResearch.emptyMarketEvents'].replace('{market}', dictionary['terminal.market.hk']))).toBeInTheDocument();
    expect(within(emptySection).queryByText(marketSnapshots.HK.events[0].eventTitle)).not.toBeInTheDocument();
    expect(within(emptySection).getByText(scopeText('HK', '00700.HK'))).toBeInTheDocument();
  });

  it.each([
    ['zh-CN', 'database'],
    ['zh-CN', 'quant_pipeline'],
    ['en-US', 'database'],
    ['en-US', 'quant_pipeline'],
  ])('shows a symbol-specific empty signal state in %s for %s', (locale, source) => {
    localeState.locale = locale;
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    const first = buildStockResearch(false);
    first.signalDataStatus = { source, completeness: source === 'database' ? 'complete' : 'computed', signalCount: 0 };
    const view = render(contentFor(first));
    fireEvent.click(screen.getByRole('tab', { name: dictionary['terminal.tab.quant'] }));
    const emptyMessage = (symbol: string) => dictionary['terminal.stockResearch.emptySignals'].replace('{symbol}', symbol);
    const firstSection = getActiveSection('terminal.quant.quantSignals');
    expect(within(firstSection).getByText(emptyMessage('AAPL'))).toBeInTheDocument();
    const statusId = source === 'database' ? 'terminal.signalDataStatus.database' : 'terminal.signalDataStatus.computed';
    expect(within(firstSection).getByText(dictionary[statusId].replace('{count}', '0'))).toBeInTheDocument();

    const next: StockResearchSnapshot = {
      ...first, symbol: 'MSFT', name: 'Microsoft',
      quantSignals: [{ key: 'msft-signal', code: 'momentum', title: 'MSFT_SIGNAL', direction: 'positive', severity: 'info', score: 0.25, evidence: ['MSFT_EVIDENCE'] }],
      signalDataStatus: { ...first.signalDataStatus, signalCount: 1 },
    };
    view.rerender(contentFor(next));
    expect(within(getActiveSection('terminal.quant.quantSignals')).getByText('MSFT_SIGNAL')).toBeInTheDocument();
    expect(within(getActiveSection('terminal.quant.quantSignals')).queryByText(emptyMessage('AAPL'))).not.toBeInTheDocument();
    expect(within(getActiveSection('terminal.quant.quantSignals')).queryByText(emptyMessage('MSFT'))).not.toBeInTheDocument();

    view.rerender(contentFor({ ...next, quantSignals: [], signalDataStatus: { ...next.signalDataStatus, signalCount: 0 } }));
    const nextSection = getActiveSection('terminal.quant.quantSignals');
    expect(within(nextSection).getByText(emptyMessage('MSFT'))).toBeInTheDocument();
    expect(within(nextSection).queryByText(emptyMessage('AAPL'))).not.toBeInTheDocument();
    expect(within(nextSection).queryByText('MSFT_SIGNAL')).not.toBeInTheDocument();
  });

  it.each(([
    ['terminal.tab.fundamentals', 'terminal.tab.fundamentals', 'terminal.fundamentalDataStatus.databaseComplete'],
    ['terminal.tab.valuation', 'terminal.tab.valuation', 'terminal.fundamentalDataStatus.databaseComplete'],
    ['terminal.tab.quant', 'terminal.quant.factorSnapshot', 'terminal.factorDataStatus.computed'],
    ['terminal.tab.quant', 'terminal.quant.technicalIndicators', 'terminal.dataSource.quantPipeline'],
    ['terminal.tab.quant', 'terminal.quant.quantSignals', 'terminal.signalDataStatus.computed'],
    ['terminal.tab.quant', 'terminal.quant.cashFlowQuality', 'terminal.fundamentalDataStatus.databaseComplete'],
  ] as const).flatMap(([tabId, sectionId, statusId]) =>
    ['zh-CN', 'en-US'].map(locale => ({ locale, tabId, sectionId, statusId })),
  ))('keeps $sectionId and its source in a single header in $locale', ({ locale, tabId, sectionId, statusId }) => {
    localeState.locale = locale;
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    renderContent();
    fireEvent.click(screen.getByRole('tab', { name: dictionary[tabId] }));
    const section = getActiveSection(sectionId);
    const header = section.querySelector('.terminal-quant-section-header') as HTMLElement;
    expect(header).not.toBeNull();
    expect(section.querySelectorAll('.terminal-quant-section-header')).toHaveLength(1);
    expect(within(header).getByRole('heading', { name: dictionary[sectionId], level: 2 })).toBeInTheDocument();
    expect(within(header).getByText(dictionary[statusId].replace('{count}', '0'))).toBeInTheDocument();
    expect(section.querySelector('.terminal-panel-header')).toBeNull();
  });

  it.each(([
    ['terminal.tab.fundamentals', 'terminal.tab.fundamentals', 'profitability', '+18.00%', '0.00%'],
    ['terminal.tab.valuation', 'terminal.tab.valuation', 'valuation', '24.5', '0'],
    ['terminal.tab.quant', 'terminal.quant.factorSnapshot', 'factors', '+8.00%', '0.00%'],
    ['terminal.tab.quant', 'terminal.quant.technicalIndicators', 'technical', '58.4', '0'],
    ['terminal.tab.quant', 'terminal.quant.cashFlowQuality', 'cash-flow', '$1,234.56', '$0.00'],
  ] as const).flatMap(([tabId, sectionId, group, previousValue, zeroValue]) =>
    ['zh-CN', 'en-US'].map(locale => ({ locale, tabId, sectionId, group, previousValue, zeroValue })),
  ))('shows missing and empty $group groups in $locale, then restores valid zero values', ({
    locale, tabId, sectionId, group, previousValue, zeroValue,
  }) => {
    localeState.locale = locale;
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    const first = buildStockResearch(false);
    const view = render(contentFor(first));
    fireEvent.click(screen.getByRole('tab', { name: dictionary[tabId] }));
    expect(within(getActiveSection(sectionId)).getByText(previousValue)).toBeInTheDocument();

    for (const metricGroups of [
      first.metricGroups.filter(item => item.key !== group),
      first.metricGroups.map(item => item.key === group ? { ...item, metrics: [] } : item),
    ]) {
      view.rerender(contentFor({ ...first, symbol: 'MSFT', name: 'Microsoft', metricGroups }));
      const section = getActiveSection(sectionId);
      expect(within(section).getByText(dictionary['terminal.stockResearch.emptyMetrics'])).toBeInTheDocument();
      expect(within(section).queryByText(previousValue)).not.toBeInTheDocument();
      expect(section.querySelector('.terminal-metric')).toBeNull();
      expect(screen.getByRole('tab', { name: dictionary[tabId] })).toHaveAttribute('aria-selected', 'true');
    }

    view.rerender(contentFor({
      ...first,
      symbol: 'MSFT',
      name: 'Microsoft',
      metricGroups: first.metricGroups.map(item => item.key === group
        ? { ...item, metrics: item.metrics.map(metric => ({ ...metric, value: 0 })) }
        : item),
    }));
    const section = getActiveSection(sectionId);
    expect(within(section).getByText(zeroValue)).toBeInTheDocument();
    expect(within(section).queryByText(dictionary['terminal.stockResearch.emptyMetrics'])).not.toBeInTheDocument();
  });

  it('replaces signal rows, evidence and provenance for a new stock, including an empty result', () => {
    const first = buildStockResearch(false);
    first.quantSignals = [{ key: 'aapl-signal', code: 'trend', title: 'AAPL_SIGNAL', direction: 'negative', severity: 'warning', score: 0.87, evidence: ['AAPL_EVIDENCE'] }];
    first.signalDataStatus = { source: 'database', completeness: 'complete', signalCount: 1 };
    const view = render(contentFor(first));
    fireEvent.click(screen.getByRole('tab', { name: zhCN['terminal.tab.quant'] }));
    expect(within(getActiveSection('terminal.quant.quantSignals')).getByText('AAPL_SIGNAL')).toBeInTheDocument();
    expect(within(getActiveSection('terminal.quant.quantSignals')).getByText('数据库信号 1')).toBeInTheDocument();

    const next: StockResearchSnapshot = {
      ...first, symbol: 'MSFT', name: 'Microsoft',
      quantSignals: [{ key: 'msft-signal', code: 'momentum', title: 'MSFT_SIGNAL', direction: 'positive', severity: 'info', score: 0.25, evidence: ['MSFT_EVIDENCE'] }],
      signalDataStatus: { source: 'quant_pipeline', completeness: 'computed', signalCount: 1 },
    };
    view.rerender(contentFor(next));
    const section = getActiveSection('terminal.quant.quantSignals');
    expect(within(section).getByText('MSFT_SIGNAL')).toBeInTheDocument();
    expect(within(section).getByText('MSFT_EVIDENCE')).toBeInTheDocument();
    expect(within(section).queryByText(/AAPL_/)).not.toBeInTheDocument();
    expect(within(section).getByText('即时计算信号 1')).toBeInTheDocument();
    expect(within(section).queryByText('数据库信号 1')).not.toBeInTheDocument();

    view.rerender(contentFor({ ...next, quantSignals: [], signalDataStatus: { ...next.signalDataStatus, signalCount: 0 } }));
    const emptySection = getActiveSection('terminal.quant.quantSignals');
    expect(within(emptySection).queryByText(/MSFT_/)).not.toBeInTheDocument();
    expect(within(emptySection).getByText('即时计算信号 0')).toBeInTheDocument();
  });

  it('updates the symbol, market currency, price and quote source together', () => {
    const first = buildStockResearch(false);
    const view = render(contentFor(first));
    expect(
      screen.getByRole('heading', { name: 'AAPL / Apple' }),
    ).toBeInTheDocument();
    expect(screen.getByText('$220.00')).toBeInTheDocument();

    const next: StockResearchSnapshot = {
      ...first,
      market: 'CN',
      symbol: '600519.SH',
      name: '贵州茅台',
      currency: 'CNY',
      timezone: 'Asia/Shanghai',
      exchange: 'SSE',
      quote: { ...first.quote, price: 1599.56, changePercent: -0.0123 },
      direction: 'negative',
      quoteDataSource: { ...first.quoteDataSource, source: 'database' },
    };
    view.rerender(contentFor(next));

    expect(
      screen.getByRole('heading', { name: '600519.SH / 贵州茅台' }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: 'AAPL / Apple' }),
    ).not.toBeInTheDocument();
    expect(screen.getByText('¥1,599.56')).toHaveAttribute('title', '¥1,599.56');
    expect(screen.queryByText('$220.00')).not.toBeInTheDocument();
    expect(screen.getByText('-1.23%')).toHaveClass('terminal-tone-negative');
    expect(screen.getByText('行情: 数据库')).toBeInTheDocument();
    expect(
      screen.queryByText('行情: YahooFinance 公开行情'),
    ).not.toBeInTheDocument();
  });

  it.each([
    {
      tabId: 'terminal.tab.fundamentals',
      sectionId: 'terminal.tab.fundamentals',
      group: 'profitability',
      value: '+18.00%',
      zero: '0.00%',
      missingStatus: '数据库部分缺失 1',
      restoredStatus: '数据库完整',
      source: 'database',
    },
    {
      tabId: 'terminal.tab.valuation',
      sectionId: 'terminal.tab.valuation',
      group: 'valuation',
      value: '24.5',
      zero: '0',
      missingStatus: '数据库部分缺失 1',
      restoredStatus: '数据库完整',
      source: 'database',
    },
    {
      tabId: 'terminal.tab.quant',
      sectionId: 'terminal.quant.factorSnapshot',
      group: 'factors',
      value: '+8.00%',
      zero: '0.00%',
      missingStatus: '数据库因子缺失 1',
      restoredStatus: '数据库因子',
      source: 'database',
    },
    {
      tabId: 'terminal.tab.quant',
      sectionId: 'terminal.quant.technicalIndicators',
      group: 'technical',
      value: '58.4',
      zero: '0',
      missingStatus: 'Mock 回退',
      restoredStatus: '即时 Quant Pipeline',
      source: 'quant_pipeline',
    },
    {
      tabId: 'terminal.tab.quant',
      sectionId: 'terminal.quant.cashFlowQuality',
      group: 'cash-flow',
      value: '$1,234.56',
      zero: '$0.00',
      missingStatus: '数据库部分缺失 1',
      restoredStatus: '数据库完整',
      source: 'database',
    },
  ] as const)('replaces $group values and source status without leaving the selected tab', ({
    tabId,
    sectionId,
    group,
    value,
    zero,
    missingStatus,
    restoredStatus,
    source,
  }) => {
    const first = buildStockResearch(false);
    const view = render(contentFor(first));
    fireEvent.click(screen.getByRole('tab', { name: zhCN[tabId] }));
    expect(
      within(getActiveSection(sectionId)).getByText(value),
    ).toBeInTheDocument();

    // 在同一个组件实例上替换股票快照，覆盖用户停留在当前 Tab 的情况。
    const missing: StockResearchSnapshot = {
      ...buildStockResearch(true),
      symbol: 'MSFT',
      name: 'Microsoft',
      metricGroups: first.metricGroups.map((item) =>
        item.key === group
          ? {
              ...item,
              metrics: item.metrics.map((metric) => ({
                ...metric,
                value: 0,
                change: 0.1,
                changeFormat: 'percent',
                dataSource: { source, status: 'unavailable' },
              })),
            }
          : item,
      ),
      fundamentalDataStatus: {
        source: 'database',
        completeness: 'partial',
        availableSections: [],
        missingSections: [group],
      },
      factorDataStatus: {
        source: 'database',
        completeness: 'partial',
        availableFactors: [],
        missingFactors: ['momentum_20d'],
      },
    };
    view.rerender(contentFor(missing));

    const missingSection = getActiveSection(sectionId);
    expect(screen.getByRole('tab', { name: zhCN[tabId] })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(within(missingSection).getByText('--')).toHaveAttribute(
      'title',
      '数据不可用',
    );
    expect(within(missingSection).queryByText(value)).not.toBeInTheDocument();
    expect(within(missingSection).getByText(missingStatus)).toBeInTheDocument();
    expect(missingSection.querySelector('em')).not.toBeInTheDocument();

    const restored: StockResearchSnapshot = {
      ...first,
      symbol: 'MSFT',
      name: 'Microsoft',
      metricGroups: first.metricGroups.map((item) => ({
        ...item,
        metrics: item.metrics.map((metric) => ({ ...metric, value: 0 })),
      })),
      factorDataStatus: {
        ...first.factorDataStatus,
        source: 'database',
        completeness: 'complete',
      },
    };
    view.rerender(contentFor(restored));

    const restoredSection = getActiveSection(sectionId);
    expect(within(restoredSection).getByText(zero)).toHaveAttribute(
      'title',
      zero,
    );
    expect(within(restoredSection).queryByText('--')).not.toBeInTheDocument();
    expect(
      within(restoredSection).getByText(restoredStatus),
    ).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: zhCN[tabId] })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  });

  it('replaces the previous stock summary and its source badge', () => {
    const first = buildStockResearch(false);
    const view = render(contentFor(first));
    const firstPanel = getActiveSection('terminal.panel.aiQuant');
    expect(within(firstPanel).getByText('量化摘要')).toBeInTheDocument();
    expect(
      within(firstPanel).getByText('即时 Quant Pipeline'),
    ).toBeInTheDocument();

    view.rerender(
      contentFor({
        ...first,
        symbol: 'MSFT',
        name: 'Microsoft',
        summaryPoints: ['新标的量化摘要'],
        summaryDataSource: {
          source: 'mock_fallback',
          detail: '新标的研究数据不可用',
          fallbackActive: true,
          dataStatus: 'unavailable',
        },
      }),
    );

    const nextPanel = getActiveSection('terminal.panel.aiQuant');
    expect(within(nextPanel).getByText('新标的量化摘要')).toBeInTheDocument();
    expect(within(nextPanel).getByText('Mock 回退')).toBeInTheDocument();
    expect(within(nextPanel).queryByText('量化摘要')).not.toBeInTheDocument();
    expect(
      within(nextPanel).queryByText('即时 Quant Pipeline'),
    ).not.toBeInTheDocument();
  });
});

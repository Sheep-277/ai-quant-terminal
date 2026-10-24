import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import enUSNetwork from '../../locales/en-US/network';
import enUS from '../../locales/en-US/terminal';
import zhCNNetwork from '../../locales/zh-CN/network';
import zhCN from '../../locales/zh-CN/terminal';
import type {
  PaperOrderCreateResponse,
  PreTradeRiskCheckResponse,
} from './apiTypes';
import { marketSnapshots } from './mockData';
import type { StockResearchTarget } from './StockSymbolSelector';
import {
  TerminalMainContent,
  type TerminalMainContentProps,
} from './TerminalMainContent';
import type {
  BacktestSnapshot,
  MarketCode,
  PortfolioSnapshot,
  StockResearchSnapshot,
} from './types';

const componentMocks = vi.hoisted(() => ({
  locale: 'zh-CN',
  portfolioContent: vi.fn(),
  stockResearchContent: vi.fn(),
  stockSymbolSelector: vi.fn(),
  backtestContent: vi.fn(),
}));

vi.mock('./BacktestContent', () => ({
  BacktestContent: (props: { backtest: BacktestSnapshot }) => {
    componentMocks.backtestContent(props);
    return <div data-testid="backtest-content">{props.backtest.backtestId}</div>;
  },
}));

vi.mock('@ant-design/icons', () => ({
  LoadingOutlined: () => null,
  ReloadOutlined: () => null,
}));

vi.mock('./TerminalRightRail', () => ({
  StrategyGuardrails: () => null,
}));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: componentMocks.locale,
    formatMessage: (
      { id, defaultMessage }: { id?: string; defaultMessage?: string },
      values?: Record<string, string | number>,
    ) => {
      const dictionary =
        componentMocks.locale === 'en-US'
          ? { ...enUS, ...enUSNetwork }
          : { ...zhCN, ...zhCNNetwork };
      let message =
        (id && dictionary[id as keyof typeof dictionary]) ||
        defaultMessage ||
        id ||
        '';
      for (const [key, value] of Object.entries(values ?? {})) {
        message = message.replace(`{${key}}`, String(value));
      }
      return message;
    },
  }),
}));

vi.mock('./PortfolioContent', () => ({
  PortfolioContent: (props: {
    portfolio: PortfolioSnapshot;
    paperOrderReceipt?: PaperOrderCreateResponse;
    preTradeRiskCheckReceipt?: PreTradeRiskCheckResponse;
  }) => {
    componentMocks.portfolioContent(props);
    return (
      <div data-testid="portfolio-content">
        {props.portfolio.account.accountId}
      </div>
    );
  },
}));

vi.mock('./StockResearchContent', () => ({
  StockResearchContent: (
    props: Required<
      Pick<
        TerminalMainContentProps,
        'snapshot' | 'stockResearch' | 'eventColumns'
      >
    >,
  ) => {
    componentMocks.stockResearchContent(props);
    return (
      <div data-testid="stock-research-content">
        {props.stockResearch.symbol}
      </div>
    );
  },
}));

vi.mock('./StockSymbolSelector', () => ({
  StockSymbolSelector: (props: { researchTarget?: StockResearchTarget }) => {
    componentMocks.stockSymbolSelector(props);
    // 非受控输入用于观察挂载边界；选择器本身的校验和提交由独立测试覆盖。
    return <input data-testid="stock-symbol-selector" aria-label="research-symbol-test" defaultValue="" />;
  },
}));

const buildStockResearch = (
  market: MarketCode,
  symbol: string,
): StockResearchSnapshot => ({
  market,
  symbol,
  name: symbol,
  exchange: market === 'HK' ? 'HKEX' : market === 'US' ? 'NASDAQ' : 'SSE',
  currency: marketSnapshots[market].currency,
  timezone: marketSnapshots[market].timezone,
  sector: 'Technology',
  industry: 'Research Fixture',
  dataStatus: 'delayed',
  quote: {
    price: 100,
    change: 1,
    changePercent: 0.01,
    volume: 1_000_000,
    turnover: 100_000_000,
    timestamp: '2026-10-19T01:30:00Z',
  },
  metricGroups: [],
  fundamentalDataStatus: {
    source: 'database',
    completeness: 'complete',
    availableSections: [],
    missingSections: [],
  },
  quoteDataSource: {
    source: 'yahoo_finance',
    detail: 'YahooFinance 公开行情',
    fallbackActive: false,
    dataStatus: 'delayed',
  },
  technicalDataSource: {
    source: 'quant_pipeline',
    detail: 'K线计算结果',
    fallbackActive: false,
    dataStatus: 'delayed',
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
  kline: { interval: '1d', dataStatus: 'unavailable', bars: [] },
  klineDataSource: {
    source: 'mock_fallback',
    detail: '历史K线读取失败',
    fallbackActive: true,
    dataStatus: 'unavailable',
  },
  riskFlags: [],
  summaryPoints: [],
  summaryDataSource: {
    source: 'quant_pipeline',
    detail: '确定性量化摘要',
    fallbackActive: false,
    dataStatus: 'delayed',
  },
  direction: 'neutral',
});

const portfolio: PortfolioSnapshot = {
  market: 'HK',
  timestamp: '2026-10-16T02:00:00Z',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  dataMode: 'paper',
  account: {
    accountId: 'paper-hk-001',
    market: 'HK',
    currency: 'HKD',
    nav: 100000,
    cash: 25000,
    marketValue: 75000,
    dailyPnl: 800,
    totalPnl: 5000,
    totalReturn: 0.05,
    updatedAt: '2026-10-16T02:00:00Z',
  },
  accountMetrics: [],
  positions: [],
  orders: [],
  riskMetrics: [],
  riskFlags: [],
};

const riskReceipt: PreTradeRiskCheckResponse = {
  account_id: 'paper-hk-001',
  market: 'HK',
  symbol: '00700.HK',
  side: 'buy',
  decision: 'approved',
  risk_checked: true,
  checked_at: '2026-10-16T02:00:00Z',
  projected_order_value: 610,
  projected_cash: 24390,
  projected_cash_weight: 0.2439,
  projected_position_weight: 0.6161,
  reasons: [],
};

const orderReceipt: PaperOrderCreateResponse = {
  order_id: 'paper-order-001',
  account_id: 'paper-hk-001',
  market: 'HK',
  symbol: '00700.HK',
  side: 'buy',
  quantity: 1,
  limit_price: 610,
  status: 'submitted',
  submitted_at: '2026-10-16T02:00:00Z',
  currency: 'HKD',
  risk_checked: true,
  risk_decision: 'approved',
  risk_reason_codes: [],
  risk_reasons: [],
  data_status: 'delayed',
  fallback_active: false,
  fallback_reason: null,
  storage_source: 'database',
};

const renderMainContent = (
  props: Partial<{
    portfolio: PortfolioSnapshot;
    paperOrderReceipt: PaperOrderCreateResponse;
    preTradeRiskCheckReceipt: PreTradeRiskCheckResponse;
  }> = {},
) =>
  render(
    <App>
      <TerminalMainContent
        pageKey="portfolio"
        snapshot={marketSnapshots.HK}
        eventColumns={[]}
        {...props}
      />
    </App>,
  );

const stockMainContent = (
  market: MarketCode,
  stockResearch?: StockResearchSnapshot,
  stockResearchQueryState?: TerminalMainContentProps['stockResearchQueryState'],
) => (
  <App>
    <TerminalMainContent
      pageKey="stock-research"
      snapshot={marketSnapshots[market]}
      stockResearch={stockResearch}
      stockResearchQueryState={stockResearchQueryState}
      eventColumns={[]}
    />
  </App>
);

beforeEach(() => {
  componentMocks.locale = 'zh-CN';
  componentMocks.portfolioContent.mockClear();
  componentMocks.stockResearchContent.mockClear();
  componentMocks.stockSymbolSelector.mockClear();
  componentMocks.backtestContent.mockClear();
});

afterEach(() => {
  cleanup();
});

describe('TerminalMainContent backtest read states', () => {
  const backtest: BacktestSnapshot = {
    backtestId: 'cached-backtest-001', strategyId: 'strategy-001', market: 'HK',
    status: 'completed', dataMode: 'historical', timestamp: '2026-10-16T02:05:00Z',
    timezone: 'Asia/Hong_Kong', currency: 'HKD', benchmark: 'Hang Seng TECH',
    startDate: '2025-01-01', endDate: '2025-12-31',
    performanceMetrics: [], equityCurve: [], trades: [], assumptions: [],
  };
  const content = (query: { isError: boolean; isFetching: boolean; refetch: () => Promise<unknown> }, data?: BacktestSnapshot) => (
    <App><TerminalMainContent pageKey="backtest" snapshot={marketSnapshots.HK} eventColumns={[]}
      backtest={data} backtestQueryState={query} /></App>
  );

  it.each(['zh-CN', 'en-US'])('首次失败不继续转圈，重试和恢复保持当前市场：%s', (locale) => {
    componentMocks.locale = locale;
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    const network = locale === 'en-US' ? enUSNetwork : zhCNNetwork;
    const query = { isError: false, isFetching: true, refetch: vi.fn().mockResolvedValue(undefined) };
    const view = render(content(query));
    expect(screen.getByText(dictionary['terminal.panel.backtestDataPreparing'])).toBeInTheDocument();
    view.rerender(content({ ...query, isError: true, isFetching: false }));
    expect(screen.getByRole('alert')).toHaveTextContent(dictionary['terminal.backtest.readFailed']);
    expect(view.container.querySelector('.ant-spin')).toBeNull();
    expect(screen.queryByTestId('backtest-content')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: network['app.error.retry'] }));
    expect(query.refetch).toHaveBeenCalledTimes(1);
    view.rerender(content({ ...query, isError: true }));
    expect(screen.getByRole('button', { name: network['app.error.retry'] })).toBeDisabled();
    view.rerender(content(query));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    view.rerender(content({ ...query, isFetching: false }, backtest));
    expect(screen.getByTestId('backtest-content')).toHaveTextContent(backtest.backtestId);
    expect(componentMocks.backtestContent).toHaveBeenLastCalledWith(expect.objectContaining({ backtest }));
  });

  it('缓存刷新失败保留结果与原始时间，重试不卸载结果', () => {
    const query = { isError: false, isFetching: false, refetch: vi.fn().mockResolvedValue(undefined) };
    const view = render(content(query, backtest));
    const result = screen.getByTestId('backtest-content');
    view.rerender(content({ ...query, isError: true }, backtest));
    expect(screen.getByRole('alert')).toHaveClass('ant-alert-warning');
    expect(screen.getByRole('alert')).toHaveTextContent('2026/10/16 10:05:00');
    expect(screen.getByTestId('backtest-content')).toBe(result);
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(query.refetch).toHaveBeenCalledTimes(1);
    view.rerender(content({ ...query, isError: true, isFetching: true }, backtest));
    expect(screen.getByTestId('backtest-content')).toBe(result);
    expect(screen.getByRole('button', { name: '重试' })).toBeDisabled();
    expect(screen.getByRole('alert')).toHaveTextContent('2026/10/16 10:05:00');
    view.rerender(content(query, backtest));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});

describe('TerminalMainContent portfolio branch', () => {
  it('组合数据就绪时传递组合和两类回执', () => {
    renderMainContent({
      portfolio,
      paperOrderReceipt: orderReceipt,
      preTradeRiskCheckReceipt: riskReceipt,
    });

    expect(
      screen.getByText(zhCN['terminal.dataSourceStrip.title']),
    ).toBeInTheDocument();
    expect(screen.getByTestId('portfolio-content')).toHaveTextContent(
      'paper-hk-001',
    );
    expect(screen.queryByTestId('stock-symbol-selector')).not.toBeInTheDocument();
    expect(componentMocks.portfolioContent).toHaveBeenCalledWith({
      portfolio,
      paperOrderReceipt: orderReceipt,
      preTradeRiskCheckReceipt: riskReceipt,
    });
  });

  it('组合数据未就绪时只显示当前市场的准备状态', () => {
    renderMainContent();

    expect(screen.getByText('组合数据准备中')).toBeInTheDocument();
    expect(
      screen.getByText(zhCN['terminal.page.portfolio.title']),
    ).toBeInTheDocument();
    expect(screen.getByText(/HK.*恒生指数 HSI/)).toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-content')).not.toBeInTheDocument();
    expect(componentMocks.portfolioContent).not.toHaveBeenCalled();
  });
});

describe('TerminalMainContent stock research branch', () => {
  it('passes the submitted symbol separately from the returned research symbol', () => {
    const stock = buildStockResearch('US', 'AAPL');
    render(
      <App>
        <TerminalMainContent pageKey="stock-research" snapshot={marketSnapshots.US} eventColumns={[]}
          stockResearch={stock} requestedStockSymbol="MSFT" />
      </App>,
    );
    expect(componentMocks.stockResearchContent).toHaveBeenLastCalledWith(expect.objectContaining({
      requestedSymbol: 'MSFT', stockResearch: stock,
    }));
    expect(screen.getByTestId('stock-symbol-selector')).toBeInTheDocument();
  });
  it.each((['US', 'HK', 'CN'] as const).flatMap(market =>
    ['zh-CN', 'en-US'].map(locale => ({ market, locale })),
  ))('keeps one search instance through loading, failure and recovery in $market / $locale', ({ market, locale }) => {
    componentMocks.locale = locale;
    const dictionary = locale === 'en-US' ? enUSNetwork : zhCNNetwork;
    const query = { isError: false, isFetching: true, refetch: vi.fn().mockResolvedValue(undefined) };
    const view = render(stockMainContent(market, undefined, query));
    const input = screen.getByTestId('stock-symbol-selector');
    expect(screen.getAllByTestId('stock-symbol-selector')).toHaveLength(1);
    expect(input).toBeEnabled();
    fireEvent.change(input, { target: { value: 'USER_DRAFT' } });

    view.rerender(stockMainContent(market, undefined, { ...query, isError: true, isFetching: false }));
    expect(screen.getByTestId('stock-symbol-selector')).toBe(input);
    expect(input).toHaveValue('USER_DRAFT');
    fireEvent.click(screen.getByRole('button', { name: dictionary['app.error.retry'] }));
    expect(query.refetch).toHaveBeenCalledTimes(1);
    view.rerender(stockMainContent(market, undefined, query));
    expect(screen.getByTestId('stock-symbol-selector')).toBe(input);
    expect(input).toHaveValue('USER_DRAFT');

    const symbol = market === 'US' ? 'NVDA' : market === 'HK' ? '00700.HK' : '600519.SH';
    const stock = buildStockResearch(market, symbol);
    view.rerender(stockMainContent(market, stock, { ...query, isFetching: false }));
    expect(screen.getAllByTestId('stock-symbol-selector')).toHaveLength(1);
    expect(screen.getByTestId('stock-symbol-selector')).toBe(input);
    expect(input).toHaveValue('USER_DRAFT');
    expect(componentMocks.stockSymbolSelector).toHaveBeenLastCalledWith({ researchTarget: {
      market, symbol, quoteTimestamp: stock.quote.timestamp, timezone: stock.timezone,
    } });

    view.rerender(stockMainContent(market, stock, { ...query, isError: true, isFetching: false }));
    expect(screen.getByTestId('stock-symbol-selector')).toBe(input);
    expect(input).toBeEnabled();
    expect(input).toHaveValue('USER_DRAFT');
  });

  it('首次读取失败时显示错误和重试按钮，不继续展示准备状态', () => {
    const query = {
      isError: true,
      isFetching: false,
      refetch: vi.fn().mockResolvedValue(undefined),
    };
    const { container } = render(stockMainContent('HK', undefined, query));

    expect(screen.getByRole('alert')).toHaveTextContent(
      zhCN['terminal.stockResearch.refreshFailed'],
    );
    expect(screen.getByRole('alert')).toHaveTextContent(
      zhCN['terminal.dataStatus.unavailable'],
    );
    expect(screen.getByRole('button', { name: '重试' })).toBeEnabled();
    expect(container.querySelector('.ant-spin')).not.toBeInTheDocument();
    expect(
      screen.queryByText(zhCN['terminal.panel.stockDataPreparing']),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId('stock-research-content'),
    ).not.toBeInTheDocument();
    expect(componentMocks.stockResearchContent).not.toHaveBeenCalled();
  });

  it('重试只调用当前查询，读取期间禁用按钮，成功后恢复研究内容', () => {
    const query = {
      isError: true,
      isFetching: false,
      refetch: vi.fn().mockResolvedValue(undefined),
    };
    const view = render(stockMainContent('HK', undefined, query));
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(query.refetch).toHaveBeenCalledTimes(1);

    view.rerender(
      stockMainContent('HK', undefined, { ...query, isFetching: true }),
    );
    const retryButton = screen.getByRole('button', { name: '重试' });
    expect(retryButton).toBeDisabled();
    fireEvent.click(retryButton);
    expect(query.refetch).toHaveBeenCalledTimes(1);

    view.rerender(
      stockMainContent('HK', undefined, {
        ...query,
        isError: false,
        isFetching: true,
      }),
    );
    expect(
      screen.getByText(zhCN['terminal.panel.stockDataPreparing']),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: '重试' }),
    ).not.toBeInTheDocument();

    const stock = buildStockResearch('HK', '00700.HK');
    view.rerender(stockMainContent('HK', stock, { ...query, isError: false }));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: '重试' }),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId('stock-research-content')).toHaveTextContent(
      '00700.HK',
    );
  });

  it('后台刷新失败时显示警告并保留已有研究数据和原始行情时间', () => {
    const stock = buildStockResearch('HK', '00700.HK');
    const query = {
      isError: true,
      isFetching: false,
      refetch: vi.fn().mockResolvedValue(undefined),
    };
    const view = render(stockMainContent('HK', stock, query));

    expect(screen.getByRole('alert')).toHaveClass('ant-alert-warning');
    expect(screen.getByRole('alert')).toHaveTextContent(
      '行情时间: 2026/10/19 09:30:00',
    );
    expect(screen.getByTestId('stock-research-content')).toHaveTextContent(
      '00700.HK',
    );
    expect(componentMocks.stockResearchContent).toHaveBeenLastCalledWith({
      snapshot: marketSnapshots.HK,
      stockResearch: stock,
      requestedSymbol: undefined,
      eventColumns: [],
    });
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(query.refetch).toHaveBeenCalledTimes(1);

    view.rerender(
      stockMainContent('HK', stock, { ...query, isFetching: true }),
    );
    expect(screen.getByTestId('stock-research-content')).toHaveTextContent(
      '00700.HK',
    );
    expect(screen.getByRole('button', { name: '重试' })).toBeDisabled();
    expect(screen.getByRole('alert')).toHaveTextContent('2026/10/19 09:30:00');
  });

  it.each(['zh-CN', 'en-US'])('缓存报价缺少时间时在 %s 刷新警告中显示缺失状态', (locale) => {
    componentMocks.locale = locale;
    const stock = buildStockResearch('HK', '00700.HK');
    stock.quote.timestamp = null;
    render(stockMainContent('HK', stock, {
      isError: true,
      isFetching: false,
      refetch: vi.fn(),
    }));
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    expect(screen.getByRole('alert')).toHaveTextContent(
      dictionary['terminal.footer.time.unavailable'],
    );
    expect(screen.getByRole('alert')).not.toHaveTextContent('1970');
    expect(screen.getByTestId('stock-research-content')).toHaveTextContent('00700.HK');
  });

  it('英文界面复用英文失败文案和重试标签', () => {
    componentMocks.locale = 'en-US';
    const query = {
      isError: true,
      isFetching: false,
      refetch: vi.fn().mockResolvedValue(undefined),
    };
    render(stockMainContent('US', undefined, query));

    expect(screen.getByRole('alert')).toHaveTextContent(
      enUS['terminal.stockResearch.refreshFailed'],
    );
    expect(screen.getByRole('button', { name: 'Retry' })).toBeEnabled();
    expect(
      screen.queryByText(zhCN['terminal.stockResearch.refreshFailed']),
    ).not.toBeInTheDocument();
  });

  it('个股快照未就绪时显示当前市场准备状态且不展示来源和其他业务内容', () => {
    render(stockMainContent('HK'));

    expect(
      screen.getByText(zhCN['terminal.panel.stockDataPreparing']),
    ).toBeInTheDocument();
    expect(
      screen.getByText(zhCN['terminal.page.stockResearch.title']),
    ).toBeInTheDocument();
    expect(screen.getByText(/HK.*恒生指数 HSI/)).toBeInTheDocument();
    expect(
      screen.queryByText(zhCN['terminal.dataSourceStrip.title']),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId('stock-research-content'),
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-content')).not.toBeInTheDocument();
    expect(componentMocks.stockResearchContent).not.toHaveBeenCalled();
    expect(componentMocks.portfolioContent).not.toHaveBeenCalled();
  });

  it('个股快照就绪后传给研究页并分别显示四个分区的来源', () => {
    const stock = buildStockResearch('HK', '00700.HK');
    render(stockMainContent('HK', stock));

    expect(screen.getByTestId('stock-research-content')).toHaveTextContent(
      '00700.HK',
    );
    expect(
      screen.queryByText(zhCN['terminal.panel.stockDataPreparing']),
    ).not.toBeInTheDocument();
    expect(screen.getByText('行情: YahooFinance 公开行情')).toBeInTheDocument();
    expect(screen.getByText('K线: Mock 回退')).toBeInTheDocument();
    expect(screen.getByText('基本面: 数据库')).toBeInTheDocument();
    expect(screen.getByText('因子: 即时 Quant Pipeline')).toBeInTheDocument();
    expect(componentMocks.stockResearchContent).toHaveBeenLastCalledWith({
      snapshot: marketSnapshots.HK,
      stockResearch: stock,
      requestedSymbol: undefined,
      eventColumns: [],
    });
    expect(componentMocks.portfolioContent).not.toHaveBeenCalled();
  });

  it('快照到达后展示个股，切换市场等待新快照时移除旧内容和来源', () => {
    const view = render(stockMainContent('HK'));
    const first = buildStockResearch('HK', '00700.HK');
    view.rerender(stockMainContent('HK', first));
    expect(screen.getByTestId('stock-research-content')).toHaveTextContent(
      '00700.HK',
    );

    // 同一分发组件经历清空与重新加载，检查旧内容不会留在新市场的准备页。
    view.rerender(stockMainContent('CN'));
    expect(
      screen.getByText(zhCN['terminal.panel.stockDataPreparing']),
    ).toBeInTheDocument();
    expect(screen.getByText(/CN.*沪深300 CSI 300/)).toBeInTheDocument();
    expect(screen.queryByText(/HK.*恒生指数 HSI/)).not.toBeInTheDocument();
    expect(screen.queryByText('00700.HK')).not.toBeInTheDocument();
    expect(
      screen.queryByTestId('stock-research-content'),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(zhCN['terminal.dataSourceStrip.title']),
    ).not.toBeInTheDocument();

    const next = buildStockResearch('CN', '600519.SH');
    view.rerender(stockMainContent('CN', next));
    expect(screen.getByTestId('stock-research-content')).toHaveTextContent(
      '600519.SH',
    );
    expect(screen.queryByText('00700.HK')).not.toBeInTheDocument();
    expect(
      screen.queryByText(zhCN['terminal.panel.stockDataPreparing']),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(zhCN['terminal.dataSourceStrip.title']),
    ).toBeInTheDocument();
    expect(componentMocks.stockResearchContent).toHaveBeenLastCalledWith({
      snapshot: marketSnapshots.CN,
      stockResearch: next,
      requestedSymbol: undefined,
      eventColumns: [],
    });
  });

  it('切换标的后同步替换来源标签，行情和K线不互相继承回退状态', () => {
    const first = buildStockResearch('HK', '00700.HK');
    const view = render(stockMainContent('HK', first));
    const next: StockResearchSnapshot = {
      ...first,
      symbol: '09988.HK',
      name: 'Alibaba',
      quoteDataSource: { ...first.quoteDataSource, source: 'database' },
      kline: { ...first.kline, dataStatus: 'delayed' },
      klineDataSource: {
        ...first.klineDataSource,
        source: 'yahoo_finance',
        fallbackActive: false,
        dataStatus: 'delayed',
      },
      fundamentalDataStatus: {
        ...first.fundamentalDataStatus,
        source: 'mock_provider',
        completeness: 'mock',
      },
      factorDataStatus: {
        ...first.factorDataStatus,
        source: 'database',
        completeness: 'complete',
      },
    };
    view.rerender(stockMainContent('HK', next));

    expect(screen.getByTestId('stock-research-content')).toHaveTextContent(
      '09988.HK',
    );
    expect(screen.getByText('行情: 数据库')).toBeInTheDocument();
    expect(screen.getByText('K线: YahooFinance 公开行情')).toBeInTheDocument();
    expect(screen.getByText('基本面: Mock Provider')).toBeInTheDocument();
    expect(screen.getByText('因子: 数据库')).toBeInTheDocument();
    expect(
      screen.queryByText('行情: YahooFinance 公开行情'),
    ).not.toBeInTheDocument();
    expect(screen.queryByText('K线: Mock 回退')).not.toBeInTheDocument();
    expect(screen.queryByText('基本面: 数据库')).not.toBeInTheDocument();
    expect(
      screen.queryByText('因子: 即时 Quant Pipeline'),
    ).not.toBeInTheDocument();
  });
});

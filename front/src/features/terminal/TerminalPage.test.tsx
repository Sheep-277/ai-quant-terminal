import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import zhCN from '../../locales/zh-CN/terminal';
import { marketSnapshots } from './mockData';
import { TerminalPage } from './TerminalPage';
import type { PortfolioSnapshot, StockResearchSnapshot } from './types';
import type { useTerminalPageData } from './useTerminalPageData';

const dependencyMocks = vi.hoisted(() => ({
  eventColumns: [{ key: 'event-column' }],
  eventStreamPanel: vi.fn(),
  header: vi.fn(),
  leftRail: vi.fn(),
  mainContent: vi.fn(),
  metricStrip: vi.fn(),
  rightRail: vi.fn(),
  runPrimaryAction: vi.fn(),
  showPrototypeMessage: vi.fn(),
  useTerminalPageData: vi.fn(),
  useTerminalPrimaryAction: vi.fn(),
}));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: 'zh-CN',
    formatMessage: (
      { id, defaultMessage }: { id?: string; defaultMessage?: string },
      values: Record<string, string> = {},
    ) => Object.entries(values).reduce(
      (text, [key, value]) => text.replaceAll(`{${key}}`, value),
      (id && zhCN[id as keyof typeof zhCN]) || defaultMessage || id || '',
    ),
  }),
}));

vi.mock('./DataSourceBadge', () => ({
  getDataSourceLabelText: () => 'YahooFinance',
}));

vi.mock('./formatters', () => ({
  formatDateTime: () => '2026/10/16 10:00:00',
}));

vi.mock('./terminalEventColumns', () => ({
  useEventColumns: () => dependencyMocks.eventColumns,
}));

vi.mock('./useTerminalPageData', () => ({
  useTerminalPageData: dependencyMocks.useTerminalPageData,
}));

vi.mock('./useTerminalPrimaryAction', () => ({
  useTerminalPrimaryAction: dependencyMocks.useTerminalPrimaryAction,
}));

vi.mock('./TerminalPageHeader', () => ({
  TerminalPageHeader: (props: {
    onMockDataClick: () => void;
    onPrimaryActionClick: () => void;
    primaryActionLoading: boolean;
  }) => {
    dependencyMocks.header(props);
    return (
      <header data-testid="terminal-page-header">
        <button type="button" onClick={props.onMockDataClick}>
          prototype
        </button>
        <button type="button" onClick={props.onPrimaryActionClick}>
          primary
        </button>
      </header>
    );
  },
}));

vi.mock('./TerminalLeftRail', () => ({
  TerminalLeftRail: (props: Record<string, unknown>) => {
    dependencyMocks.leftRail(props);
    return <aside data-testid="terminal-left-rail" />;
  },
}));

vi.mock('./TerminalMainContent', () => ({
  TerminalMainContent: (props: Record<string, unknown>) => {
    dependencyMocks.mainContent(props);
    return (
      <section data-testid="terminal-main-content">
        {props.pageKey === 'ai-research' ? <input aria-label="ai-layout-draft" /> : null}
        {props.pageKey === 'portfolio' ? <input aria-label="portfolio-layout-draft" /> : null}
      </section>
    );
  },
}));

vi.mock('./TerminalRightRail', () => ({
  TerminalRightRail: (props: Record<string, unknown>) => {
    dependencyMocks.rightRail(props);
    return <aside data-testid="terminal-right-rail" />;
  },
}));

vi.mock('./TerminalEventStreamPanel', () => ({
  TerminalEventStreamPanel: (props: Record<string, unknown>) => {
    dependencyMocks.eventStreamPanel(props);
    return <section data-testid="terminal-event-stream" />;
  },
}));

vi.mock('./TerminalShared', () => ({
  MetricStrip: (props: Record<string, unknown>) => {
    dependencyMocks.metricStrip(props);
    return <section data-testid="terminal-metric-strip" />;
  },
}));

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

const query = (
  data?: unknown,
  status: { isError?: boolean; isFetching?: boolean } = {},
) => ({
  data,
  isError: status.isError ?? false,
  isFetching: status.isFetching ?? false,
  refetch: vi.fn(),
});

const mutation = (
  data?: unknown,
  isPending = false,
) => ({
  data,
  isPending,
  mutateAsync: vi.fn(),
});

const orderReceipt = { order_id: 'paper-order-001' };
const riskReceipt = { decision: 'approved' };

let portfolioQuery: ReturnType<typeof query>;
let createPaperOrderMutation: ReturnType<typeof mutation>;
let preTradeRiskCheckMutation: ReturnType<typeof mutation>;

const buildPageData = () => {
  portfolioQuery = query(portfolio, { isError: true, isFetching: true });
  createPaperOrderMutation = mutation(orderReceipt);
  preTradeRiskCheckMutation = mutation(riskReceipt, true);

  return {
    market: 'HK',
    selectedSymbol: '00700.HK',
    snapshot: marketSnapshots.HK,
    stockResearch: undefined,
    strategyLab: undefined,
    backtest: undefined,
    aiResearch: undefined,
    portfolio,
    monitor: undefined,
    providerStatus: undefined,
    providerStatusQuery: query(),
    marketOverviewQuery: query(),
    stockResearchQuery: query(),
    strategyLabQuery: query(),
    createStrategyDraftMutation: mutation(),
    backtestQuery: query(),
    createBacktestTaskMutation: mutation(),
    createAIResearchTaskMutation: mutation(),
    aiResearchLLMStatusQuery: query(),
    aiResearchQuery: query(),
    portfolioQuery,
    createPaperOrderMutation,
    preTradeRiskCheckMutation,
    monitorQuery: query(),
  } as unknown as ReturnType<typeof useTerminalPageData>;
};

beforeEach(() => {
  vi.clearAllMocks();
  dependencyMocks.useTerminalPageData.mockReturnValue(buildPageData());
  dependencyMocks.useTerminalPrimaryAction.mockReturnValue({
    runPrimaryAction: dependencyMocks.runPrimaryAction,
    showPrototypeMessage: dependencyMocks.showPrototypeMessage,
  });
});

afterEach(() => {
  cleanup();
});

describe('TerminalPage quote time', () => {
  it('缺少报价时间时页脚显示缺失文案而非格式化空时间', () => {
    const data = buildPageData();
    const stock = {
      market: 'HK',
      symbol: '00700.HK',
      timezone: 'Asia/Hong_Kong',
      quote: { timestamp: null },
    } as StockResearchSnapshot;
    dependencyMocks.useTerminalPageData.mockReturnValue({ ...data, stockResearch: stock });

    render(<TerminalPage pageKey="stock-research" />);

    expect(screen.getByText(/暂无数据时间/)).toBeInTheDocument();
    expect(dependencyMocks.mainContent).toHaveBeenLastCalledWith(expect.objectContaining({
      requestedStockSymbol: data.selectedSymbol,
    }));
    expect(screen.queryByText(/2026\/10\/16 10:00:00/)).not.toBeInTheDocument();
  });
});

describe('TerminalPage context event placement', () => {
  it.each([
    { pageKey: 'dashboard', queryKey: 'marketOverviewQuery', reference: 'terminal.dashboard.referenceDetails' },
    { pageKey: 'stock-research', queryKey: 'stockResearchQuery', reference: 'terminal.stockResearch.referenceDetails' },
    { pageKey: 'backtest', queryKey: 'backtestQuery', reference: 'terminal.backtest.referenceDetails' },
  ] as const)('$pageKey 在加载、失败与重试中保留布局、主体和参考区状态', ({ pageKey, queryKey, reference }) => {
    const data = buildPageData();
    dependencyMocks.useTerminalPageData.mockReturnValue(data);
    const view = render(<TerminalPage pageKey={pageKey} />);
    const shell = view.container.querySelector('.terminal-shell');
    const center = view.container.querySelector('.terminal-center');
    const workspace = screen.getByTestId('terminal-main-content');
    const toggle = screen.getByText(zhCN[reference]);
    const details = toggle.closest('details') as HTMLDetailsElement;
    fireEvent.click(toggle);
    expect(details.open).toBe(true);

    for (const status of [
      { isError: false, isFetching: true },
      { isError: true, isFetching: false },
      { isError: true, isFetching: true },
      { isError: false, isFetching: false },
    ]) {
      const currentQuery = query(undefined, status);
      dependencyMocks.useTerminalPageData.mockReturnValue({ ...data, [queryKey]: currentQuery });
      view.rerender(<TerminalPage pageKey={pageKey} />);
      expect(view.container.querySelector('.terminal-shell')).toBe(shell);
      expect(shell).toHaveAttribute('data-page', pageKey);
      expect(view.container.querySelector('.terminal-center')).toBe(center);
      expect(screen.getByTestId('terminal-main-content')).toBe(workspace);
      expect(details.open).toBe(true);
      expect(dependencyMocks.header).toHaveBeenLastCalledWith(expect.objectContaining({
        apiStatusMap: expect.objectContaining({ [pageKey]: status }),
      }));
      if (pageKey === 'backtest') {
        expect(dependencyMocks.mainContent).toHaveBeenLastCalledWith(expect.objectContaining({ backtestQueryState: currentQuery }));
      }
      expect(currentQuery.refetch).not.toHaveBeenCalled();
    }
    expect(dependencyMocks.runPrimaryAction).not.toHaveBeenCalled();
  });

  it('总览观察列表常驻，事件独立占行，静态说明展开不重建主体', () => {
    const view = render(<TerminalPage pageKey="dashboard" />);
    const workspace = screen.getByTestId('terminal-main-content');
    const leftRail = screen.getByTestId('terminal-left-rail');
    const details = screen.getByText(zhCN['terminal.dashboard.referenceDetails']).closest('details') as HTMLDetailsElement;
    expect(details.open).toBe(false);
    expect(leftRail.closest('details')).toBeNull();
    expect(screen.getByTestId('terminal-right-rail').closest('details')).toBe(details);
    const events = view.container.querySelector('.terminal-dashboard-events');
    expect(screen.getByTestId('terminal-event-stream').parentElement).toBe(events);
    expect(events?.closest('.terminal-center')).toBeNull();
    fireEvent.click(screen.getByText(zhCN['terminal.dashboard.referenceDetails']));
    expect(details.open).toBe(true);
    fireEvent.click(screen.getByText(zhCN['terminal.dashboard.referenceDetails']));
    expect(details.open).toBe(false);
    expect(screen.getByTestId('terminal-main-content')).toBe(workspace);
    expect(screen.getByTestId('terminal-left-rail')).toBe(leftRail);
    expect(dependencyMocks.runPrimaryAction).not.toHaveBeenCalled();
    view.rerender(<TerminalPage pageKey="stock-research" />);
    expect(view.container.querySelector('.terminal-dashboard-reference')).toBeNull();
    expect(view.container.querySelector('.terminal-dashboard-events')).toBeNull();
  });

  it('个股参考展开不重建主体，离开后恢复总览辅助栏', () => {
    const view = render(<TerminalPage pageKey="stock-research" />);
    const toggle = screen.getByText(zhCN['terminal.stockResearch.referenceDetails']);
    const details = toggle.closest('details') as HTMLDetailsElement;
    const workspace = screen.getByTestId('terminal-main-content');
    expect(details.open).toBe(false);
    expect(screen.getByTestId('terminal-left-rail').closest('details')).toBe(details);
    expect(screen.getByTestId('terminal-right-rail').closest('details')).toBe(details);
    expect(workspace.closest('details')).toBeNull();
    fireEvent.click(toggle);
    expect(details.open).toBe(true);
    fireEvent.click(toggle);
    expect(details.open).toBe(false);
    expect(screen.getByTestId('terminal-main-content')).toBe(workspace);
    expect(screen.getAllByTestId('terminal-left-rail')).toHaveLength(1);
    expect(screen.getAllByTestId('terminal-right-rail')).toHaveLength(1);
    expect(dependencyMocks.runPrimaryAction).not.toHaveBeenCalled();
    view.rerender(<TerminalPage pageKey="dashboard" />);
    expect(view.container.querySelector('.terminal-stock-reference')).toBeNull();
    expect(screen.getByTestId('terminal-left-rail').closest('.terminal-shell')).not.toBeNull();
    expect(screen.getByTestId('terminal-right-rail').closest('.terminal-shell')).not.toBeNull();
  });

  it('回测参考默认收起，展开不重建回测主体或触发任务创建', () => {
    const view = render(<TerminalPage pageKey="backtest" />);
    const toggle = screen.getByText(zhCN['terminal.backtest.referenceDetails']);
    const details = toggle.closest('details') as HTMLDetailsElement;
    const workspace = screen.getByTestId('terminal-main-content');
    expect(details.open).toBe(false);
    expect(screen.getByTestId('terminal-left-rail').closest('details')).toBe(details);
    expect(screen.getByTestId('terminal-right-rail').closest('details')).toBe(details);
    expect(workspace.closest('details')).toBeNull();
    fireEvent.click(toggle);
    expect(details.open).toBe(true);
    fireEvent.click(toggle);
    expect(details.open).toBe(false);
    expect(screen.getByTestId('terminal-main-content')).toBe(workspace);
    expect(screen.getAllByTestId('terminal-left-rail')).toHaveLength(1);
    expect(screen.getAllByTestId('terminal-right-rail')).toHaveLength(1);
    expect(dependencyMocks.runPrimaryAction).not.toHaveBeenCalled();
    view.rerender(<TerminalPage pageKey="dashboard" />);
    expect(view.container.querySelector('.terminal-backtest-reference')).toBeNull();
    expect(screen.getByTestId('terminal-left-rail').closest('.terminal-shell')).not.toBeNull();
    expect(screen.getByTestId('terminal-right-rail').closest('.terminal-shell')).not.toBeNull();
  });

  it('监控参考默认收起，展开不重建主体或触发刷新，其他页面恢复辅助栏', () => {
    const view = render(<TerminalPage pageKey="monitor" />);
    const toggle = screen.getByText(zhCN['terminal.monitor.referenceDetails']);
    const details = toggle.closest('details') as HTMLDetailsElement;
    const workspace = screen.getByTestId('terminal-main-content');
    expect(details.open).toBe(false);
    expect(screen.getByTestId('terminal-left-rail').closest('details')).toBe(details);
    expect(screen.getByTestId('terminal-right-rail').closest('details')).toBe(details);
    expect(workspace.closest('details')).toBeNull();
    fireEvent.click(toggle);
    expect(details.open).toBe(true);
    expect(screen.getAllByTestId('terminal-left-rail')).toHaveLength(1);
    expect(screen.getAllByTestId('terminal-right-rail')).toHaveLength(1);
    fireEvent.click(toggle);
    expect(details.open).toBe(false);
    expect(screen.getByTestId('terminal-main-content')).toBe(workspace);
    expect(dependencyMocks.runPrimaryAction).not.toHaveBeenCalled();
    expect(screen.queryByTestId('terminal-event-stream')).not.toBeInTheDocument();

    view.rerender(<TerminalPage pageKey="dashboard" />);
    expect(view.container.querySelector('.terminal-monitor-reference')).toBeNull();
    expect(screen.getByTestId('terminal-left-rail').closest('.terminal-shell')).not.toBeNull();
    expect(screen.getByTestId('terminal-right-rail').closest('.terminal-shell')).not.toBeNull();
  });

  it('folds AI reference rails without remounting the task workspace and restores normal rails on navigation', () => {
    const view = render(<TerminalPage pageKey="ai-research" />);
    const toggle = screen.getByText(zhCN['terminal.aiResearch.referenceDetails']);
    const details = toggle.closest('details') as HTMLDetailsElement;
    const leftRail = screen.getByTestId('terminal-left-rail');
    const rightRail = screen.getByTestId('terminal-right-rail');
    const workspace = screen.getByTestId('terminal-main-content');
    const draft = screen.getByRole('textbox', { name: 'ai-layout-draft' });
    expect(details.open).toBe(false);
    expect(leftRail.closest('details')).toBe(details);
    expect(rightRail.closest('details')).toBe(details);
    expect(workspace.closest('details')).toBeNull();
    fireEvent.change(draft, { target: { value: 'UNSAVED_AI_QUERY' } });
    fireEvent.click(toggle);
    expect(details.open).toBe(true);
    expect(screen.getAllByTestId('terminal-left-rail')).toHaveLength(1);
    expect(screen.getAllByTestId('terminal-right-rail')).toHaveLength(1);
    fireEvent.click(toggle);
    expect(details.open).toBe(false);
    expect(screen.getByTestId('terminal-main-content')).toBe(workspace);
    expect(screen.getByRole('textbox', { name: 'ai-layout-draft' })).toBe(draft);
    expect(draft).toHaveValue('UNSAVED_AI_QUERY');

    view.rerender(<TerminalPage pageKey="dashboard" />);
    expect(view.container.querySelector('.terminal-ai-reference')).toBeNull();
    expect(screen.getByTestId('terminal-left-rail').closest('.terminal-shell')).not.toBeNull();
    expect(screen.getByTestId('terminal-right-rail').closest('.terminal-shell')).not.toBeNull();
  });
  it('removes outer strategy rails and restores them on other pages', () => {
    const view = render(<TerminalPage pageKey="strategy-lab" />);
    expect(screen.queryByTestId('terminal-left-rail')).not.toBeInTheDocument();
    expect(screen.queryByTestId('terminal-right-rail')).not.toBeInTheDocument();
    expect(screen.getByTestId('terminal-main-content').closest('.terminal-shell')).toHaveAttribute('data-page', 'strategy-lab');
    view.rerender(<TerminalPage pageKey="portfolio" />);
    expect(screen.getByTestId('terminal-left-rail')).toBeInTheDocument();
    expect(screen.getByTestId('terminal-right-rail')).toBeInTheDocument();
  });
  it.each([
    'dashboard', 'stock-research', 'ai-research', 'strategy-lab', 'backtest', 'portfolio', 'monitor',
  ] as const)('shows the shared event panel only on the dashboard: %s', (pageKey) => {
    render(<TerminalPage pageKey={pageKey} />);

    if (pageKey === 'dashboard') {
      expect(screen.getAllByTestId('terminal-event-stream')).toHaveLength(1);
      expect(dependencyMocks.eventStreamPanel).toHaveBeenCalledWith(expect.objectContaining({
        pageKey: 'dashboard',
        events: marketSnapshots.HK.events,
        eventColumns: dependencyMocks.eventColumns,
      }));
    } else {
      expect(screen.queryByTestId('terminal-event-stream')).not.toBeInTheDocument();
      expect(dependencyMocks.eventStreamPanel).not.toHaveBeenCalled();
    }
    // 个股页签仍从主体获得事件数据和列配置，不因移除底部面板而丢失内容。
    expect(dependencyMocks.mainContent).toHaveBeenCalledWith(expect.objectContaining({
      pageKey,
      snapshot: marketSnapshots.HK,
      eventColumns: dependencyMocks.eventColumns,
    }));
  });

  it('removes and restores the shared panel when navigating between page identities', () => {
    const view = render(<TerminalPage pageKey="dashboard" />);
    expect(screen.getAllByTestId('terminal-event-stream')).toHaveLength(1);

    view.rerender(<TerminalPage pageKey="stock-research" />);
    expect(screen.queryByTestId('terminal-event-stream')).not.toBeInTheDocument();
    view.rerender(<TerminalPage pageKey="monitor" />);
    expect(screen.queryByTestId('terminal-event-stream')).not.toBeInTheDocument();

    view.rerender(<TerminalPage pageKey="dashboard" />);
    expect(screen.getAllByTestId('terminal-event-stream')).toHaveLength(1);
  });
});

describe('TerminalPage portfolio wiring', () => {
  it('收起组合参考不卸载主体，切换页面后恢复其他页面的辅助栏', () => {
    const view = render(<TerminalPage pageKey="portfolio" />);
    const toggle = screen.getByText(zhCN['terminal.portfolio.referenceDetails']);
    const details = toggle.closest('details') as HTMLDetailsElement;
    const workspace = screen.getByTestId('terminal-main-content');
    const draft = screen.getByRole('textbox', { name: 'portfolio-layout-draft' });
    expect(details.open).toBe(false);
    expect(screen.getByTestId('terminal-left-rail').closest('details')).toBe(details);
    expect(screen.getByTestId('terminal-right-rail').closest('details')).toBe(details);
    expect(workspace.closest('details')).toBeNull();
    fireEvent.change(draft, { target: { value: 'UNSAVED_PORTFOLIO_INPUT' } });
    fireEvent.click(toggle);
    expect(details.open).toBe(true);
    expect(screen.getAllByTestId('terminal-left-rail')).toHaveLength(1);
    expect(screen.getAllByTestId('terminal-right-rail')).toHaveLength(1);
    fireEvent.click(toggle);
    expect(details.open).toBe(false);
    expect(screen.getByTestId('terminal-main-content')).toBe(workspace);
    expect(draft).toHaveValue('UNSAVED_PORTFOLIO_INPUT');
    expect(dependencyMocks.runPrimaryAction).not.toHaveBeenCalled();

    view.rerender(<TerminalPage pageKey="dashboard" />);
    expect(view.container.querySelector('.terminal-portfolio-reference')).toBeNull();
    expect(screen.getByTestId('terminal-left-rail').closest('.terminal-shell')).not.toBeNull();
    expect(screen.getByTestId('terminal-right-rail').closest('.terminal-shell')).not.toBeNull();
  });

  it('将组合数据、查询状态和操作回执交给对应展示层', () => {
    const { container } = render(<TerminalPage pageKey="portfolio" />);

    expect(dependencyMocks.useTerminalPageData).toHaveBeenCalledWith('portfolio');
    expect(dependencyMocks.useTerminalPrimaryAction).toHaveBeenCalledWith(
      expect.objectContaining({
        pageKey: 'portfolio',
        market: 'HK',
        selectedSymbol: '00700.HK',
        portfolio,
        portfolioQuery,
        createPaperOrderMutation,
        preTradeRiskCheckMutation,
      }),
    );

    expect(dependencyMocks.header).toHaveBeenCalledWith(
      expect.objectContaining({
        pageKey: 'portfolio',
        snapshot: marketSnapshots.HK,
        providerStatusLoading: false,
        providerStatusError: false,
        primaryActionLoading: true,
        apiStatusMap: expect.objectContaining({
          portfolio: { isError: true, isFetching: true },
        }),
      }),
    );
    expect(dependencyMocks.mainContent).toHaveBeenCalledWith(
      expect.objectContaining({
        pageKey: 'portfolio',
        snapshot: marketSnapshots.HK,
        eventColumns: dependencyMocks.eventColumns,
        portfolio,
        paperOrderReceipt: orderReceipt,
        preTradeRiskCheckReceipt: riskReceipt,
      }),
    );
    expect(dependencyMocks.leftRail).toHaveBeenCalledWith(
      expect.objectContaining({ pageKey: 'portfolio', snapshot: marketSnapshots.HK }),
    );
    expect(dependencyMocks.rightRail).toHaveBeenCalledWith({ pageKey: 'portfolio' });
    expect(container.querySelector('.terminal-shell')).toHaveAttribute(
      'data-layout',
      'workflow',
    );
    expect(screen.queryByTestId('terminal-metric-strip')).not.toBeInTheDocument();
    expect(screen.queryByTestId('terminal-event-stream')).not.toBeInTheDocument();
  });

  it('页头按钮调用主操作和原型说明回调', () => {
    render(<TerminalPage pageKey="portfolio" />);

    fireEvent.click(screen.getByRole('button', { name: 'primary' }));
    fireEvent.click(screen.getByRole('button', { name: 'prototype' }));

    expect(dependencyMocks.runPrimaryAction).toHaveBeenCalledTimes(1);
    expect(dependencyMocks.showPrototypeMessage).toHaveBeenCalledTimes(1);
  });
});

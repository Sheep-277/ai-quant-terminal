import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { BacktestPollError } from '@/services/terminal/backtest';
import zhCN from '../../locales/zh-CN/terminal';
import type { BacktestResponse, BacktestTaskCreateResponse } from './apiTypes';
import { BacktestContent } from './BacktestContent';
import type { BacktestSnapshot } from './types';

const dependencyMocks = vi.hoisted(() => ({
  stockMetricStrip: vi.fn(),
  useBacktestByPollUrl: vi.fn(),
}));

vi.mock('@ant-design/icons', () => ({
  BarChartOutlined: () => null,
  HistoryOutlined: () => null,
  LineChartOutlined: () => null,
}));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: 'zh-CN',
    formatMessage: (
      { id, defaultMessage }: { id?: string; defaultMessage?: string },
      values?: Record<string, string | number>,
    ) => {
      let message =
        (id && zhCN[id as keyof typeof zhCN]) || defaultMessage || id || '';
      for (const [key, value] of Object.entries(values ?? {})) {
        message = message.replace(`{${key}}`, String(value));
      }
      return message;
    },
  }),
}));

vi.mock('./useBacktestResult', () => ({
  useBacktestByPollUrl: dependencyMocks.useBacktestByPollUrl,
}));

vi.mock('./StockMetricStrip', () => ({
  StockMetricStrip: (props: {
    market: string;
    metrics: BacktestSnapshot['performanceMetrics'];
  }) => {
    dependencyMocks.stockMetricStrip(props);
    return (
      <div data-testid="backtest-metrics">
        {props.market}:{props.metrics.length}
      </div>
    );
  },
}));

vi.mock('./glossary', () => ({
  GlossaryTerm: ({ term }: { term: string }) => (
    <span data-testid={`glossary-${term}`}>{term}</span>
  ),
}));

const backtest: BacktestSnapshot = {
  backtestId: 'backtest-hk-001',
  strategyId: 'strategy-hk-quality-001',
  market: 'HK',
  status: 'completed',
  dataMode: 'historical',
  timestamp: '2026-10-16T02:05:00Z',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  benchmark: 'Hang Seng TECH',
  startDate: '2025-01-01',
  endDate: '2025-12-31',
  performanceMetrics: [
    {
      labelId: 'terminal.metric.initialCapital',
      value: 500_000,
      valueFormat: 'currency',
    },
    {
      labelId: 'terminal.metric.totalReturn',
      value: 0.12,
      valueFormat: 'percent',
      tone: 'positive',
    },
    {
      labelId: 'terminal.metric.maxDrawdown',
      value: 0.09,
      valueFormat: 'percent',
      tone: 'warning',
    },
    {
      labelId: 'terminal.metric.sharpeRatio',
      value: 1.35,
      valueFormat: 'number',
    },
  ],
  equityCurve: [
    {
      timestamp: '2025-01-01T00:00:00Z',
      equity: 500_000,
      benchmarkEquity: 500_000,
      drawdown: 0,
    },
    {
      timestamp: '2025-12-31T00:00:00Z',
      equity: 560_000,
      benchmarkEquity: 540_000,
      drawdown: 0.02,
    },
  ],
  trades: [
    {
      key: 'trade-001',
      timestamp: '2025-02-03T01:30:00Z',
      market: 'HK',
      symbol: '00700.HK',
      side: 'BUY',
      quantity: 100,
      price: 410,
      fee: 20,
      slippage: 10,
    },
  ],
  assumptions: [
    '已计入交易费用与滑点',
    '数据库回测结果读取失败，已回退 Mock 数据。',
  ],
};

const taskReceipt: BacktestTaskCreateResponse = {
  backtest_id: 'backtest-hk-002',
  strategy_id: 'strategy-hk-quality-001',
  market: 'HK',
  status: 'pending',
  accepted_at: '2026-10-16T02:10:00Z',
  data_mode: 'historical',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  poll_url: '/api/v1/backtests/backtest-hk-002',
  data_status: 'delayed',
  fallback_active: false,
  fallback_reason: null,
  storage_source: 'database',
  result_data_mode: 'historical',
};

const polledResponse: BacktestResponse = {
  backtest_id: 'backtest-hk-002',
  strategy_id: 'strategy-hk-quality-001',
  market: 'HK',
  status: 'completed',
  data_mode: 'historical',
  timestamp: '2026-10-16T02:11:00Z',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  benchmark: 'Hang Seng TECH',
  start_date: '2025-01-01',
  end_date: '2025-12-31',
  performance: {
    initial_capital: 500_000,
    final_value: 560_000,
    total_return: 0.12,
    annualized_return: 0.12,
    benchmark_return: 0.08,
    maximum_drawdown: 0.09,
    sharpe_ratio: 1.35,
    win_rate: 0.58,
    trade_count: 1,
  },
  equity_curve: [],
  trades: [
    {
      timestamp: '2025-02-03T01:30:00Z',
      market: 'HK',
      symbol: '00700.HK',
      side: 'BUY',
      quantity: 100,
      price: 410,
      fee: 20,
      slippage: 10,
    },
  ],
  assumptions: [],
};

type PollQueryStub = {
  data?: BacktestResponse;
  error?: unknown;
  isError: boolean;
  isFetching: boolean;
};

const pollQuery = (overrides: Partial<PollQueryStub> = {}): PollQueryStub => ({
  data: undefined,
  error: undefined,
  isError: false,
  isFetching: false,
  ...overrides,
});

const renderContent = (receipt?: BacktestTaskCreateResponse) =>
  render(
    <App>
      <BacktestContent backtest={backtest} taskReceipt={receipt} />
    </App>,
  );

beforeEach(() => {
  vi.clearAllMocks();
  dependencyMocks.useBacktestByPollUrl.mockReturnValue(pollQuery());
});

afterEach(() => {
  cleanup();
});

describe('BacktestContent', () => {
  it('空权益序列明确显示空状态，仍保留主行与空成交表', () => {
    const { container } = render(<App><BacktestContent backtest={{ ...backtest, equityCurve: [], trades: [] }} /></App>);
    expect(screen.getByText(zhCN['terminal.backtest.emptyEquity'])).toBeInTheDocument();
    expect(container.querySelectorAll('.terminal-backtest-primary-row > div')).toHaveLength(2);
    expect(container.querySelectorAll('polyline')).toHaveLength(0);
    fireEvent.click(screen.getByRole('tab', { name: '模拟交易记录 Trades' }));
    expect(container.querySelector('.ant-table-placeholder')).toBeInTheDocument();
  });

  it('摘要和结果共享主行，假设和任务回执分别占据完整行', () => {
    const { container } = renderContent(taskReceipt);
    const workspace = container.querySelector('.terminal-backtest-workspace');
    const primaryRow = workspace?.firstElementChild;
    expect(primaryRow).toHaveClass('terminal-backtest-primary-row');
    expect(primaryRow?.children).toHaveLength(2);
    expect(primaryRow?.children[0]).toHaveClass('terminal-backtest-performance');
    expect(primaryRow?.children[1]).toHaveClass('terminal-backtest-results');
    expect(workspace?.children).toHaveLength(3);
    expect(screen.getByRole('heading', { name: '回测假设 Assumptions' }).closest('.terminal-panel')?.parentElement).toBe(workspace);
    expect(primaryRow?.querySelector('.terminal-assumption-list')).toBeNull();
  });

  it('切换成交页签保留完整记录和表格内部滚动', async () => {
    const { container } = renderContent();
    fireEvent.click(screen.getByRole('tab', { name: '模拟交易记录 Trades' }));
    expect(screen.getByRole('tab', { name: '模拟交易记录 Trades' })).toHaveAttribute('aria-selected', 'true');
    expect(await screen.findByText('00700.HK')).toBeInTheDocument();
    expect(container.querySelector('.terminal-backtest-results .ant-table-content')).toHaveStyle({ overflowX: 'auto' });
  });

  it('展示回测摘要、权益曲线和回退假设提示', () => {
    const { container } = renderContent();

    expect(screen.getByText('strategy-hk-quality-001')).toBeInTheDocument();
    expect(screen.getByText('2025-01-01 / 2025-12-31')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-metrics')).toHaveTextContent('HK:4');
    expect(screen.getByTestId('glossary-SHARPE')).toBeInTheDocument();
    expect(screen.getByText('已计入交易费用与滑点')).toBeInTheDocument();

    const fallbackAssumption = screen.getByText(
      '数据库回测结果读取失败，已回退 Mock 数据。',
    );
    expect(fallbackAssumption.closest('.terminal-assumption-item')).toHaveClass(
      'terminal-assumption-item-warning',
    );
    expect(
      screen.getByRole('img', { name: '回测权益曲线模拟图表' }),
    ).toBeInTheDocument();

    const lines = container.querySelectorAll('polyline');
    expect(lines).toHaveLength(2);
    expect(lines[0]).toHaveAttribute('points', expect.stringContaining('0,'));
    const equityPanel = screen
      .getByRole('heading', { name: '权益曲线 Equity Curve' })
      .closest('.terminal-panel');
    expect(
      equityPanel?.querySelector('.terminal-panel-header .ant-tag'),
    ).toHaveTextContent('模拟交易记录 Trades: 1');
    expect(dependencyMocks.useBacktestByPollUrl).not.toHaveBeenCalled();
  });

  it('回执进入 Mock 回退时显示原因且禁用结果轮询', () => {
    const fallbackReceipt: BacktestTaskCreateResponse = {
      ...taskReceipt,
      fallback_active: true,
      fallback_reason: 'database writes disabled',
      storage_source: 'mock_fallback',
      result_data_mode: 'mock',
    };

    renderContent(fallbackReceipt);

    expect(screen.getByText('database writes disabled')).toBeInTheDocument();
    expect(dependencyMocks.useBacktestByPollUrl).toHaveBeenCalledWith({
      pollUrl: taskReceipt.poll_url,
      enabled: false,
    });
  });

  it('有效回执读取中时显示加载状态并启用轮询', () => {
    dependencyMocks.useBacktestByPollUrl.mockReturnValue(
      pollQuery({ isFetching: true }),
    );

    renderContent(taskReceipt);

    expect(
      screen.getByText('正在读取该回测任务的结果快照。'),
    ).toBeInTheDocument();
    expect(dependencyMocks.useBacktestByPollUrl).toHaveBeenCalledWith({
      pollUrl: taskReceipt.poll_url,
      enabled: true,
    });
  });

  it('轮询失败时根据结构化错误显示数据库开关提示', () => {
    dependencyMocks.useBacktestByPollUrl.mockReturnValue(
      pollQuery({
        isError: true,
        error: new BacktestPollError({
          code: 'backtest_database_reads_disabled',
          message: 'database reads disabled',
          backtestId: taskReceipt.backtest_id,
        }),
      }),
    );

    renderContent(taskReceipt);

    expect(
      screen.getByText(
        '后端数据库读取开关未开启，请在 .env 中开启 ENABLE_BACKTEST_DATABASE_READS 后重启后端。',
      ),
    ).toBeInTheDocument();
  });

  it('读取成功后显示该任务的状态与绩效摘要', () => {
    dependencyMocks.useBacktestByPollUrl.mockReturnValue(
      pollQuery({ data: polledResponse }),
    );

    renderContent(taskReceipt);

    expect(
      screen.getByText('已读取到该回测任务的结果快照。'),
    ).toBeInTheDocument();
    expect(screen.getByText(/\u7ed3果 ID：backtest-hk-002/)).toHaveTextContent(
      '模拟成交：1 笔',
    );
    expect(screen.getByText(/\u7ed3果 ID：backtest-hk-002/)).toHaveTextContent(
      '总收益率：+12.00%',
    );
    expect(screen.getByText(/\u7ed3果 ID：backtest-hk-002/)).toHaveTextContent(
      '夏普比率：1.35',
    );
  });
});

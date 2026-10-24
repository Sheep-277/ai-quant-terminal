import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';
import { App } from 'antd';
import { afterEach, describe, expect, it, vi } from 'vitest';
import zhCN from '../../locales/zh-CN/terminal';
import { marketSnapshots } from './mockData';
import {
  MetricStrip,
  MockChart,
  Panel,
  SectorTape,
  TerminalTableText,
} from './TerminalShared';
import type { Metric } from './types';

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: 'zh-CN',
    formatMessage: ({ id }: { id: string }) =>
      zhCN[id as keyof typeof zhCN] ?? id,
  }),
}));

vi.mock('./MarketContext', () => ({
  useMarket: () => ({
    market: 'US',
    snapshot: marketSnapshots.US,
    selectedSymbol: undefined,
    setMarket: vi.fn(),
    setSelectedSymbol: vi.fn(),
  }),
}));

const renderWithApp = (node: React.ReactNode) => render(<App>{node}</App>);

afterEach(cleanup);

describe('TerminalTableText', () => {
  it('keeps custom and code classes while exposing full text in a tooltip', async () => {
    renderWithApp(
      <TerminalTableText className="custom-cell" code>
        AAPL.US
      </TerminalTableText>,
    );

    const text = screen.getByText('AAPL.US');
    expect(text).toHaveClass(
      'terminal-table-text',
      'terminal-table-text-code',
      'custom-cell',
    );

    fireEvent.mouseOver(text);
    expect(await screen.findByRole('tooltip')).toHaveTextContent('AAPL.US');
  });

  it('renders React elements directly without creating an empty tooltip', () => {
    const { container } = renderWithApp(
      <TerminalTableText>
        <strong>结构化内容</strong>
      </TerminalTableText>,
    );

    expect(screen.getByText('结构化内容')).toBeInTheDocument();
    expect(
      container.querySelector('.ant-tooltip-open'),
    ).not.toBeInTheDocument();
  });
});

describe('Panel', () => {
  it('renders its title, icon, extra action, body and custom class in fixed slots', () => {
    const { container } = renderWithApp(
      <Panel
        title="测试面板"
        icon={<span data-testid="panel-icon" />}
        extra={<button type="button">刷新</button>}
        className="custom-panel"
      >
        <p>面板正文</p>
      </Panel>,
    );

    const panel = container.querySelector('.terminal-panel');
    expect(panel).toHaveClass('custom-panel');
    expect(
      within(panel as HTMLElement).getByRole('heading', { name: '测试面板' }),
    ).toBeInTheDocument();
    expect(screen.getByTestId('panel-icon')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '刷新' })).toBeInTheDocument();
    expect(screen.getByText('面板正文')).toBeInTheDocument();
  });
});

describe('MetricStrip', () => {
  const metrics: Metric[] = [
    {
      labelId: 'terminal.metric.sp500',
      value: 123456.78,
      valueFormat: 'currency',
      change: 0.0123,
      changeFormat: 'percent',
      tone: 'positive',
      dataSource: {
        source: 'yahoo_finance',
        status: 'delayed',
        timestamp: '2026-10-15T12:00:00Z',
      },
    },
    {
      labelId: 'terminal.metric.vix',
      value: 18.5,
      change: -1,
      changeFormat: 'number',
      tone: 'negative',
      dataSource: {
        source: 'yahoo_finance',
        status: 'unavailable',
      },
    },
  ];

  it('shows compact values, full-value titles, change semantics and provenance', async () => {
    const { container } = renderWithApp(<MetricStrip metrics={metrics} />);
    const metricCards = container.querySelectorAll('.terminal-metric');
    const availableCard = metricCards[0] as HTMLElement;

    expect(within(availableCard).getByText('$123.5K')).toHaveAttribute(
      'title',
      '$123,456.78',
    );
    expect(within(availableCard).getByText('+1.23%')).toHaveClass(
      'terminal-tone-positive',
    );

    const source = within(availableCard).getByText(
      'YahooFinance 公开行情 · 延迟数据',
    );
    fireEvent.mouseOver(source);
    expect(await screen.findByRole('tooltip')).toHaveTextContent(
      '2026/10/15 08:00:00',
    );
  });

  it('replaces unavailable values and hides their changes', () => {
    const { container } = renderWithApp(<MetricStrip metrics={metrics} />);
    const unavailableCard = container.querySelectorAll(
      '.terminal-metric',
    )[1] as HTMLElement;

    expect(within(unavailableCard).getByText('--')).toHaveAttribute(
      'title',
      '数据不可用',
    );
    expect(unavailableCard.querySelector('em')).not.toBeInTheDocument();
    expect(
      within(unavailableCard).getByText('YahooFinance 公开行情 · 数据不可用'),
    ).toBeInTheDocument();
  });
});

describe('SectorTape', () => {
  it('derives positive, negative and neutral colors from percentage values', () => {
    const sectors: Metric[] = [
      {
        labelId: 'terminal.sector.semis',
        value: 0.01,
        valueFormat: 'percent',
        tone: 'negative',
      },
      {
        labelId: 'terminal.sector.banks',
        value: -0.02,
        valueFormat: 'percent',
        tone: 'positive',
      },
      {
        labelId: 'terminal.sector.energy',
        value: 0,
        valueFormat: 'percent',
        tone: 'warning',
      },
    ];
    const { container } = renderWithApp(<SectorTape sectors={sectors} />);
    const rows = container.querySelectorAll('.terminal-sector-item');

    expect(rows[0].querySelector('.terminal-sector-value')).toHaveClass(
      'terminal-tone-positive',
    );
    expect(rows[1].querySelector('.terminal-sector-value')).toHaveClass(
      'terminal-tone-negative',
    );
    expect(rows[2].querySelector('.terminal-sector-value')).toHaveClass(
      'terminal-tone-neutral',
    );
    expect(screen.getByText('+1.00%')).toBeInTheDocument();
    expect(screen.getByText('-2.00%')).toBeInTheDocument();
  });
});

describe('MockChart', () => {
  it('keeps accessible chart labels, indicator glossary links and all mock bars', () => {
    const { container } = renderWithApp(<MockChart />);

    expect(
      screen.getByRole('img', { name: '交互式 K 线图' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('img', { name: 'K 线价格与成交量图' }),
    ).toBeInTheDocument();
    expect(screen.getByText('交互 K 线图')).toBeInTheDocument();
    expect(screen.getByText('RSI 相对强弱指标')).toBeInTheDocument();
    expect(screen.getByText('MACD 指数平滑异同移动平均线')).toBeInTheDocument();
    expect(container.querySelectorAll('svg rect')).toHaveLength(18);
  });
});

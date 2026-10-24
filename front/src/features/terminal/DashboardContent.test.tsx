import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, describe, expect, it, vi } from 'vitest';
import zhCN from '../../locales/zh-CN/terminal';
import type { ProviderStatusResponse } from './apiTypes';
import { DashboardContent } from './DashboardContent';
import { marketSnapshots } from './mockData';
import type { MarketSnapshot } from './types';

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: 'zh-CN',
    formatMessage: (
      { id }: { id: string },
      values: Record<string, string | number> = {},
    ) => Object.entries(values).reduce(
      (text, [key, value]) => text.replaceAll(`{${key}}`, String(value)),
      zhCN[id as keyof typeof zhCN] ?? id,
    ),
  }),
}));

const snapshot: MarketSnapshot = {
  ...marketSnapshots.US,
  breadth: [
    { labelId: 'terminal.metric.advancers', value: 0.5, valueFormat: 'percent', tone: 'positive' },
    { labelId: 'terminal.metric.decliners', value: 0.3, valueFormat: 'percent', tone: 'negative' },
    { labelId: 'terminal.metric.newHighs', value: 120, tone: 'positive' },
    { labelId: 'terminal.metric.newLows', value: 40, tone: 'negative' },
  ],
  chartBars: [
    { timestamp: '2026-10-13T20:00:00Z', open: 100, high: 102, low: 99, close: 101, volume: 1_000_000 },
    { timestamp: '2026-10-14T20:00:00Z', open: 101, high: 106, low: 100, close: 105, volume: 1_200_000 },
    { timestamp: '2026-10-15T20:00:00Z', open: 105, high: 106, low: 102, close: 103, volume: 1_100_000 },
  ],
};

vi.mock('./MarketContext', () => ({
  useMarket: () => ({ market: 'US', snapshot }),
}));

const providerStatus: ProviderStatusResponse = {
  provider_name: 'YahooFinance',
  mode: 'real',
  ready: true,
  data_status: 'delayed',
  fallback_active: false,
  fallback_reason: null,
  source_type: 'provider',
  active_source: 'yahoo_finance',
};

const renderDashboard = (currentSnapshot: MarketSnapshot = snapshot) => render(
  <App>
    <DashboardContent
      providerStatus={providerStatus}
      snapshot={currentSnapshot}
      eventColumns={[]}
    />
  </App>,
);

afterEach(cleanup);

describe('dashboard market overview chart', () => {
  it('空行情和空股票池保留总览行边界，派生走势不伪造历史时间', () => {
    const { container } = renderDashboard({ ...snapshot, chartBars: [], breadth: [], watchlist: [], events: [] });
    expect(container.querySelector('.terminal-dashboard-primary-row')?.children).toHaveLength(2);
    const titles = [...container.querySelectorAll('.terminal-market-overview-chart circle > title')].map(el => el.textContent ?? '');
    expect(titles).toHaveLength(16);
    expect(titles.every(title => title.includes('派生点位') && !title.includes('2026/'))).toBe(true);
    fireEvent.click(screen.getByRole('tab', { name: zhCN['terminal.tab.fundamentals'] }));
    expect(container.querySelector('.terminal-dashboard-detail-row')?.children).toHaveLength(2);
    expect(container.querySelector('.ant-table-placeholder')).toBeInTheDocument();
  });

  it('价格图和市场宽度共用主行，不再使用两列独立堆叠', () => {
    const { container } = renderDashboard();
    const row = container.querySelector('.terminal-dashboard-primary-row');
    expect(row?.children).toHaveLength(2);
    expect(row?.children[0]).toHaveClass('terminal-dashboard-chart-panel');
    expect(row?.children[1]).toHaveClass('terminal-dashboard-breadth-panel');
    expect(screen.getByRole('heading', { name: zhCN['terminal.panel.priceMarket'] }).closest('.terminal-panel')?.parentElement).toBe(row);
    expect(screen.getByRole('heading', { name: zhCN['terminal.panel.marketBreadth'] }).closest('.terminal-panel')?.parentElement).toBe(row);
  });

  it('基本面页签内市场结构和活跃成分股共享一行，保留样例来源', () => {
    const { container } = renderDashboard();
    fireEvent.click(screen.getByRole('tab', { name: zhCN['terminal.tab.fundamentals'] }));
    const row = container.querySelector('.terminal-dashboard-detail-row');
    expect(row?.children).toHaveLength(2);
    expect(screen.getByRole('heading', { name: zhCN['terminal.panel.marketStructure'] }).closest('.terminal-panel')?.parentElement).toBe(row);
    expect(screen.getByRole('heading', { name: zhCN['terminal.panel.activeConstituents'] }).closest('.terminal-panel')?.parentElement).toBe(row);
    expect(screen.getByText('NVDA')).toBeInTheDocument();
    expect(row?.children[1].querySelector('.ant-table-content')).toHaveStyle({ overflowX: 'auto' });
  });

  it('shows real delayed provider status, axes and breadth legend', () => {
    renderDashboard();

    expect(screen.getByRole('img', {
      name: '市场总览指数走势与市场宽度图',
    })).toBeInTheDocument();
    expect(screen.getByText('Provider: YahooFinance')).toBeInTheDocument();
    expect(screen.getByText('数据状态 Data Status: 延迟数据')).toBeInTheDocument();
    expect(screen.queryByText('Mock 回退')).not.toBeInTheDocument();
    expect(screen.getByText('Y轴：收盘点位')).toBeInTheDocument();
    expect(screen.getByText('市场宽度 Breadth')).toBeInTheDocument();
    expect(screen.getByText('上涨')).toBeInTheDocument();
    expect(screen.getByText('下跌')).toBeInTheDocument();
    expect(screen.getByText('平盘')).toBeInTheDocument();
  });

  it('attaches date, historical source and close value to every trend point', () => {
    const { container } = renderDashboard();
    const pointTitles = Array.from(
      container.querySelectorAll('.terminal-market-overview-chart circle > title'),
    ).map((title) => title.textContent ?? '');

    expect(pointTitles).toHaveLength(3);
    expect(pointTitles[0]).toContain('历史收盘价：101');
    expect(pointTitles[1]).toContain('历史收盘价：105');
    expect(pointTitles[2]).toContain('历史收盘价：103');
    expect(pointTitles.every((title) => title.includes('2026/10/'))).toBe(true);
  });

  it('draws breadth segments from advancer, decliner and unchanged shares', () => {
    const { container } = renderDashboard();
    const breadthRects = Array.from(
      container.querySelectorAll('.terminal-market-overview-chart svg > rect'),
    );

    expect(breadthRects).toHaveLength(3);
    const widths = breadthRects.map((rect) => Number(rect.getAttribute('width')));
    expect(widths[0]).toBeCloseTo(302);
    expect(widths[1]).toBeCloseTo(181.2);
    expect(widths[2]).toBeCloseTo(120.8);
  });

  it('labels generated points as derived when historical bars are unavailable', () => {
    const { container } = renderDashboard({
      ...snapshot,
      chartBars: [],
    });
    const pointTitles = Array.from(
      container.querySelectorAll('.terminal-market-overview-chart circle > title'),
    ).map((title) => title.textContent ?? '');

    expect(pointTitles).toHaveLength(16);
    expect(pointTitles[0]).toContain('派生点 1');
    expect(pointTitles[0]).toContain('派生点位');
    expect(pointTitles[15]).toContain('派生点 16');
  });
});

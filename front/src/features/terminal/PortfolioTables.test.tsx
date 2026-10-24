import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import enUS from '../../locales/en-US/terminal';
import zhCN from '../../locales/zh-CN/terminal';
import { PortfolioTables } from './PortfolioTables';
import type { PortfolioSnapshot } from './types';

let locale = 'zh-CN';

vi.mock('@ant-design/icons', () => ({
  StockOutlined: () => null,
}));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale,
    formatMessage: ({ id, defaultMessage }: { id?: string; defaultMessage?: string }) => {
      const messages = locale === 'en-US' ? enUS : zhCN;
      return (id && messages[id as keyof typeof messages]) || defaultMessage || id || '';
    },
  }),
}));

const paperPortfolio: PortfolioSnapshot = {
  market: 'CN',
  timestamp: '2026-10-15T02:00:00Z',
  timezone: 'Asia/Shanghai',
  currency: 'CNY',
  dataMode: 'paper',
  account: {
    accountId: 'paper-cn-001',
    market: 'CN',
    currency: 'CNY',
    nav: 112000,
    cash: 16800,
    marketValue: 95200,
    dailyPnl: -260,
    totalPnl: 12000,
    totalReturn: 0.12,
    updatedAt: '2026-10-15T02:00:00Z',
  },
  accountMetrics: [],
  positions: [
    {
      key: 'position-600519',
      market: 'CN',
      symbol: '600519.SH',
      name: '贵州茅台',
      quantity: 30,
      averageCost: 1288,
      lastPrice: 1310,
      marketValue: 39300,
      weight: 0.3509,
      unrealizedPnl: 660,
      unrealizedPnlPercent: 0.0171,
    },
  ],
  orders: [
    {
      key: 'order-001',
      orderId: 'paper-cn-001',
      market: 'CN',
      symbol: '600519.SH',
      side: 'buy',
      quantity: 10,
      limitPrice: 1300,
      status: 'submitted',
      submittedAt: '2026-10-15T02:00:00Z',
      filledAt: null,
      source: 'paper_order',
    },
    {
      key: 'order-002',
      orderId: 'seed-cn-001',
      market: 'CN',
      symbol: '300750.SZ',
      side: 'sell',
      quantity: 20,
      limitPrice: null,
      status: 'filled',
      submittedAt: '2026-10-14T02:00:00Z',
      filledAt: '2026-10-14T02:01:00Z',
      source: 'mock_summary',
    },
  ],
  riskMetrics: [],
  riskFlags: [],
};

const renderTables = (portfolio: PortfolioSnapshot) =>
  render(
    <App>
      <PortfolioTables portfolio={portfolio} />
    </App>,
  );

describe('PortfolioTables', () => {
  beforeEach(() => {
    locale = 'zh-CN';
  });

  afterEach(() => {
    cleanup();
  });

  it('默认展示公开行情估值后的持仓数据', () => {
    renderTables(paperPortfolio);

    expect(screen.getByRole('tab', { name: '持仓与订单: 1' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(screen.getByText('600519.SH')).toBeInTheDocument();
    expect(screen.getByText('贵州茅台')).toBeInTheDocument();
    expect(screen.getByText('Provider 行情')).toBeInTheDocument();
    expect(screen.getByText('¥1,288.00')).toBeInTheDocument();
    expect(screen.getByText('¥1,310.00')).toBeInTheDocument();
    expect(screen.getByText('+35.09%')).toBeInTheDocument();
    expect(screen.getByText(/¥660\.00 \/ \+1\.71%/)).toHaveClass('terminal-positive');
    expect(screen.getByText(/Provider 公开行情/)).toBeInTheDocument();
  });

  it('切换页签后展示模拟订单状态、方向和来源', () => {
    renderTables(paperPortfolio);

    fireEvent.click(screen.getByRole('tab', { name: '模拟订单 Paper Orders: 2' }));

    expect(screen.getByText('paper-cn-001')).toBeInTheDocument();
    expect(screen.getByText('seed-cn-001')).toBeInTheDocument();
    expect(screen.getByText('买入')).toBeInTheDocument();
    expect(screen.getByText('卖出')).toBeInTheDocument();
    expect(screen.getByText('已提交')).toBeInTheDocument();
    expect(screen.getByText('已成交')).toBeInTheDocument();
    expect(screen.getByText('用户模拟下单')).toBeInTheDocument();
    expect(screen.getByText('Seed 快照')).toBeInTheDocument();
    expect(screen.getByText('¥1,300.00')).toBeInTheDocument();
    expect(screen.getByText('2026/10/15 10:00:00')).toBeInTheDocument();
  });

  it('Mock 模式明确显示本地快照估值及回退边界', () => {
    renderTables({ ...paperPortfolio, dataMode: 'mock' });

    expect(screen.getByText('Mock 快照')).toBeInTheDocument();
    expect(screen.queryByText('Provider 行情')).not.toBeInTheDocument();
    expect(screen.getByText(/本地 Mock 快照/)).toBeInTheDocument();
  });
});

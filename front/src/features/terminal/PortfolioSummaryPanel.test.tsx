import { cleanup, render, screen, within } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import enUS from '../../locales/en-US/terminal';
import zhCN from '../../locales/zh-CN/terminal';
import { PortfolioSummaryPanel } from './PortfolioSummaryPanel';
import type { PortfolioSnapshot } from './types';

let locale = 'zh-CN';

vi.mock('@ant-design/icons', () => ({
  QuestionCircleOutlined: () => null,
  WalletOutlined: () => null,
}));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale,
    formatMessage: (
      descriptor: { id?: string; defaultMessage?: string },
      values?: Record<string, string | number>,
    ) => {
      const messages = locale === 'en-US' ? enUS : zhCN;
      let message =
        (descriptor.id && messages[descriptor.id as keyof typeof messages]) ||
        descriptor.defaultMessage ||
        descriptor.id ||
        '';

      for (const [key, value] of Object.entries(values ?? {})) {
        message = message.replace(`{${key}}`, String(value));
      }

      return message;
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
  accountMetrics: [
    { labelId: 'terminal.metric.nav', value: 112000, valueFormat: 'currency' },
    { labelId: 'terminal.metric.cash', value: 16800, valueFormat: 'currency' },
    {
      labelId: 'terminal.metric.marketValue',
      value: 95200,
      valueFormat: 'currency',
    },
    {
      labelId: 'terminal.metric.dailyPnl',
      value: -260,
      valueFormat: 'currency',
      tone: 'negative',
    },
    {
      labelId: 'terminal.metric.totalPnl',
      value: 12000,
      valueFormat: 'currency',
      tone: 'positive',
    },
    {
      labelId: 'terminal.metric.totalReturn',
      value: 0.12,
      valueFormat: 'percent',
      tone: 'positive',
    },
  ],
  positions: [],
  orders: [],
  riskMetrics: [],
  riskFlags: [],
};

const renderPanel = (portfolio: PortfolioSnapshot) =>
  render(
    <App>
      <PortfolioSummaryPanel portfolio={portfolio} />
    </App>,
  );

describe('PortfolioSummaryPanel', () => {
  beforeEach(() => {
    locale = 'zh-CN';
  });

  afterEach(() => {
    cleanup();
  });

  it('展示公开行情估值的模拟账户摘要和格式化指标', () => {
    renderPanel(paperPortfolio);

    expect(screen.getByText('模拟交易控制台')).toBeInTheDocument();
    expect(screen.getByText('仅模拟交易')).toBeInTheDocument();
    expect(screen.getByText('真实行情估值')).toBeInTheDocument();
    expect(screen.getByText('paper-cn-001')).toBeInTheDocument();
    expect(screen.getByText('CNY')).toBeInTheDocument();
    expect(screen.getByText('Paper 模拟账户')).toBeInTheDocument();

    const navMetric = screen.getByText('NAV 组合净值').closest('.terminal-metric');
    const returnMetric = screen.getByText('总收益率 Total Return').closest('.terminal-metric');

    expect(navMetric).not.toBeNull();
    expect(returnMetric).not.toBeNull();
    expect(within(navMetric as HTMLElement).getByTitle(/112,000\.00/)).toBeInTheDocument();
    expect(within(returnMetric as HTMLElement).getByTitle('+12.00%')).toBeInTheDocument();
    expect(screen.getByText(/2026\/10\/15 10:00:00/)).toBeInTheDocument();
    expect(screen.getByText(/不连接真实资金账户/)).toBeInTheDocument();
  });

  it('纯 Mock 模式不显示真实行情估值标签', () => {
    renderPanel({
      ...paperPortfolio,
      dataMode: 'mock',
      account: { ...paperPortfolio.account, accountId: 'mock-cn-001' },
    });

    expect(screen.getByText('Mock 模拟数据')).toBeInTheDocument();
    expect(screen.getByText('仅模拟交易')).toBeInTheDocument();
    expect(screen.queryByText('真实行情估值')).not.toBeInTheDocument();
  });

  it('根据当前 locale 展示英文界面文案', () => {
    locale = 'en-US';
    renderPanel(paperPortfolio);

    expect(screen.getByText('Paper Trading Console')).toBeInTheDocument();
    expect(screen.getByText('Paper Trading Only')).toBeInTheDocument();
    expect(screen.getByText('Provider-priced')).toBeInTheDocument();
    expect(screen.getByText('Paper Account')).toBeInTheDocument();
  });
});

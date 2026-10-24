import { cleanup, render, screen, within } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import enUS from '../../locales/en-US/terminal';
import zhCN from '../../locales/zh-CN/terminal';
import { PortfolioRiskPanel } from './PortfolioRiskPanel';
import type { PortfolioSnapshot } from './types';

let locale = 'zh-CN';

vi.mock('@ant-design/icons', () => ({
  QuestionCircleOutlined: () => null,
  SafetyCertificateOutlined: () => null,
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

const portfolio: PortfolioSnapshot = {
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
  positions: [],
  orders: [],
  riskMetrics: [
    {
      labelId: 'terminal.metric.grossExposure',
      value: 0.8494,
      valueFormat: 'percent',
      tone: 'warning',
    },
    {
      labelId: 'terminal.metric.netExposure',
      value: 0.8494,
      valueFormat: 'percent',
    },
    {
      labelId: 'terminal.metric.largestPositionWeight',
      value: 0.3798,
      valueFormat: 'percent',
      tone: 'warning',
    },
    {
      labelId: 'terminal.metric.cashWeight',
      value: 0.1506,
      valueFormat: 'percent',
    },
  ],
  riskFlags: ['单一持仓权重超过 30% 风险约束'],
};

const renderPanel = (value: PortfolioSnapshot) =>
  render(
    <App>
      <PortfolioRiskPanel portfolio={value} />
    </App>,
  );

describe('PortfolioRiskPanel', () => {
  beforeEach(() => {
    locale = 'zh-CN';
  });

  afterEach(() => {
    cleanup();
  });

  it('展示组合敞口、集中度、现金权重和普通风险提示', () => {
    renderPanel(portfolio);

    expect(screen.getByText('交易边界')).toBeInTheDocument();

    const grossExposure = screen.getByText('总敞口 Gross Exposure').closest('.terminal-metric');
    const largestPosition = screen.getByText('最大持仓权重').closest('.terminal-metric');
    const cashWeight = screen.getByText('现金权重 Cash Weight').closest('.terminal-metric');

    expect(grossExposure).not.toBeNull();
    expect(largestPosition).not.toBeNull();
    expect(cashWeight).not.toBeNull();
    expect(within(grossExposure as HTMLElement).getByTitle('+84.94%')).toBeInTheDocument();
    expect(within(largestPosition as HTMLElement).getByTitle('+37.98%')).toBeInTheDocument();
    expect(within(cashWeight as HTMLElement).getByTitle('+15.06%')).toBeInTheDocument();

    const ordinaryRisk = screen.getByText('单一持仓权重超过 30% 风险约束').closest('.terminal-risk-item');
    expect(ordinaryRisk).not.toBeNull();
    expect(ordinaryRisk).not.toHaveClass('terminal-risk-item-fallback');
    expect(screen.queryByText('数据源回退中')).not.toBeInTheDocument();
    expect(screen.queryByText('行情回退')).not.toBeInTheDocument();
  });

  it('区分数据库组合回退与持仓行情回退', () => {
    renderPanel({
      ...portfolio,
      riskFlags: [
        '数据库组合快照读取失败，当前页面已回退到服务层组合摘要。',
        '真实持仓行情读取失败，当前页面已回退到 Mock 组合估值。',
      ],
    });

    expect(screen.getByText('数据源回退中')).toBeInTheDocument();
    expect(screen.getByText('行情回退')).toBeInTheDocument();

    for (const flag of [
      '数据库组合快照读取失败，当前页面已回退到服务层组合摘要。',
      '真实持仓行情读取失败，当前页面已回退到 Mock 组合估值。',
    ]) {
      expect(screen.getByText(flag).closest('.terminal-risk-item')).toHaveClass(
        'terminal-risk-item-fallback',
      );
    }
  });

  it('识别英文回退原因并使用英文界面标签', () => {
    locale = 'en-US';
    renderPanel({
      ...portfolio,
      riskFlags: [
        'Database portfolio snapshot read failed; using service snapshot.',
        'Provider quote unavailable; market=HK; symbol=00700.HK.',
      ],
    });

    expect(screen.getByText('Trading Boundary')).toBeInTheDocument();
    expect(screen.getByText('Provider fallback')).toBeInTheDocument();
    expect(screen.getByText('Quote fallback')).toBeInTheDocument();
  });
});

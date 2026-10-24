import { cleanup, render, screen, within } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, describe, expect, it, vi } from 'vitest';
import zhCN from '../../locales/zh-CN/terminal';
import type {
  PreTradeRiskCheckResponse,
  RiskCheckDecision,
} from './apiTypes';
import { PreTradeRiskCheckPanel } from './PreTradeRiskCheckPanel';
import type { PortfolioSnapshot } from './types';

vi.mock('@ant-design/icons', () => ({
  SafetyCertificateOutlined: () => null,
}));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: 'zh-CN',
    formatMessage: ({ id, defaultMessage }: { id?: string; defaultMessage?: string }) =>
      (id && zhCN[id as keyof typeof zhCN]) || defaultMessage || id || '',
  }),
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

const createReceipt = (
  overrides: Partial<PreTradeRiskCheckResponse> = {},
): PreTradeRiskCheckResponse => ({
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
  ...overrides,
});

const renderPanel = (receipt: PreTradeRiskCheckResponse) =>
  render(
    <App>
      <PreTradeRiskCheckPanel portfolio={portfolio} receipt={receipt} />
    </App>,
  );

afterEach(() => {
  cleanup();
});

describe('PreTradeRiskCheckPanel', () => {
  it('展示预计资金、权重、检查时间和模拟风控边界', () => {
    renderPanel(createReceipt());

    expect(screen.getByText('下单前风险检查回执')).toBeInTheDocument();
    expect(screen.getByText('通过 Approved')).toBeInTheDocument();
    expect(screen.getByText('00700.HK')).toBeInTheDocument();
    expect(screen.getByText('2026/10/16 10:00:00')).toBeInTheDocument();

    const orderValue = screen.getByText('预计订单金额').closest('span');
    const cash = screen.getByText('预计现金').closest('span');
    const cashWeight = screen.getByText('预计现金权重').closest('span');
    const positionWeight = screen.getByText('预计持仓权重').closest('span');

    expect(orderValue).not.toBeNull();
    expect(cash).not.toBeNull();
    expect(cashWeight).not.toBeNull();
    expect(positionWeight).not.toBeNull();
    expect(within(orderValue as HTMLElement).getByText(/610\.00/)).toBeInTheDocument();
    expect(within(cash as HTMLElement).getByText(/24,390\.00/)).toBeInTheDocument();
    expect(within(cashWeight as HTMLElement).getByText('+24.39%')).toBeInTheDocument();
    expect(within(positionWeight as HTMLElement).getByText('+61.61%')).toBeInTheDocument();
    expect(screen.getByText(/后端创建模拟订单时仍会再次执行风险检查/)).toBeInTheDocument();
  });

  it.each<[
    RiskCheckDecision,
    string,
  ]>([
    ['approved', '通过 Approved'],
    ['warning', '提示 Warning'],
    ['rejected', '拒绝 Rejected'],
  ])('风险结论 %s 显示对应标签', (decision, label) => {
    renderPanel(createReceipt({ decision }));

    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it('根据原因严重程度区分普通提示与关键风险', () => {
    renderPanel(
      createReceipt({
        decision: 'rejected',
        reasons: [
          {
            code: 'POSITION_INFO',
            message: '预计持仓权重接近限制',
            severity: 'info',
          },
          {
            code: 'POSITION_WARNING',
            message: '预计持仓集中度较高',
            severity: 'warning',
          },
          {
            code: 'CASH_CRITICAL',
            message: '预计现金权重低于最低限制',
            severity: 'critical',
          },
        ],
      }),
    );

    expect(screen.getByText('预计持仓权重接近限制')).toHaveClass(
      'terminal-tone-warning',
    );
    expect(screen.getByText('预计持仓集中度较高')).toHaveClass(
      'terminal-tone-warning',
    );
    expect(screen.getByText('预计现金权重低于最低限制')).toHaveClass(
      'terminal-tone-negative',
    );
  });
});

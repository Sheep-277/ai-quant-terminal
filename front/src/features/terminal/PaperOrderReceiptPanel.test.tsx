import { cleanup, render, screen, within } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, describe, expect, it, vi } from 'vitest';
import zhCN from '../../locales/zh-CN/terminal';
import type { PaperOrderCreateResponse, PaperOrderStatus } from './apiTypes';
import { PaperOrderReceiptPanel } from './PaperOrderReceiptPanel';
import type { PortfolioSnapshot } from './types';

vi.mock('@ant-design/icons', () => ({
  WalletOutlined: () => null,
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
  overrides: Partial<PaperOrderCreateResponse> = {},
): PaperOrderCreateResponse => ({
  order_id: 'paper-order-001',
  account_id: 'paper-hk-001',
  market: 'HK',
  symbol: '00700.HK',
  side: 'buy',
  quantity: 100,
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
  ...overrides,
});

const renderPanel = (receipt: PaperOrderCreateResponse) =>
  render(
    <App>
      <PaperOrderReceiptPanel portfolio={portfolio} receipt={receipt} />
    </App>,
  );

afterEach(() => {
  cleanup();
});

describe('PaperOrderReceiptPanel', () => {
  it('展示模拟订单字段、风控结论和格式化时间', () => {
    renderPanel(createReceipt());

    expect(screen.getByText('模拟订单接收回执')).toBeInTheDocument();
    expect(screen.getByText('已提交')).toBeInTheDocument();
    expect(screen.getByText('paper-order-001')).toBeInTheDocument();
    expect(screen.getByText('00700.HK')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
    expect(screen.getByText('是')).toBeInTheDocument();
    expect(screen.getByText('通过 Approved')).toBeInTheDocument();
    expect(screen.getByText('2026/10/16 10:00:00')).toBeInTheDocument();

    const priceMeta = screen.getByText('价格').closest('span');
    expect(priceMeta).not.toBeNull();
    expect(within(priceMeta as HTMLElement).getByText(/610\.00/)).toBeInTheDocument();
    expect(screen.getByText(/不代表真实成交，也不会连接券商账户/)).toBeInTheDocument();
  });

  it.each<[
    PaperOrderStatus,
    string,
    RegExp,
  ]>([
    ['submitted', '已提交', /模拟请求已提交/],
    ['filled', '已成交', /不代表真实券商成交/],
    ['cancelled', '已撤销', /不涉及真实券商撤单/],
    ['rejected', '已拒绝', /没有写入真实交易订单/],
  ])('订单状态 %s 显示对应状态和边界说明', (status, label, description) => {
    renderPanel(createReceipt({ status }));

    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.getByText(description)).toBeInTheDocument();
  });

  it('按照风控结论展示警告或拒绝原因', () => {
    const { rerender } = render(
      <App>
        <PaperOrderReceiptPanel
          portfolio={portfolio}
          receipt={createReceipt({
            risk_decision: 'warning',
            risk_reason_codes: ['POSITION_LIMIT'],
            risk_reasons: ['预计持仓集中度较高'],
          })}
        />
      </App>,
    );

    expect(screen.getByText('提示 Warning')).toBeInTheDocument();
    expect(screen.getByText('预计持仓集中度较高')).toHaveClass(
      'terminal-tone-warning',
    );

    rerender(
      <App>
        <PaperOrderReceiptPanel
          portfolio={portfolio}
          receipt={createReceipt({
            risk_decision: 'rejected',
            risk_reason_codes: ['CASH_LIMIT'],
            risk_reasons: ['预计现金权重低于限制'],
          })}
        />
      </App>,
    );

    expect(screen.getByText('拒绝 Rejected')).toBeInTheDocument();
    expect(screen.getByText('预计现金权重低于限制')).toHaveClass(
      'terminal-tone-negative',
    );
  });

  it('fallback 回执明确展示降级原因', () => {
    renderPanel(
      createReceipt({
        fallback_active: true,
        fallback_reason: '数据库写入不可用，订单仅保留在 Mock 回执中。',
        data_status: 'unavailable',
        storage_source: 'mock_fallback',
      }),
    );

    expect(screen.getAllByText('数据源回退中')).toHaveLength(2);
    const fallbackReason = screen.getByText(
      '数据库写入不可用，订单仅保留在 Mock 回执中。',
    );
    expect(fallbackReason.closest('.terminal-risk-item')).toHaveClass(
      'terminal-risk-item-fallback',
    );
  });

  it('无指定价格且未执行风险检查时显示明确空值', () => {
    renderPanel(
      createReceipt({
        limit_price: null,
        risk_checked: false,
        risk_decision: 'warning',
      }),
    );

    const priceMeta = screen.getByText('价格').closest('span');
    expect(priceMeta).not.toBeNull();
    expect(within(priceMeta as HTMLElement).getByText('-')).toBeInTheDocument();
    expect(screen.getByText('否')).toBeInTheDocument();
  });
});

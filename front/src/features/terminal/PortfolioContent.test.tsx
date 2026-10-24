import { cleanup, render, screen } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, describe, expect, it, vi } from 'vitest';
import zhCN from '../../locales/zh-CN/terminal';
import type {
  PaperOrderCreateResponse,
  PreTradeRiskCheckResponse,
} from './apiTypes';
import { PortfolioContent } from './PortfolioContent';
import type { PortfolioSnapshot } from './types';

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

vi.mock('./PortfolioSummaryPanel', () => ({
  PortfolioSummaryPanel: ({ portfolio }: { portfolio: PortfolioSnapshot }) => (
    <div data-testid="portfolio-summary">{portfolio.account.accountId}</div>
  ),
}));

vi.mock('./PortfolioRiskPanel', () => ({
  PortfolioRiskPanel: ({ portfolio }: { portfolio: PortfolioSnapshot }) => (
    <div data-testid="portfolio-risk">{portfolio.market}</div>
  ),
}));

vi.mock('./PortfolioTables', () => ({
  PortfolioTables: ({ portfolio }: { portfolio: PortfolioSnapshot }) => (
    <div data-testid="portfolio-tables">{portfolio.positions.length}</div>
  ),
}));

vi.mock('./PreTradeRiskCheckPanel', () => ({
  PreTradeRiskCheckPanel: ({
    receipt,
  }: {
    receipt: PreTradeRiskCheckResponse;
  }) => <div data-testid="risk-check-receipt">{receipt.decision}</div>,
}));

vi.mock('./PaperOrderReceiptPanel', () => ({
  PaperOrderReceiptPanel: ({ receipt }: { receipt: PaperOrderCreateResponse }) => (
    <div data-testid="paper-order-receipt">{receipt.status}</div>
  ),
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

const renderContent = (
  value: PortfolioSnapshot,
  receipts: {
    paperOrderReceipt?: PaperOrderCreateResponse;
    preTradeRiskCheckReceipt?: PreTradeRiskCheckResponse;
  } = {},
) =>
  render(
    <App>
      <PortfolioContent portfolio={value} {...receipts} />
    </App>,
  );

afterEach(() => {
  cleanup();
});

describe('PortfolioContent', () => {
  it('aligns account and risk panels in one row and gives the boundary and tables separate full-width rows', () => {
    const { container } = renderContent(portfolio);
    const layout = container.querySelector('.terminal-portfolio-layout') as HTMLElement;
    const primary = layout.querySelector('.terminal-portfolio-primary-row') as HTMLElement;
    expect(primary.children).toHaveLength(2);
    expect(screen.getByRole('alert').parentElement).toBe(layout);
    expect(screen.getByTestId('portfolio-summary').parentElement).toHaveClass('terminal-portfolio-summary');
    expect(screen.getByTestId('portfolio-risk').parentElement).toHaveClass('terminal-portfolio-risk');
    expect(screen.getByTestId('portfolio-tables').closest('.terminal-portfolio-table-area')?.parentElement).toBe(layout);
    expect(layout.querySelector('.terminal-portfolio-receipts')).toBeNull();
  });

  it('places both receipts below the account row without nesting or hiding them in risk details', () => {
    const { container } = renderContent(portfolio, { preTradeRiskCheckReceipt: riskReceipt, paperOrderReceipt: orderReceipt });
    const layout = container.querySelector('.terminal-portfolio-layout') as HTMLElement;
    const receipts = layout.querySelector('.terminal-portfolio-receipts') as HTMLElement;
    expect(receipts.parentElement).toBe(layout);
    expect(receipts.children).toHaveLength(2);
    expect(screen.getByTestId('risk-check-receipt').parentElement).toBe(receipts);
    expect(screen.getByTestId('paper-order-receipt').parentElement).toBe(receipts);
    expect(layout.children[1]).toHaveClass('terminal-portfolio-primary-row');
    expect(layout.children[2]).toBe(receipts);
    expect(layout.children[3]).toHaveClass('terminal-portfolio-table-area');
  });
  it('paper 模式展示公开行情重估边界和基础组合区域', () => {
    renderContent(portfolio);

    expect(screen.getByText('模拟组合数据边界')).toBeInTheDocument();
    expect(
      screen.getByText(/当前账户 paper-hk-001 使用 Paper 模拟账户，市场为 HK/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Provider 公开行情重估/)).toBeInTheDocument();
    expect(screen.getByTestId('portfolio-summary')).toHaveTextContent('paper-hk-001');
    expect(screen.getByTestId('portfolio-risk')).toHaveTextContent('HK');
    expect(screen.getByTestId('portfolio-tables')).toHaveTextContent('0');
    expect(screen.queryByTestId('risk-check-receipt')).not.toBeInTheDocument();
    expect(screen.queryByTestId('paper-order-receipt')).not.toBeInTheDocument();
  });

  it('Mock 模式切换为本地快照边界说明', () => {
    renderContent({ ...portfolio, dataMode: 'mock' });

    expect(
      screen.getByText(/当前账户 paper-hk-001 使用 Mock 模拟数据，市场为 HK/),
    ).toBeInTheDocument();
    expect(screen.getByText(/来自本地 Mock 快照/)).toBeInTheDocument();
    expect(screen.queryByText(/Provider 公开行情重估/)).not.toBeInTheDocument();
  });

  it('只在收到风险检查结果后显示风险回执', () => {
    renderContent(portfolio, { preTradeRiskCheckReceipt: riskReceipt });

    expect(screen.getByTestId('risk-check-receipt')).toHaveTextContent('approved');
    expect(screen.queryByTestId('paper-order-receipt')).not.toBeInTheDocument();
  });

  it('只在收到订单结果后显示模拟订单回执', () => {
    renderContent(portfolio, { paperOrderReceipt: orderReceipt });

    expect(screen.getByTestId('paper-order-receipt')).toHaveTextContent('submitted');
    expect(screen.queryByTestId('risk-check-receipt')).not.toBeInTheDocument();
  });
});

import { describe, expect, it } from 'vitest';
import {
  buildPaperOrderCreatePayload,
  buildPreTradeRiskCheckPayload,
} from './portfolioOrderPayloads';
import type { PortfolioSnapshot } from './types';

const portfolio: PortfolioSnapshot = {
  market: 'HK',
  timestamp: '2026-10-15T02:00:00Z',
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
    updatedAt: '2026-10-15T02:00:00Z',
  },
  accountMetrics: [],
  positions: [
    {
      key: 'position-00700',
      market: 'HK',
      symbol: '00700.HK',
      name: '腾讯控股',
      quantity: 100,
      averageCost: 580,
      lastPrice: 610,
      marketValue: 61000,
      weight: 0.61,
      unrealizedPnl: 3000,
      unrealizedPnlPercent: 0.0517,
    },
    {
      key: 'position-09988',
      market: 'HK',
      symbol: '09988.HK',
      name: '阿里巴巴-W',
      quantity: 200,
      averageCost: 68,
      lastPrice: 70,
      marketValue: 14000,
      weight: 0.14,
      unrealizedPnl: 400,
      unrealizedPnlPercent: 0.0294,
    },
  ],
  orders: [],
  riskMetrics: [],
  riskFlags: [],
};

describe('portfolioOrderPayloads', () => {
  it('使用第一条持仓构造最小模拟买入订单', () => {
    expect(buildPaperOrderCreatePayload(portfolio)).toEqual({
      account_id: 'paper-hk-001',
      market: 'HK',
      symbol: '00700.HK',
      side: 'buy',
      quantity: 1,
      limit_price: 610,
      paper_trading: true,
    });
  });

  it('构造包含账户资金、全部持仓和风控阈值的检查请求', () => {
    expect(buildPreTradeRiskCheckPayload(portfolio)).toEqual({
      account_id: 'paper-hk-001',
      market: 'HK',
      symbol: '00700.HK',
      side: 'buy',
      quantity: 1,
      limit_price: 610,
      nav: 100000,
      cash: 25000,
      current_positions: [
        {
          market: 'HK',
          symbol: '00700.HK',
          market_value: 61000,
          side: 'long',
        },
        {
          market: 'HK',
          symbol: '09988.HK',
          market_value: 14000,
          side: 'long',
        },
      ],
      max_position_weight: 0.3,
      min_cash_weight: 0.05,
      paper_trading: true,
    });
  });

  it.each([
    ['模拟订单', buildPaperOrderCreatePayload],
    ['下单前风险检查', buildPreTradeRiskCheckPayload],
  ])('没有持仓时拒绝构造%s请求', (_name, buildPayload) => {
    expect(() => buildPayload({ ...portfolio, positions: [] })).toThrow(
      'Portfolio position is required to create a mock paper order.',
    );
  });
});

import { request } from '@umijs/max';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  PaperOrderCreateResponse,
  PaperOrderRequest,
  PortfolioResponse,
} from '@/features/terminal/apiTypes';
import {
  createPaperOrder,
  getPortfolioAccountSummary,
  getPortfolioSummary,
} from './portfolio';

vi.mock('@umijs/max', () => ({
  request: vi.fn(),
}));

const portfolioResponse: PortfolioResponse = {
  market: 'HK',
  timestamp: '2026-10-17T02:00:00Z',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  data_mode: 'paper',
  account: {
    account_id: 'paper-hk-001',
    market: 'HK',
    currency: 'HKD',
    nav: 100_000,
    cash: 25_000,
    market_value: 75_000,
    daily_pnl: 800,
    total_pnl: 5_000,
    total_return: 0.05,
    updated_at: '2026-10-17T02:00:00Z',
  },
  positions: [],
  orders: [],
  risk: {
    gross_exposure: 0.75,
    net_exposure: 0.75,
    largest_position_weight: 0.4,
    cash_weight: 0.25,
    risk_flags: [],
  },
};

const paperOrderPayload: PaperOrderRequest = {
  account_id: 'paper-hk-001',
  market: 'HK',
  symbol: '00700.HK',
  side: 'buy',
  quantity: 100,
  limit_price: 610,
  paper_trading: true,
};

const paperOrderResponse: PaperOrderCreateResponse = {
  order_id: 'paper-order-001',
  account_id: 'paper-hk-001',
  market: 'HK',
  symbol: '00700.HK',
  side: 'buy',
  quantity: 100,
  limit_price: 610,
  status: 'submitted',
  submitted_at: '2026-10-17T02:01:00Z',
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

describe('portfolio service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('按市场获取模拟组合总览并透传响应', async () => {
    vi.mocked(request).mockResolvedValue(portfolioResponse);

    await expect(getPortfolioSummary({ market: 'HK' })).resolves.toEqual(
      portfolioResponse,
    );
    expect(request).toHaveBeenCalledWith('/api/v1/portfolio/summary', {
      method: 'GET',
      params: { market: 'HK' },
    });
  });

  it('编码账户 ID 后获取指定模拟账户详情', async () => {
    vi.mocked(request).mockResolvedValue(portfolioResponse);

    await expect(
      getPortfolioAccountSummary({ accountId: 'paper/HK?version=1' }),
    ).resolves.toEqual(portfolioResponse);
    expect(request).toHaveBeenCalledWith(
      '/api/v1/portfolio/accounts/paper%2FHK%3Fversion%3D1/summary',
      { method: 'GET' },
    );
  });

  it('向模拟订单路径提交完整纸面交易参数', async () => {
    vi.mocked(request).mockResolvedValue(paperOrderResponse);

    await expect(createPaperOrder(paperOrderPayload)).resolves.toEqual(
      paperOrderResponse,
    );
    expect(request).toHaveBeenCalledWith('/api/v1/paper/orders', {
      method: 'POST',
      data: paperOrderPayload,
    });
    expect(paperOrderPayload.paper_trading).toBe(true);
    expect(paperOrderResponse).toMatchObject({
      status: 'submitted',
      risk_checked: true,
      risk_decision: 'approved',
    });
  });

  it('保留组合总览请求错误供页面统一处理', async () => {
    const requestError = new Error('portfolio summary unavailable');
    vi.mocked(request).mockRejectedValue(requestError);

    await expect(getPortfolioSummary({ market: 'CN' })).rejects.toBe(
      requestError,
    );
  });

  it('保留账户详情请求错误供页面统一处理', async () => {
    const requestError = new Error('portfolio account unavailable');
    vi.mocked(request).mockRejectedValue(requestError);

    await expect(
      getPortfolioAccountSummary({ accountId: 'paper-cn-001' }),
    ).rejects.toBe(requestError);
  });

  it('保留模拟订单请求错误供页面统一处理', async () => {
    const requestError = new Error('paper order unavailable');
    vi.mocked(request).mockRejectedValue(requestError);

    await expect(createPaperOrder(paperOrderPayload)).rejects.toBe(
      requestError,
    );
  });
});

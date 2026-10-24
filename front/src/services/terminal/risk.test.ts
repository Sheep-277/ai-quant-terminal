import { request } from '@umijs/max';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  PreTradeRiskCheckRequest,
  PreTradeRiskCheckResponse,
  RiskCheckDecision,
} from '@/features/terminal/apiTypes';
import { preTradeRiskCheck } from './risk';

vi.mock('@umijs/max', () => ({
  request: vi.fn(),
}));

const riskCheckPayload: PreTradeRiskCheckRequest = {
  account_id: 'paper-hk-001',
  market: 'HK',
  symbol: '00700.HK',
  side: 'buy',
  quantity: 100,
  limit_price: 610,
  nav: 100_000,
  cash: 25_000,
  current_positions: [
    {
      market: 'HK',
      symbol: '00700.HK',
      market_value: 60_000,
      side: 'long',
    },
    {
      market: 'HK',
      symbol: '09988.HK',
      market_value: 15_000,
      side: 'long',
    },
  ],
  max_position_weight: 0.3,
  min_cash_weight: 0.05,
  paper_trading: true,
};

const createRiskCheckResponse = (
  decision: RiskCheckDecision,
): PreTradeRiskCheckResponse => ({
  account_id: riskCheckPayload.account_id,
  market: riskCheckPayload.market,
  symbol: riskCheckPayload.symbol,
  side: riskCheckPayload.side,
  decision,
  risk_checked: true,
  checked_at: '2026-10-17T02:00:00Z',
  projected_order_value: 61_000,
  projected_cash: -36_000,
  projected_cash_weight: -0.36,
  projected_position_weight: 1.21,
  reasons:
    decision === 'approved'
      ? []
      : [
          {
            code: 'POSITION_WEIGHT_LIMIT',
            message: '预计持仓权重超过限制',
            severity: decision === 'rejected' ? 'critical' : 'warning',
          },
        ],
});

describe('risk service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('向下单前风险检查路径提交完整模拟账户载荷', async () => {
    const response = createRiskCheckResponse('approved');
    vi.mocked(request).mockResolvedValue(response);

    await expect(preTradeRiskCheck(riskCheckPayload)).resolves.toEqual(
      response,
    );
    expect(request).toHaveBeenCalledWith('/api/v1/risk/pre-trade-check', {
      method: 'POST',
      data: riskCheckPayload,
    });
    expect(riskCheckPayload).toMatchObject({
      paper_trading: true,
      nav: 100_000,
      cash: 25_000,
      max_position_weight: 0.3,
      min_cash_weight: 0.05,
    });
    expect(riskCheckPayload.current_positions).toHaveLength(2);
  });

  it.each<RiskCheckDecision>(['approved', 'warning', 'rejected'])(
    '保留 %s 风险结论和原因',
    async (decision) => {
      const response = createRiskCheckResponse(decision);
      vi.mocked(request).mockResolvedValue(response);

      await expect(preTradeRiskCheck(riskCheckPayload)).resolves.toEqual(
        response,
      );
      expect(response.decision).toBe(decision);
      expect(response.risk_checked).toBe(true);
      expect(response.reasons).toHaveLength(decision === 'approved' ? 0 : 1);
    },
  );

  it('保留风险检查请求错误供页面统一处理', async () => {
    const requestError = new Error('pre-trade risk check unavailable');
    vi.mocked(request).mockRejectedValue(requestError);

    await expect(preTradeRiskCheck(riskCheckPayload)).rejects.toBe(
      requestError,
    );
  });
});

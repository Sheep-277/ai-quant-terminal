import { request } from '@umijs/max';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  StrategyDraftCreateRequest,
  StrategyDraftDto,
  StrategyLabResponse,
  StrategyNaturalLanguageParseRequest,
  StrategyNaturalLanguageParseResponse,
} from '@/features/terminal/apiTypes';
import {
  createStrategyDraft,
  getStrategyLab,
  parseStrategyNaturalLanguage,
} from './strategy';

vi.mock('@umijs/max', () => ({
  request: vi.fn(),
}));

const draftPayload: StrategyDraftCreateRequest = {
  market: 'HK',
  name: 'HK Cash Flow Value Draft',
  description: '筛选现金流稳健且估值合理的港股互联网标的。',
  universe: {
    market: 'HK',
    universe_type: 'index',
    name: 'Hang Seng TECH',
    symbols: ['00700.HK', '09988.HK'],
  },
  entry_conditions: [
    {
      field: 'roe',
      operator: 'gt',
      value: 0.18,
      upper_value: null,
      description: 'ROE 大于 18%',
    },
  ],
  exit_conditions: [
    {
      field: 'rsi_14',
      operator: 'gt',
      value: 78,
      upper_value: null,
      description: 'RSI 高于 78 时退出',
    },
  ],
  position_rule: {
    max_holdings: 8,
    max_position_weight: 0.15,
    equal_weight: true,
  },
  rebalance_frequency: 'monthly',
  risk_constraints: [
    {
      max_drawdown: 0.16,
      stop_loss: 0.07,
      min_liquidity: 30_000_000,
    },
  ],
  created_by: 'user',
};

const draftResponse: StrategyDraftDto = {
  strategy_id: 'strategy-hk-quality-001',
  version: 1,
  status: 'draft',
  created_at: '2026-10-16T02:00:00Z',
  updated_at: '2026-10-16T02:00:00Z',
  parameters: {
    storage_source: 'database',
  },
  ...draftPayload,
};

const strategyLabResponse: StrategyLabResponse = {
  market: 'HK',
  timestamp: '2026-10-16T02:00:00Z',
  default_universe: draftPayload.universe,
  drafts: [draftResponse],
};

const parsePayload: StrategyNaturalLanguageParseRequest = {
  market: 'HK',
  text: 'ROE 大于 18%，RSI 高于 78 时退出，止损 7%',
  universe: draftPayload.universe,
  preferred_source: 'hybrid',
  require_user_confirmation: true,
};

const parseResponse: StrategyNaturalLanguageParseResponse = {
  market: 'HK',
  source: 'hybrid',
  confidence: 0.93,
  requires_user_confirmation: true,
  parsed_at: '2026-10-16T02:01:00Z',
  raw_text: parsePayload.text,
  result: {
    entry_conditions: draftPayload.entry_conditions,
    exit_conditions: draftPayload.exit_conditions,
    risk_constraints: draftPayload.risk_constraints,
    warnings: [],
  },
};

describe('strategy service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('按市场请求策略实验室快照', async () => {
    vi.mocked(request).mockResolvedValue(strategyLabResponse);

    await expect(getStrategyLab({ market: 'HK' })).resolves.toEqual(
      strategyLabResponse,
    );
    expect(request).toHaveBeenCalledWith('/api/v1/strategy/lab', {
      method: 'GET',
      params: { market: 'HK' },
    });
  });

  it('提交自然语言并保留股票池和人工确认标记', async () => {
    vi.mocked(request).mockResolvedValue(parseResponse);

    await expect(parseStrategyNaturalLanguage(parsePayload)).resolves.toEqual(
      parseResponse,
    );
    expect(request).toHaveBeenCalledWith(
      '/api/v1/strategy/parse-natural-language',
      {
        method: 'POST',
        data: parsePayload,
      },
    );
  });

  it('向策略创建路径提交人工确认后的草案', async () => {
    vi.mocked(request).mockResolvedValue(draftResponse);

    await expect(createStrategyDraft(draftPayload)).resolves.toEqual(
      draftResponse,
    );
    expect(request).toHaveBeenCalledWith('/api/v1/strategies', {
      method: 'POST',
      data: draftPayload,
    });
  });

  it('保留策略请求错误供页面统一错误处理', async () => {
    const requestError = new Error('strategy service unavailable');
    vi.mocked(request).mockRejectedValue(requestError);

    await expect(parseStrategyNaturalLanguage(parsePayload)).rejects.toBe(
      requestError,
    );
  });
});

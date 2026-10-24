import { describe, expect, it } from 'vitest';
import type { StrategyDraftDto } from './apiTypes';
import {
  buildBacktestTaskCreatePayload,
  buildStrategyDraftCreatePayload,
  getAIResearchSymbols,
} from './terminalActionPayloads';
import type { AIResearchSnapshot, BacktestSnapshot } from './types';

const strategyDraft: StrategyDraftDto = {
  strategy_id: 'strategy-hk-quality-001',
  name: 'HK Quality Momentum',
  version: 3,
  description: '港股质量与动量策略',
  status: 'draft',
  created_by: 'agent',
  created_at: '2026-10-16T02:00:00Z',
  updated_at: '2026-10-16T02:00:00Z',
  universe: {
    market: 'HK',
    universe_type: 'index',
    name: 'Hang Seng TECH',
    symbols: ['00700.HK', '09988.HK'],
  },
  entry_conditions: [
    {
      field: 'momentum_20d',
      operator: 'between',
      value: 0.02,
      upper_value: 0.16,
      description: '20 日动量介于 2% 到 16%',
    },
  ],
  exit_conditions: [
    {
      field: 'rsi_14',
      operator: 'gt',
      value: 78,
      upper_value: null,
      description: 'RSI 明显过热时退出',
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
  parameters: {
    fallback_active: false,
  },
};

const backtest: BacktestSnapshot = {
  backtestId: 'backtest-hk-001',
  strategyId: 'strategy-hk-quality-001',
  market: 'HK',
  status: 'completed',
  dataMode: 'historical',
  timestamp: '2026-10-16T02:00:00Z',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  benchmark: 'Hang Seng TECH',
  startDate: '2025-01-01',
  endDate: '2025-12-31',
  performanceMetrics: [
    {
      labelId: 'terminal.metric.initialCapital',
      value: 500_000,
      valueFormat: 'currency',
    },
  ],
  equityCurve: [],
  trades: [],
  assumptions: [],
};

const aiResearch: AIResearchSnapshot = {
  taskId: 'research-hk-001',
  market: 'HK',
  query: '分析港股互联网板块风险',
  status: 'completed',
  timestamp: '2026-10-16T02:00:00Z',
  timezone: 'Asia/Hong_Kong',
  dataStatus: 'delayed',
  trace: [],
  toolCalls: [],
  evidence: [
    {
      key: 'market-evidence',
      evidenceId: 'evidence-market-001',
      evidenceType: 'market_data',
      market: 'HK',
      symbol: null,
      title: '市场宽度',
      value: '上涨数量占比 52%',
      source: 'quant_pipeline',
      dataStatus: 'delayed',
      timestamp: '2026-10-16T02:00:00Z',
    },
    {
      key: 'stock-evidence',
      evidenceId: 'evidence-stock-001',
      evidenceType: 'valuation',
      market: 'HK',
      symbol: '00700.HK',
      title: '估值快照',
      value: 'PE TTM=22.4',
      source: 'database',
      dataStatus: 'delayed',
      timestamp: '2026-10-16T02:00:00Z',
    },
    {
      key: 'second-stock-evidence',
      evidenceId: 'evidence-stock-002',
      evidenceType: 'risk',
      market: 'HK',
      symbol: '09988.HK',
      title: '风险快照',
      value: '波动率上升',
      source: 'quant_pipeline',
      dataStatus: 'delayed',
      timestamp: '2026-10-16T02:00:00Z',
    },
  ],
  result: {
    headline: '板块动量与风险并存',
    direction: 'warning',
    confidence: 0.78,
    horizon: 'risk_review',
    keyPoints: [],
    riskFlags: [],
    evidenceIds: ['evidence-stock-001'],
  },
};

describe('terminalActionPayloads', () => {
  it('将策略草案转为用户确认的创建请求', () => {
    expect(buildStrategyDraftCreatePayload(strategyDraft)).toEqual({
      market: 'HK',
      name: 'HK Quality Momentum',
      description: '港股质量与动量策略',
      universe: strategyDraft.universe,
      entry_conditions: strategyDraft.entry_conditions,
      exit_conditions: strategyDraft.exit_conditions,
      position_rule: strategyDraft.position_rule,
      rebalance_frequency: 'monthly',
      risk_constraints: strategyDraft.risk_constraints,
      created_by: 'user',
    });
  });

  it('使用回测快照生成带固定费率的历史回测请求', () => {
    expect(buildBacktestTaskCreatePayload(backtest)).toEqual({
      market: 'HK',
      strategy_id: 'strategy-hk-quality-001',
      strategy_status: 'confirmed',
      data_mode: 'historical',
      start_date: '2025-01-01',
      end_date: '2025-12-31',
      sample_split_at: null,
      initial_capital: 500_000,
      benchmark: 'Hang Seng TECH',
      transaction_fee_rate: 0.0005,
      slippage_rate: 0.0005,
    });
  });

  it('回测快照没有绩效指标时使用默认初始资金', () => {
    const payload = buildBacktestTaskCreatePayload({
      ...backtest,
      performanceMetrics: [],
    });

    expect(payload.initial_capital).toBe(100_000);
  });

  it('按证据顺序选取第一个有效的 AI 研究标的', () => {
    expect(getAIResearchSymbols(aiResearch)).toEqual(['00700.HK']);
  });

  it.each([
    ['研究任务缺失', undefined],
    ['证据中没有具体标的', { ...aiResearch, evidence: aiResearch.evidence.slice(0, 1) }],
  ] as const)('%s时返回空标的列表', (_name, research) => {
    expect(getAIResearchSymbols(research)).toEqual([]);
  });
});

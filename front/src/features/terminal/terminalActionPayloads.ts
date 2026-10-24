import type { BacktestRequest, StrategyDraftCreateRequest, StrategyDraftDto } from './apiTypes';
import type { AIResearchSnapshot, BacktestSnapshot } from './types';

export const getAIResearchSymbols = (research?: AIResearchSnapshot) => {
  // 当前 Mock 创建任务只需要一个标的，真实表单接入后再支持用户输入多个 symbol。
  const symbol = research?.evidence.find((item) => item.symbol)?.symbol;
  return symbol ? [symbol] : [];
};

export const buildBacktestTaskCreatePayload = (backtest: BacktestSnapshot): BacktestRequest => {
  // 当前没有独立回测表单，先把页面展示的回测区间和数据模式转成创建请求。
  return {
    market: backtest.market,
    strategy_id: backtest.strategyId,
    strategy_status: 'confirmed',
    data_mode: backtest.dataMode,
    start_date: backtest.startDate,
    end_date: backtest.endDate,
    sample_split_at: null,
    initial_capital: backtest.performanceMetrics[0]?.value ?? 100_000,
    benchmark: backtest.benchmark,
    transaction_fee_rate: 0.0005,
    slippage_rate: 0.0005,
  };
};

export const buildStrategyDraftCreatePayload = (draft: StrategyDraftDto): StrategyDraftCreateRequest => {
  // 当前没有独立表单，先把页面展示的 Mock 草案转成创建请求，后续表单化时替换这里的输入来源。
  return {
    market: draft.universe.market,
    name: draft.name,
    description: draft.description,
    universe: draft.universe,
    entry_conditions: draft.entry_conditions,
    exit_conditions: draft.exit_conditions,
    position_rule: draft.position_rule,
    rebalance_frequency: draft.rebalance_frequency,
    risk_constraints: draft.risk_constraints,
    created_by: 'user',
  };
};

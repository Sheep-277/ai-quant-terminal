import type { AIResearchHorizon, MarketCode, MonitorProvenance } from './types';

export type DataStatus = 'realtime' | 'delayed' | 'unavailable';

export type ProviderMode = 'mock' | 'real';

export type ProviderStatusResponse = {
  provider_name: string;
  mode: ProviderMode;
  ready: boolean;
  data_status: DataStatus;
  fallback_active: boolean;
  fallback_reason: string | null;
  source_type?: string;
  active_source?: string;
  missing_configuration?: string[];
  next_action?: string | null;
  last_logged_at?: string | null;
  recent_log_count?: number;
};

export type ProviderStatusLogItem = {
  id: number;
  provider_name: string;
  mode: ProviderMode | string;
  ready: boolean;
  data_status: DataStatus;
  fallback_active: boolean;
  fallback_reason: string | null;
  checked_at: string;
};

export type ProviderStatusLogListResponse = {
  items: ProviderStatusLogItem[];
  total: number;
  database_available: boolean;
  fallback_reason: string | null;
};

export type Direction = 'positive' | 'negative' | 'neutral' | 'warning';

export type MarketIndexDto = {
  name: string;
  symbol: string;
  value: number | null;
  change_percent: number | null;
  status: DataStatus;
  source?: string;
  timestamp?: string | null;
};

export type MarketBreadthDto = {
  advancers_percent: number;
  decliners_percent: number;
  unchanged_percent: number;
  new_highs: number;
  new_lows: number;
  source: string;
  status: DataStatus;
  timestamp?: string | null;
};

export type SectorPerformanceDto = {
  name: string;
  change_percent: number;
  direction: Direction;
  source: string;
  status: DataStatus;
  timestamp?: string | null;
};

export type MarketEventDto = {
  timestamp: string;
  source: string;
  origin: 'mock_sample' | 'system' | 'news';
  title: string;
  impact: string;
  confidence: number;
};

export type MarketChartBarDto = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  data_status: DataStatus;
  source: string;
};

// 与后端 MarketOverviewResponse 保持同构，前端展示层再做本地化映射。
export type MarketOverviewResponse = {
  market: MarketCode;
  timestamp: string;
  timezone: string;
  currency: string;
  benchmark: string;
  data_status: DataStatus;
  indices: MarketIndexDto[];
  breadth: MarketBreadthDto;
  chart_bars: MarketChartBarDto[];
  sectors: SectorPerformanceDto[];
  events: MarketEventDto[];
};

export type StockAssetType = 'common_stock';

export type KLineInterval = '1d';

export type StockProfileDto = {
  market: MarketCode;
  symbol: string;
  name: string;
  asset_type: StockAssetType;
  exchange: string;
  currency: string;
  timezone: string;
  sector: string;
  industry: string;
};

export type StockQuoteDto = {
  price: number;
  change: number;
  change_percent: number;
  volume: number;
  turnover: number;
  timestamp: string | null;
  data_status: DataStatus;
};

export type ValuationMetricsDto = {
  pe_ttm: number | null;
  pb: number | null;
  ps_ttm: number | null;
  pfcf_ttm: number | null;
};

export type ProfitabilityMetricsDto = {
  roe_ttm: number | null;
  roic_ttm: number | null;
  gross_margin_ttm: number | null;
  operating_margin_ttm: number | null;
};

export type CashFlowMetricsDto = {
  fcf_ttm: number | null;
  operating_cash_flow_ttm: number | null;
  capex_ttm: number | null;
};

export type FundamentalDataStatusDto = {
  source: 'database' | 'mock_provider' | string;
  completeness: 'complete' | 'partial' | 'mock' | string;
  available_sections: string[];
  missing_sections: string[];
};

export type FactorDataStatusDto = {
  source: 'database' | 'quant_pipeline' | string;
  completeness: 'complete' | 'partial' | 'computed' | string;
  available_factors: string[];
  missing_factors: string[];
};

export type SignalDataStatusDto = {
  source: 'database' | 'quant_pipeline' | string;
  completeness: 'complete' | 'computed' | string;
  signal_count: number;
};

export type MarketDataSourceStatusDto = {
  source:
    | 'database'
    | 'provider'
    | 'mock_provider'
    | 'computed'
    | 'quant_pipeline'
    | string;
  detail: string;
  fallback_active: boolean;
  data_status: DataStatus;
};

export type TechnicalIndicatorsDto = {
  rsi_14: number | null;
  macd: number | null;
  macd_signal: number | null;
  macd_histogram: number | null;
};

export type StockFactorSnapshotDto = {
  momentum_20d: number | null;
  trend_strength: number | null;
  volatility_20d: number | null;
  quality_score: number | null;
  composite_score: number | null;
};

export type StockQuantSignalDto = {
  code: string;
  title: string;
  direction: Direction;
  severity: 'info' | 'warning' | 'critical';
  score: number;
  evidence: string[];
};

export type KLineBarDto = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type KLineSeriesDto = {
  interval: KLineInterval;
  data_status: DataStatus;
  bars: KLineBarDto[];
};

// 与后端 StockResearchResponse 保持同构，页面层再决定如何展示和本地化。
export type StockResearchResponse = {
  profile: StockProfileDto;
  quote: StockQuoteDto;
  valuation: ValuationMetricsDto;
  profitability: ProfitabilityMetricsDto;
  cash_flow: CashFlowMetricsDto;
  fundamental_data_status?: FundamentalDataStatusDto;
  technical: TechnicalIndicatorsDto;
  technical_data_source: MarketDataSourceStatusDto;
  factor_snapshot: StockFactorSnapshotDto;
  factor_data_status?: FactorDataStatusDto;
  quant_signals: StockQuantSignalDto[];
  signal_data_status?: SignalDataStatusDto;
  quote_data_source?: MarketDataSourceStatusDto;
  kline: KLineSeriesDto;
  kline_data_source?: MarketDataSourceStatusDto;
  risk_flags: string[];
  summary_points: string[];
  summary_data_source: MarketDataSourceStatusDto;
  direction: Direction;
};

export type StrategyCreatedBy = 'user' | 'agent';

export type StrategyStatus = 'draft' | 'confirmed' | 'archived';

export type UniverseType = 'index' | 'watchlist' | 'custom';

export type StrategyConditionField =
  | 'momentum_20d'
  | 'roe'
  | 'volume_ratio'
  | 'rsi_14'
  | 'pe_ttm';

export type StrategyConditionOperator = 'gt' | 'gte' | 'lt' | 'lte' | 'between';

export type RebalanceFrequency = 'daily' | 'weekly' | 'monthly';

export type StrategyParseSource = 'rule_based' | 'llm' | 'hybrid';

export type StrategyUniverseDto = {
  market: MarketCode;
  universe_type: UniverseType;
  name: string;
  symbols: string[];
};

export type StrategyConditionDto = {
  field: StrategyConditionField;
  operator: StrategyConditionOperator;
  value: number;
  upper_value: number | null;
  description: string;
};

export type PositionRuleDto = {
  max_holdings: number;
  max_position_weight: number;
  equal_weight: boolean;
};

export type RiskConstraintDto = {
  max_drawdown: number | null;
  stop_loss: number | null;
  min_liquidity: number | null;
};

export type StrategyDraftCreateRequest = {
  market: MarketCode;
  name: string;
  description: string;
  universe: StrategyUniverseDto;
  entry_conditions: StrategyConditionDto[];
  exit_conditions: StrategyConditionDto[];
  position_rule: PositionRuleDto;
  rebalance_frequency: RebalanceFrequency;
  risk_constraints: RiskConstraintDto[];
  created_by: StrategyCreatedBy;
};

export type StrategyNaturalLanguageParseRequest = {
  market: MarketCode;
  text: string;
  universe?: StrategyUniverseDto | null;
  preferred_source?: StrategyParseSource | null;
  require_user_confirmation?: boolean;
};

export type StrategyNaturalLanguageParseResult = {
  entry_conditions: StrategyConditionDto[];
  exit_conditions: StrategyConditionDto[];
  risk_constraints: RiskConstraintDto[];
  warnings: string[];
};

export type StrategyNaturalLanguageParseResponse = {
  market: MarketCode;
  source: StrategyParseSource;
  confidence: number;
  requires_user_confirmation: boolean;
  parsed_at: string;
  raw_text: string;
  result: StrategyNaturalLanguageParseResult;
};

export type StrategyDraftDto = {
  strategy_id: string;
  name: string;
  version: number;
  description: string;
  status: StrategyStatus;
  created_by: StrategyCreatedBy;
  created_at: string;
  updated_at: string;
  universe: StrategyUniverseDto;
  entry_conditions: StrategyConditionDto[];
  exit_conditions: StrategyConditionDto[];
  position_rule: PositionRuleDto;
  rebalance_frequency: RebalanceFrequency;
  risk_constraints: RiskConstraintDto[];
  parameters: Record<string, unknown>;
};

// 与后端 StrategyLabResponse 保持同构，页面层不直接拼后端字段。
export type StrategyLabResponse = {
  market: MarketCode;
  timestamp: string;
  default_universe: StrategyUniverseDto;
  drafts: StrategyDraftDto[];
};

export type BacktestStatus = 'pending' | 'completed' | 'failed';

export type BacktestDataMode = 'mock' | 'historical';

export type BacktestRequest = {
  market: MarketCode;
  strategy_id: string;
  strategy_status: StrategyStatus;
  data_mode: BacktestDataMode;
  start_date: string;
  end_date: string;
  sample_split_at: string | null;
  initial_capital: number;
  benchmark: string;
  transaction_fee_rate: number;
  slippage_rate: number;
};

export type BacktestTaskCreateResponse = {
  backtest_id: string;
  strategy_id: string;
  market: MarketCode;
  status: BacktestStatus;
  accepted_at: string;
  data_mode: BacktestDataMode;
  timezone: string;
  currency: string;
  poll_url: string;
  data_status: DataStatus;
  fallback_active: boolean;
  fallback_reason: string | null;
  storage_source: 'mock' | 'database' | 'mock_fallback' | string;
  result_data_mode: BacktestDataMode | null;
};

export type BacktestPerformanceDto = {
  initial_capital: number;
  final_value: number;
  total_return: number;
  annualized_return: number;
  benchmark_return: number;
  maximum_drawdown: number;
  sharpe_ratio: number | null;
  win_rate: number;
  trade_count: number;
};

export type EquityCurvePointDto = {
  timestamp: string;
  equity: number;
  benchmark_equity: number;
  drawdown: number;
};

export type BacktestTradeDto = {
  timestamp: string;
  market: MarketCode;
  symbol: string;
  side: string;
  quantity: number;
  price: number;
  fee: number;
  slippage: number;
};

// 与后端 BacktestResponse 保持同构，页面展示层再做字段转换和格式化。
export type BacktestResponse = {
  backtest_id: string;
  strategy_id: string;
  market: MarketCode;
  status: BacktestStatus;
  data_mode: BacktestDataMode;
  timestamp: string;
  timezone: string;
  currency: string;
  benchmark: string;
  start_date: string;
  end_date: string;
  performance: BacktestPerformanceDto;
  equity_curve: EquityCurvePointDto[];
  trades: BacktestTradeDto[];
  assumptions: string[];
};

export type PortfolioDataMode = 'mock' | 'paper';

export type PaperOrderStatus = 'submitted' | 'filled' | 'cancelled' | 'rejected';

export type PaperOrderSide = 'buy' | 'sell';

export type RiskCheckDecision = 'approved' | 'warning' | 'rejected';

// 创建模拟订单的请求 DTO，只表达 Paper Trading 意图，不承载真实交易凭证。
export type PaperOrderRequest = {
  account_id: string;
  market: MarketCode;
  symbol: string;
  side: PaperOrderSide;
  quantity: number;
  limit_price: number | null;
  paper_trading: boolean;
};

export type PortfolioAccountDto = {
  account_id: string;
  market: MarketCode;
  currency: string;
  nav: number;
  cash: number;
  market_value: number;
  daily_pnl: number;
  total_pnl: number;
  total_return: number;
  updated_at: string;
};

export type PortfolioPositionDto = {
  market: MarketCode;
  symbol: string;
  name: string;
  quantity: number;
  average_cost: number;
  last_price: number;
  market_value: number;
  weight: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
};

export type PaperOrderDto = {
  order_id: string;
  market: MarketCode;
  symbol: string;
  side: PaperOrderSide;
  quantity: number;
  limit_price: number | null;
  status: PaperOrderStatus;
  submitted_at: string;
  filled_at: string | null;
  source: 'mock_summary' | 'paper_order' | string;
};

// 创建模拟订单后的接收回执，表示请求已被系统接受，不代表真实成交。
export type PaperOrderCreateResponse = {
  order_id: string;
  account_id: string;
  market: MarketCode;
  symbol: string;
  side: PaperOrderSide;
  quantity: number;
  limit_price: number | null;
  status: PaperOrderStatus;
  submitted_at: string;
  currency: string;
  risk_checked: boolean;
  risk_decision: RiskCheckDecision;
  risk_reason_codes: string[];
  risk_reasons: string[];
  data_status: DataStatus;
  fallback_active: boolean;
  fallback_reason: string | null;
  storage_source: 'mock' | 'database' | 'mock_fallback' | string;
};

export type RiskPositionSide = 'long' | 'short';

export type RiskCheckSeverity = 'info' | 'warning' | 'critical';

export type RiskPositionInputDto = {
  market: MarketCode;
  symbol: string;
  market_value: number;
  side: RiskPositionSide;
};

// 下单前风险检查请求 DTO，只评估模拟订单风险，不创建订单。
export type PreTradeRiskCheckRequest = {
  account_id: string;
  market: MarketCode;
  symbol: string;
  side: PaperOrderSide;
  quantity: number;
  limit_price: number | null;
  nav: number;
  cash: number;
  current_positions: RiskPositionInputDto[];
  max_position_weight: number;
  min_cash_weight: number;
  paper_trading: boolean;
};

export type RiskCheckReasonDto = {
  code: string;
  message: string;
  severity: RiskCheckSeverity;
};

// 下单前风险检查响应 DTO，只表示风险结论，不表示订单已创建或已成交。
export type PreTradeRiskCheckResponse = {
  account_id: string;
  market: MarketCode;
  symbol: string;
  side: PaperOrderSide;
  decision: RiskCheckDecision;
  risk_checked: boolean;
  checked_at: string;
  projected_order_value: number;
  projected_cash: number;
  projected_cash_weight: number;
  projected_position_weight: number;
  reasons: RiskCheckReasonDto[];
};

export type PortfolioRiskSummaryDto = {
  gross_exposure: number;
  net_exposure: number;
  largest_position_weight: number;
  cash_weight: number;
  risk_flags: string[];
};

// 与后端 PortfolioResponse 保持同构，页面展示层再做字段转换和格式化。
export type PortfolioResponse = {
  market: MarketCode;
  timestamp: string;
  timezone: string;
  currency: string;
  data_mode: PortfolioDataMode;
  account: PortfolioAccountDto;
  positions: PortfolioPositionDto[];
  orders: PaperOrderDto[];
  risk: PortfolioRiskSummaryDto;
};

export type MonitorStreamStatus = 'connected' | 'reconnecting' | 'disconnected';

export type MonitorSignalSeverity = 'info' | 'warning' | 'critical';

export type MonitorSource = 'FAST_PATH' | 'AI_PATH' | 'RISK_ENGINE' | 'PROVIDER';

export type MonitorStreamHealthDto = {
  status: MonitorStreamStatus;
  latency_ms: number;
  last_heartbeat_at: string;
  reconnect_attempts: number;
  data_status: DataStatus | 'mock';
};

export type MonitorSignalDto = {
  signal_id: string;
  market: MarketCode;
  symbol: string;
  title: string;
  direction: Direction;
  severity: MonitorSignalSeverity;
  score: number;
  triggered_at: string;
  evidence: string[];
  source?: string | null;
  data_origin?: 'seed' | 'mock' | 'unknown';
};

export type MonitorEventDto = {
  event_id: string;
  market: MarketCode;
  source: MonitorSource;
  title: string;
  summary: string;
  impact: Direction;
  confidence: number;
  created_at: string;
};

// 与后端 MonitorResponse 保持同构，页面展示层再做字段转换和格式化。
export type MonitorProvenanceDto = {
  transport: MonitorProvenance['transport'];
  stream_source: MonitorProvenance['streamSource'];
  signal_source: MonitorProvenance['signalSource'];
  event_source: MonitorProvenance['eventSource'];
  heartbeat_basis: MonitorProvenance['heartbeatBasis'];
};

export type MonitorResponse = {
  market: MarketCode;
  timestamp: string;
  timezone: string;
  currency: string;
  stream: MonitorStreamHealthDto;
  provenance?: MonitorProvenanceDto;
  signals: MonitorSignalDto[];
  events: MonitorEventDto[];
};

export type MonitorCalculatedSignalsResponse = {
  market: MarketCode;
  symbol: string;
  timezone: string;
  currency: string;
  source: string;
  data_status: DataStatus;
  timestamp: string;
  bar_count: number;
  calculation_scope: 'price_only';
  signals: StockQuantSignalDto[];
};

export type ResearchTaskStatus = 'queued' | 'running' | 'completed' | 'failed';

export type ResearchAgentType =
  | 'orchestrator'
  | 'market_analyst'
  | 'fundamental'
  | 'valuation'
  | 'event'
  | 'strategy'
  | 'risk';

export type ToolCallStatus = 'pending' | 'running' | 'completed' | 'failed';

export type EvidenceType =
  | 'market_data'
  | 'fundamental'
  | 'valuation'
  | 'event'
  | 'risk'
  | 'tool_output';

export type AIResearchRequest = {
  market: MarketCode;
  query: string;
  symbols: string[];
  include_strategy_idea: boolean;
};

// 与后端 AIResearchTaskCreateResponse 保持同构，表示 Mock 任务已被 HTTP 层接收。
export type AIResearchTaskCreateResponse = {
  task_id: string;
  market: MarketCode;
  query: string;
  status: ResearchTaskStatus;
  accepted_at: string;
  timezone: string;
  data_status: DataStatus;
  poll_url: string;
  fallback_active: boolean;
  fallback_reason: string | null;
  storage_source: 'mock' | 'database' | 'mock_fallback' | string;
};

export type ResearchToolCallDto = {
  tool_call_id: string;
  agent: ResearchAgentType;
  tool_name: string;
  status: ToolCallStatus;
  started_at: string | null;
  completed_at: string | null;
  summary: string;
};

export type ResearchEvidenceDto = {
  evidence_id: string;
  evidence_type: EvidenceType;
  market: MarketCode;
  symbol: string | null;
  title: string;
  value: string;
  source: string;
  data_status: DataStatus;
  timestamp: string;
};

export type ResearchTraceStepDto = {
  step_id: string;
  agent: ResearchAgentType;
  status: ToolCallStatus;
  title: string;
  summary: string;
  started_at: string;
  completed_at: string | null;
};

export type StructuredResearchResultDto = {
  headline: string;
  direction: Direction;
  confidence: number;
  horizon: AIResearchHorizon;
  key_points: string[];
  risk_flags: string[];
  evidence_ids: string[];
};

// 与后端 AIResearchResponse 保持同构，页面展示层再做字段转换和本地化。
export type AIResearchResponse = {
  task_id: string;
  market: MarketCode;
  query: string;
  status: ResearchTaskStatus;
  timestamp: string;
  timezone: string;
  data_status: DataStatus;
  trace: ResearchTraceStepDto[];
  tool_calls: ResearchToolCallDto[];
  evidence: ResearchEvidenceDto[];
  result: StructuredResearchResultDto;
};

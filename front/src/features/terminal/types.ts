export type MarketCode = 'US' | 'HK' | 'CN';

export type TerminalPageKey =
  | 'dashboard'
  | 'stock-research'
  | 'ai-research'
  | 'strategy-lab'
  | 'backtest'
  | 'portfolio'
  | 'monitor';

export type Metric = {
  labelId: string;
  value: number;
  valueFormat?: 'number' | 'currency' | 'percent';
  change?: number;
  changeFormat?: 'number' | 'percent' | 'basisPoint';
  tone?: 'positive' | 'negative' | 'warning' | 'neutral' | 'accent';
  dataSource?: {
    source: string;
    status: 'realtime' | 'delayed' | 'unavailable';
    timestamp?: string | null;
  };
};

export type QuoteRow = {
  key: string;
  symbol: string;
  nameId: string;
  price: number;
  changePercent: number;
  volume: number;
  signalId: string;
  riskId: string;
};

export type EventRow = {
  key: string;
  time: string;
  sourceId: string;
  eventOrigin: 'mock_sample' | 'system' | 'news';
  eventTitle: string;
  impactLabel: string;
  confidence: number;
};

export type DataSourceStatus = {
  source: string;
  detail: string;
  fallbackActive: boolean;
  dataStatus: 'realtime' | 'delayed' | 'unavailable';
  timestamp?: string | null;
};

export type MarketSnapshot = {
  code: MarketCode;
  labelId: string;
  currency: string;
  timezone: string;
  benchmark: string;
  status: 'Open' | 'Closed' | 'Pre-market' | 'Lunch Break';
  updatedAt: string;
  indices: Metric[];
  breadth: Metric[];
  breadthDataSource: DataSourceStatus;
  chartBars: KLinePoint[];
  sectors: Metric[];
  sectorDataSource: DataSourceStatus;
  watchlist: QuoteRow[];
  events: EventRow[];
};

export type KLinePoint = {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type StockMetricGroup = {
  key: string;
  titleId: string;
  metrics: Metric[];
};

export type StockFactorSnapshot = {
  momentum20d: number | null;
  trendStrength: number | null;
  volatility20d: number | null;
  qualityScore: number | null;
  compositeScore: number | null;
};

export type StockFundamentalDataStatus = {
  source: 'database' | 'mock_provider' | string;
  completeness: 'complete' | 'partial' | 'mock' | string;
  availableSections: string[];
  missingSections: string[];
};

export type StockFactorDataStatus = {
  source: 'database' | 'quant_pipeline' | string;
  completeness: 'complete' | 'partial' | 'computed' | string;
  availableFactors: string[];
  missingFactors: string[];
};

export type StockSignalDataStatus = {
  source: 'database' | 'quant_pipeline' | string;
  completeness: 'complete' | 'computed' | string;
  signalCount: number;
};

export type StockMarketDataSourceStatus = DataSourceStatus;

export type StockQuantSignal = {
  key: string;
  code: string;
  title: string;
  direction: Metric['tone'];
  severity: 'info' | 'warning' | 'critical';
  score: number;
  evidence: string[];
};

export type StockResearchSnapshot = {
  market: MarketCode;
  symbol: string;
  name: string;
  exchange: string;
  currency: string;
  timezone: string;
  sector: string;
  industry: string;
  dataStatus: 'realtime' | 'delayed' | 'unavailable';
  quote: {
    price: number;
    change: number;
    changePercent: number;
    volume: number;
    turnover: number;
    timestamp: string | null;
  };
  metricGroups: StockMetricGroup[];
  fundamentalDataStatus: StockFundamentalDataStatus;
  quoteDataSource: StockMarketDataSourceStatus;
  technicalDataSource: StockMarketDataSourceStatus;
  factorSnapshot: StockFactorSnapshot;
  factorDataStatus: StockFactorDataStatus;
  quantSignals: StockQuantSignal[];
  signalDataStatus: StockSignalDataStatus;
  kline: {
    interval: '1d';
    dataStatus: 'realtime' | 'delayed' | 'unavailable';
    bars: KLinePoint[];
  };
  klineDataSource: StockMarketDataSourceStatus;
  riskFlags: string[];
  summaryPoints: string[];
  summaryDataSource: StockMarketDataSourceStatus;
  direction: Metric['tone'];
};

export type StrategyCondition = {
  field: string;
  operator: string;
  value: number;
  upperValue: number | null;
  description: string;
};

export type StrategyUniverse = {
  market: MarketCode;
  universeType: 'index' | 'watchlist' | 'custom';
  name: string;
  symbols: string[];
};

export type StrategyDraft = {
  strategyId: string;
  name: string;
  version: number;
  description: string;
  status: 'draft' | 'confirmed' | 'archived';
  createdBy: 'user' | 'agent';
  createdAt: string;
  updatedAt: string;
  universe: StrategyUniverse;
  entryConditions: StrategyCondition[];
  exitConditions: StrategyCondition[];
  positionMetrics: Metric[];
  riskMetrics: Metric[];
  rebalanceFrequency: 'daily' | 'weekly' | 'monthly';
  parameters: Record<string, unknown>;
};

export type StrategyLabSnapshot = {
  market: MarketCode;
  timestamp: string;
  defaultUniverse: StrategyUniverse;
  drafts: StrategyDraft[];
};

export type EquityCurvePoint = {
  timestamp: string;
  equity: number;
  benchmarkEquity: number;
  drawdown: number;
};

export type BacktestTrade = {
  key: string;
  timestamp: string;
  market: MarketCode;
  symbol: string;
  side: string;
  quantity: number;
  price: number;
  fee: number;
  slippage: number;
};

export type BacktestSnapshot = {
  backtestId: string;
  strategyId: string;
  market: MarketCode;
  status: 'pending' | 'completed' | 'failed';
  dataMode: 'mock' | 'historical';
  timestamp: string;
  timezone: string;
  currency: string;
  benchmark: string;
  startDate: string;
  endDate: string;
  performanceMetrics: Metric[];
  equityCurve: EquityCurvePoint[];
  trades: BacktestTrade[];
  assumptions: string[];
};

export type PortfolioAccount = {
  accountId: string;
  market: MarketCode;
  currency: string;
  nav: number;
  cash: number;
  marketValue: number;
  dailyPnl: number;
  totalPnl: number;
  totalReturn: number;
  updatedAt: string;
};

export type PortfolioPosition = {
  key: string;
  market: MarketCode;
  symbol: string;
  name: string;
  quantity: number;
  averageCost: number;
  lastPrice: number;
  marketValue: number;
  weight: number;
  unrealizedPnl: number;
  unrealizedPnlPercent: number;
};

export type PaperOrder = {
  key: string;
  orderId: string;
  market: MarketCode;
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  limitPrice: number | null;
  status: 'submitted' | 'filled' | 'cancelled' | 'rejected';
  submittedAt: string;
  filledAt: string | null;
  source: 'mock_summary' | 'paper_order' | string;
};

export type PortfolioSnapshot = {
  market: MarketCode;
  timestamp: string;
  timezone: string;
  currency: string;
  dataMode: 'mock' | 'paper';
  account: PortfolioAccount;
  accountMetrics: Metric[];
  positions: PortfolioPosition[];
  orders: PaperOrder[];
  riskMetrics: Metric[];
  riskFlags: string[];
};

export type MonitorStreamHealth = {
  status: 'connected' | 'reconnecting' | 'disconnected';
  latencyMs: number;
  lastHeartbeatAt: string;
  reconnectAttempts: number;
  dataStatus: 'realtime' | 'delayed' | 'unavailable' | 'mock';
};

export type MonitorSignal = {
  key: string;
  signalId: string;
  market: MarketCode;
  symbol: string;
  title: string;
  direction: Metric['tone'];
  severity: 'info' | 'warning' | 'critical';
  score: number;
  triggeredAt: string;
  evidence: string[];
  source?: string | null;
  dataOrigin?: 'seed' | 'mock' | 'unknown';
};

export type MonitorEvent = {
  key: string;
  eventId: string;
  market: MarketCode;
  source: 'FAST_PATH' | 'AI_PATH' | 'RISK_ENGINE' | 'PROVIDER';
  title: string;
  summary: string;
  impact: Metric['tone'];
  confidence: number;
  createdAt: string;
};

export type MonitorProvenance = {
  transport: 'rest_polling' | 'unknown';
  streamSource: 'mock' | 'unknown';
  signalSource: 'mock' | 'database' | 'unknown';
  eventSource: 'mock' | 'mixed' | 'unknown';
  heartbeatBasis: 'mock_clock' | 'latest_signal' | 'unknown';
};

export type MonitorSnapshot = {
  market: MarketCode;
  timestamp: string;
  timezone: string;
  currency: string;
  stream: MonitorStreamHealth;
  streamMetrics: Metric[];
  provenance?: MonitorProvenance;
  signals: MonitorSignal[];
  events: MonitorEvent[];
};

export type AIResearchTaskStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed';

export type AIResearchHorizon = 'short_term' | 'risk_review' | 'watchlist';

export type AIResearchAgentType =
  | 'orchestrator'
  | 'market_analyst'
  | 'fundamental'
  | 'valuation'
  | 'event'
  | 'strategy'
  | 'risk';

export type AIResearchToolCallStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed';

export type AIResearchEvidenceType =
  | 'market_data'
  | 'fundamental'
  | 'valuation'
  | 'event'
  | 'risk'
  | 'tool_output';

export type AIResearchTraceStep = {
  key: string;
  stepId: string;
  agent: AIResearchAgentType;
  status: AIResearchToolCallStatus;
  title: string;
  summary: string;
  startedAt: string;
  completedAt: string | null;
};

export type AIResearchToolCall = {
  key: string;
  toolCallId: string;
  agent: AIResearchAgentType;
  toolName: string;
  status: AIResearchToolCallStatus;
  startedAt: string | null;
  completedAt: string | null;
  summary: string;
};

export type AIResearchEvidence = {
  key: string;
  evidenceId: string;
  evidenceType: AIResearchEvidenceType;
  market: MarketCode;
  symbol: string | null;
  title: string;
  value: string;
  source: string;
  dataStatus: 'realtime' | 'delayed' | 'unavailable';
  timestamp: string;
};

export type AIResearchResult = {
  headline: string;
  direction: Metric['tone'];
  confidence: number;
  horizon: AIResearchHorizon;
  keyPoints: string[];
  riskFlags: string[];
  evidenceIds: string[];
};

export type AIResearchSnapshot = {
  taskId: string;
  market: MarketCode;
  query: string;
  status: AIResearchTaskStatus;
  timestamp: string;
  timezone: string;
  dataStatus: 'realtime' | 'delayed' | 'unavailable';
  trace: AIResearchTraceStep[];
  toolCalls: AIResearchToolCall[];
  evidence: AIResearchEvidence[];
  result: AIResearchResult;
};

export type PageDefinition = {
  key: TerminalPageKey;
  title: string;
  subtitle: string;
  primaryAction: string;
};

import type {
  AIResearchResponse,
  BacktestResponse,
  MonitorResponse,
  PortfolioResponse,
  StrategyLabResponse,
  StrategyUniverseDto,
  StockResearchResponse,
  MarketOverviewResponse,
} from './apiTypes';
import type {
  AIResearchSnapshot,
  BacktestSnapshot,
  MarketSnapshot,
  Metric,
  MonitorSnapshot,
  PortfolioSnapshot,
  StrategyLabSnapshot,
  StrategyUniverse,
  StockResearchSnapshot,
} from './types';

const indexLabelMap: Record<string, string> = {
  SPX: 'terminal.metric.sp500',
  '^GSPC': 'terminal.metric.sp500',
  NDX: 'terminal.metric.nasdaq100',
  '^NDX': 'terminal.metric.nasdaq100',
  VIX: 'terminal.metric.vix',
  '^VIX': 'terminal.metric.vix',
  HSI: 'terminal.metric.hsi',
  '^HSI': 'terminal.metric.hsi',
  HSTECH: 'terminal.metric.hstech',
  VHSI: 'terminal.metric.volIndex',
  '000300.SH': 'terminal.metric.csi300',
  '000300.SS': 'terminal.metric.csi300',
  '000001.SH': 'terminal.metric.sseComposite',
  '000001.SS': 'terminal.metric.sseComposite',
  '399006.SZ': 'terminal.metric.chiNext',
};

const sectorLabelMap: Record<string, string> = {
  Semiconductors: 'terminal.sector.semis',
  Software: 'terminal.sector.software',
  Banks: 'terminal.sector.banks',
  Energy: 'terminal.sector.energy',
  Internet: 'terminal.sector.internet',
  Property: 'terminal.sector.property',
  Biotech: 'terminal.sector.biotech',
  'EV Chain': 'terminal.sector.evChain',
  Brokerage: 'terminal.sector.brokerage',
  Liquor: 'terminal.sector.liquor',
  'AI Hardware': 'terminal.sector.aiHardware',
};

const sourceLabelMap: Record<string, string> = {
  FAST_PATH: 'terminal.source.fastPath',
  AI_PATH: 'terminal.source.aiPath',
  PROVIDER: 'terminal.source.provider',
  MARKET_RULES: 'terminal.source.marketRules',
};

const directionToneMap: Record<string, Metric['tone']> = {
  positive: 'positive',
  negative: 'negative',
  neutral: 'neutral',
  warning: 'warning',
};

const nullableMetric = (
  labelId: string,
  value: number | null,
  options: Pick<Metric, 'valueFormat' | 'tone'> = {},
  source?: string,
): Metric => ({
  labelId,
  value: value ?? 0,
  ...options,
  // 数字占位保留现有 Metric 类型；不可用标记防止页面把缺失值显示成真实的零。
  ...(value === null && source ? { dataSource: { source, status: 'unavailable' as const } } : {}),
});

const fallbackFundamentalDataStatus = {
  source: 'mock_provider',
  completeness: 'mock',
  available_sections: [],
  missing_sections: ['valuation', 'profitability', 'cash_flow'],
};

const fallbackFactorDataStatus = {
  source: 'quant_pipeline',
  completeness: 'computed',
  available_factors: [],
  missing_factors: [],
};

const fallbackSignalDataStatus = {
  source: 'quant_pipeline',
  completeness: 'computed',
  signal_count: 0,
};

const fallbackMarketDataSourceStatus = {
  source: 'mock_provider',
  detail: 'Mock Provider',
  fallback_active: false,
  data_status: 'unavailable' as const,
};

export const mergeMarketOverviewSnapshot = (
  fallback: MarketSnapshot,
  overview?: MarketOverviewResponse,
): MarketSnapshot => {
  if (!overview) {
    return fallback;
  }

  const allowedIndexLabels = new Set(fallback.indices.map((index) => index.labelId));
  const seenIndexLabels = new Set<string>();
  const indices: Metric[] = [];
  // 未知代码不能套用首个指数名称；同一指数的不同供应商别名只显示一次。
  for (const item of overview.indices) {
    const labelId = indexLabelMap[item.symbol];
    if (!labelId || !allowedIndexLabels.has(labelId) || seenIndexLabels.has(labelId)) {
      continue;
    }
    seenIndexLabels.add(labelId);
    indices.push({
      labelId,
      value: item.value ?? 0,
      change: item.change_percent ?? undefined,
      changeFormat: 'percent',
      tone: (item.change_percent ?? 0) > 0 ? 'positive' : (item.change_percent ?? 0) < 0 ? 'negative' : 'neutral',
      dataSource: {
        source: item.source ?? 'mock_provider',
        status: item.value === null ? 'unavailable' : item.status,
        timestamp: item.timestamp,
      },
    });
  }

  return {
    ...fallback,
    currency: overview.currency,
    timezone: overview.timezone,
    benchmark: overview.benchmark,
    updatedAt: overview.timestamp,
    indices,
    breadth: [
      {
        labelId: 'terminal.metric.advancers',
        value: overview.breadth.advancers_percent,
        valueFormat: 'percent',
        tone: 'positive',
      },
      {
        labelId: 'terminal.metric.decliners',
        value: overview.breadth.decliners_percent,
        valueFormat: 'percent',
        tone: 'negative',
      },
      {
        labelId: 'terminal.metric.newHighs',
        value: overview.breadth.new_highs,
        tone: 'positive',
      },
      {
        labelId: 'terminal.metric.newLows',
        value: overview.breadth.new_lows,
        tone: 'negative',
      },
    ],
    breadthDataSource: {
      source: overview.breadth.source,
      detail: '',
      fallbackActive: overview.breadth.source === 'mock_fallback',
      dataStatus: overview.breadth.status,
      timestamp: overview.breadth.timestamp,
    },
    chartBars: overview.chart_bars.map((bar) => ({
      timestamp: bar.timestamp,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      volume: bar.volume,
    })),
    sectors: overview.sectors.map((item) => ({
      labelId: sectorLabelMap[item.name] ?? fallback.sectors[0]?.labelId,
      value: item.change_percent,
      valueFormat: 'percent',
      tone: directionToneMap[item.direction] ?? 'neutral',
    })),
    sectorDataSource: {
      source: overview.sectors[0]?.source ?? 'mock_provider',
      detail: '',
      fallbackActive: overview.sectors[0]?.source === 'mock_fallback',
      dataStatus: overview.sectors[0]?.status ?? 'unavailable',
      timestamp: overview.sectors[0]?.timestamp,
    },
    events: overview.events.map((item, index) => ({
      key: `${overview.market}-${index}`,
      time: item.timestamp,
      sourceId: sourceLabelMap[item.source] ?? 'terminal.source.provider',
      eventOrigin: item.origin,
      eventTitle: item.title,
      impactLabel: item.impact,
      confidence: item.confidence,
    })),
  };
};

export const toStockResearchSnapshot = (
  research: StockResearchResponse,
): StockResearchSnapshot => ({
  market: research.profile.market,
  symbol: research.profile.symbol,
  name: research.profile.name,
  exchange: research.profile.exchange,
  currency: research.profile.currency,
  timezone: research.profile.timezone,
  sector: research.profile.sector,
  industry: research.profile.industry,
  dataStatus: research.quote.data_status,
  quote: {
    price: research.quote.price,
    change: research.quote.change,
    changePercent: research.quote.change_percent,
    volume: research.quote.volume,
    turnover: research.quote.turnover,
    timestamp: research.quote.timestamp,
  },
  metricGroups: [
    {
      key: 'valuation',
      titleId: 'terminal.tab.valuation',
      metrics: [
        nullableMetric('terminal.metric.peTtm', research.valuation.pe_ttm, {
          tone: 'warning',
        }, research.fundamental_data_status?.source ?? fallbackFundamentalDataStatus.source),
        nullableMetric('terminal.metric.pb', research.valuation.pb, {}, research.fundamental_data_status?.source ?? fallbackFundamentalDataStatus.source),
        nullableMetric('terminal.metric.psTtm', research.valuation.ps_ttm, {}, research.fundamental_data_status?.source ?? fallbackFundamentalDataStatus.source),
        nullableMetric('terminal.metric.pfcfTtm', research.valuation.pfcf_ttm, {}, research.fundamental_data_status?.source ?? fallbackFundamentalDataStatus.source),
      ],
    },
    {
      key: 'profitability',
      titleId: 'terminal.tab.fundamentals',
      metrics: [
        nullableMetric('terminal.metric.roeTtm', research.profitability.roe_ttm, {
          valueFormat: 'percent',
          tone: 'positive',
        }, research.fundamental_data_status?.source ?? fallbackFundamentalDataStatus.source),
        nullableMetric('terminal.metric.roicTtm', research.profitability.roic_ttm, {
          valueFormat: 'percent',
          tone: 'positive',
        }, research.fundamental_data_status?.source ?? fallbackFundamentalDataStatus.source),
        nullableMetric('terminal.metric.grossMarginTtm', research.profitability.gross_margin_ttm, {
          valueFormat: 'percent',
        }, research.fundamental_data_status?.source ?? fallbackFundamentalDataStatus.source),
        nullableMetric('terminal.metric.operatingMarginTtm', research.profitability.operating_margin_ttm, {
          valueFormat: 'percent',
        }, research.fundamental_data_status?.source ?? fallbackFundamentalDataStatus.source),
      ],
    },
    {
      key: 'cash-flow',
      titleId: 'terminal.metric.cashFlow',
      metrics: [
        nullableMetric('terminal.metric.fcfTtm', research.cash_flow.fcf_ttm, {
          valueFormat: 'currency',
        }, research.fundamental_data_status?.source ?? fallbackFundamentalDataStatus.source),
        nullableMetric('terminal.metric.operatingCashFlowTtm', research.cash_flow.operating_cash_flow_ttm, {
          valueFormat: 'currency',
        }, research.fundamental_data_status?.source ?? fallbackFundamentalDataStatus.source),
        nullableMetric('terminal.metric.capexTtm', research.cash_flow.capex_ttm, {
          valueFormat: 'currency',
        }, research.fundamental_data_status?.source ?? fallbackFundamentalDataStatus.source),
      ],
    },
    {
      key: 'factors',
      titleId: 'terminal.metric.factorSnapshot',
      metrics: [
        nullableMetric('terminal.metric.momentum20d', research.factor_snapshot.momentum_20d, {
          valueFormat: 'percent',
          tone: research.factor_snapshot.momentum_20d && research.factor_snapshot.momentum_20d >= 0 ? 'positive' : 'negative',
        }, research.factor_data_status?.source ?? fallbackFactorDataStatus.source),
        nullableMetric('terminal.metric.trendStrength', research.factor_snapshot.trend_strength, {
          valueFormat: 'percent',
          tone: research.factor_snapshot.trend_strength && research.factor_snapshot.trend_strength >= 0 ? 'positive' : 'negative',
        }, research.factor_data_status?.source ?? fallbackFactorDataStatus.source),
        nullableMetric('terminal.metric.volatility20d', research.factor_snapshot.volatility_20d, {
          valueFormat: 'percent',
          tone: research.factor_snapshot.volatility_20d && research.factor_snapshot.volatility_20d >= 0.45 ? 'warning' : 'neutral',
        }, research.factor_data_status?.source ?? fallbackFactorDataStatus.source),
        nullableMetric('terminal.metric.qualityScore', research.factor_snapshot.quality_score, {
          tone: 'positive',
        }, research.factor_data_status?.source ?? fallbackFactorDataStatus.source),
        nullableMetric('terminal.metric.compositeScore', research.factor_snapshot.composite_score, {
          tone: research.factor_snapshot.composite_score && research.factor_snapshot.composite_score >= 0.75 ? 'positive' : 'neutral',
        }, research.factor_data_status?.source ?? fallbackFactorDataStatus.source),
      ],
    },
    {
      key: 'technical',
      titleId: 'terminal.tab.quant',
      metrics: [
        nullableMetric('terminal.metric.rsi14', research.technical.rsi_14, {}, research.technical_data_source.source),
        nullableMetric('terminal.metric.macd', research.technical.macd, {}, research.technical_data_source.source),
        nullableMetric('terminal.metric.macdSignal', research.technical.macd_signal, {}, research.technical_data_source.source),
        nullableMetric('terminal.metric.macdHistogram', research.technical.macd_histogram, {}, research.technical_data_source.source),
      ],
    },
  ],
  fundamentalDataStatus: {
    source: (research.fundamental_data_status ?? fallbackFundamentalDataStatus).source,
    completeness: (research.fundamental_data_status ?? fallbackFundamentalDataStatus).completeness,
    availableSections: (research.fundamental_data_status ?? fallbackFundamentalDataStatus).available_sections,
    missingSections: (research.fundamental_data_status ?? fallbackFundamentalDataStatus).missing_sections,
  },
  quoteDataSource: {
    source: (research.quote_data_source ?? fallbackMarketDataSourceStatus).source,
    detail: (research.quote_data_source ?? fallbackMarketDataSourceStatus).detail,
    fallbackActive: (research.quote_data_source ?? fallbackMarketDataSourceStatus).fallback_active,
    dataStatus: (research.quote_data_source ?? fallbackMarketDataSourceStatus).data_status,
  },
  technicalDataSource: {
    source: research.technical_data_source.source,
    detail: research.technical_data_source.detail,
    fallbackActive: research.technical_data_source.fallback_active,
    dataStatus: research.technical_data_source.data_status,
  },
  factorSnapshot: {
    momentum20d: research.factor_snapshot.momentum_20d,
    trendStrength: research.factor_snapshot.trend_strength,
    volatility20d: research.factor_snapshot.volatility_20d,
    qualityScore: research.factor_snapshot.quality_score,
    compositeScore: research.factor_snapshot.composite_score,
  },
  factorDataStatus: {
    source: (research.factor_data_status ?? fallbackFactorDataStatus).source,
    completeness: (research.factor_data_status ?? fallbackFactorDataStatus).completeness,
    availableFactors: (research.factor_data_status ?? fallbackFactorDataStatus).available_factors,
    missingFactors: (research.factor_data_status ?? fallbackFactorDataStatus).missing_factors,
  },
  quantSignals: research.quant_signals.map((signal) => ({
    key: signal.code,
    code: signal.code,
    title: signal.title,
    direction: directionToneMap[signal.direction] ?? 'neutral',
    severity: signal.severity,
    score: signal.score,
    evidence: signal.evidence,
  })),
  signalDataStatus: {
    source: (research.signal_data_status ?? fallbackSignalDataStatus).source,
    completeness: (research.signal_data_status ?? fallbackSignalDataStatus).completeness,
    signalCount: (research.signal_data_status ?? fallbackSignalDataStatus).signal_count,
  },
  kline: {
    interval: research.kline.interval,
    dataStatus: research.kline.data_status,
    bars: research.kline.bars.map((bar) => ({
      timestamp: bar.timestamp,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      volume: bar.volume,
    })),
  },
  klineDataSource: {
    source: (research.kline_data_source ?? fallbackMarketDataSourceStatus).source,
    detail: (research.kline_data_source ?? fallbackMarketDataSourceStatus).detail,
    fallbackActive: (research.kline_data_source ?? fallbackMarketDataSourceStatus).fallback_active,
    dataStatus: (research.kline_data_source ?? fallbackMarketDataSourceStatus).data_status,
  },
  riskFlags: research.risk_flags,
  summaryPoints: research.summary_points,
  summaryDataSource: {
    source: research.summary_data_source.source,
    detail: research.summary_data_source.detail,
    fallbackActive: research.summary_data_source.fallback_active,
    dataStatus: research.summary_data_source.data_status,
  },
  direction: directionToneMap[research.direction] ?? 'neutral',
});

const toStrategyUniverse = (universe: StrategyUniverseDto): StrategyUniverse => ({
  market: universe.market,
  universeType: universe.universe_type,
  name: universe.name,
  symbols: universe.symbols,
});

export const toStrategyLabSnapshot = (
  strategyLab: StrategyLabResponse,
): StrategyLabSnapshot => ({
  market: strategyLab.market,
  timestamp: strategyLab.timestamp,
  defaultUniverse: toStrategyUniverse(strategyLab.default_universe),
  drafts: strategyLab.drafts.map((draft) => ({
    strategyId: draft.strategy_id,
    name: draft.name,
    version: draft.version,
    description: draft.description,
    status: draft.status,
    createdBy: draft.created_by,
    createdAt: draft.created_at,
    updatedAt: draft.updated_at,
    universe: toStrategyUniverse(draft.universe),
    entryConditions: draft.entry_conditions.map((condition) => ({
      field: condition.field,
      operator: condition.operator,
      value: condition.value,
      upperValue: condition.upper_value,
      description: condition.description,
    })),
    exitConditions: draft.exit_conditions.map((condition) => ({
      field: condition.field,
      operator: condition.operator,
      value: condition.value,
      upperValue: condition.upper_value,
      description: condition.description,
    })),
    positionMetrics: [
      {
        labelId: 'terminal.metric.maxHoldings',
        value: draft.position_rule.max_holdings,
      },
      {
        labelId: 'terminal.metric.maxPositionWeight',
        value: draft.position_rule.max_position_weight,
        valueFormat: 'percent',
        tone: 'warning',
      },
      {
        labelId: 'terminal.metric.equalWeight',
        value: draft.position_rule.equal_weight ? 1 : 0,
      },
    ],
    riskMetrics: draft.risk_constraints.flatMap((constraint) => [
      nullableMetric('terminal.metric.maxDrawdown', constraint.max_drawdown, {
        valueFormat: 'percent',
        tone: 'warning',
      }),
      nullableMetric('terminal.metric.stopLoss', constraint.stop_loss, {
        valueFormat: 'percent',
        tone: 'negative',
      }),
      nullableMetric('terminal.metric.minLiquidity', constraint.min_liquidity, {
        valueFormat: 'currency',
      }),
    ]),
    rebalanceFrequency: draft.rebalance_frequency,
    parameters: draft.parameters,
  })),
});

export const toBacktestSnapshot = (
  backtest: BacktestResponse,
): BacktestSnapshot => ({
  backtestId: backtest.backtest_id,
  strategyId: backtest.strategy_id,
  market: backtest.market,
  status: backtest.status,
  dataMode: backtest.data_mode,
  timestamp: backtest.timestamp,
  timezone: backtest.timezone,
  currency: backtest.currency,
  benchmark: backtest.benchmark,
  startDate: backtest.start_date,
  endDate: backtest.end_date,
  performanceMetrics: [
    {
      labelId: 'terminal.metric.initialCapital',
      value: backtest.performance.initial_capital,
      valueFormat: 'currency',
    },
    {
      labelId: 'terminal.metric.finalValue',
      value: backtest.performance.final_value,
      valueFormat: 'currency',
      tone: 'positive',
    },
    {
      labelId: 'terminal.metric.totalReturn',
      value: backtest.performance.total_return,
      valueFormat: 'percent',
      tone: backtest.performance.total_return >= 0 ? 'positive' : 'negative',
    },
    {
      labelId: 'terminal.metric.annualizedReturn',
      value: backtest.performance.annualized_return,
      valueFormat: 'percent',
      tone: backtest.performance.annualized_return >= 0 ? 'positive' : 'negative',
    },
    {
      labelId: 'terminal.metric.benchmarkReturn',
      value: backtest.performance.benchmark_return,
      valueFormat: 'percent',
      tone: backtest.performance.benchmark_return >= 0 ? 'positive' : 'negative',
    },
    {
      labelId: 'terminal.metric.maxDrawdown',
      value: backtest.performance.maximum_drawdown,
      valueFormat: 'percent',
      tone: 'warning',
    },
    nullableMetric('terminal.metric.sharpeRatio', backtest.performance.sharpe_ratio),
    {
      labelId: 'terminal.metric.winRate',
      value: backtest.performance.win_rate,
      valueFormat: 'percent',
      tone: 'positive',
    },
    {
      labelId: 'terminal.metric.tradeCount',
      value: backtest.performance.trade_count,
    },
  ],
  equityCurve: backtest.equity_curve.map((point) => ({
    timestamp: point.timestamp,
    equity: point.equity,
    benchmarkEquity: point.benchmark_equity,
    drawdown: point.drawdown,
  })),
  trades: backtest.trades.map((trade, index) => ({
    key: `${trade.market}-${trade.symbol}-${trade.timestamp}-${index}`,
    timestamp: trade.timestamp,
    market: trade.market,
    symbol: trade.symbol,
    side: trade.side,
    quantity: trade.quantity,
    price: trade.price,
    fee: trade.fee,
    slippage: trade.slippage,
  })),
  assumptions: backtest.assumptions,
});

export const toPortfolioSnapshot = (
  portfolio: PortfolioResponse,
): PortfolioSnapshot => ({
  market: portfolio.market,
  timestamp: portfolio.timestamp,
  timezone: portfolio.timezone,
  currency: portfolio.currency,
  dataMode: portfolio.data_mode,
  account: {
    accountId: portfolio.account.account_id,
    market: portfolio.account.market,
    currency: portfolio.account.currency,
    nav: portfolio.account.nav,
    cash: portfolio.account.cash,
    marketValue: portfolio.account.market_value,
    dailyPnl: portfolio.account.daily_pnl,
    totalPnl: portfolio.account.total_pnl,
    totalReturn: portfolio.account.total_return,
    updatedAt: portfolio.account.updated_at,
  },
  accountMetrics: [
    {
      labelId: 'terminal.metric.nav',
      value: portfolio.account.nav,
      valueFormat: 'currency',
    },
    {
      labelId: 'terminal.metric.cash',
      value: portfolio.account.cash,
      valueFormat: 'currency',
    },
    {
      labelId: 'terminal.metric.marketValue',
      value: portfolio.account.market_value,
      valueFormat: 'currency',
    },
    {
      labelId: 'terminal.metric.dailyPnl',
      value: portfolio.account.daily_pnl,
      valueFormat: 'currency',
      tone: portfolio.account.daily_pnl >= 0 ? 'positive' : 'negative',
    },
    {
      labelId: 'terminal.metric.totalPnl',
      value: portfolio.account.total_pnl,
      valueFormat: 'currency',
      tone: portfolio.account.total_pnl >= 0 ? 'positive' : 'negative',
    },
    {
      labelId: 'terminal.metric.totalReturn',
      value: portfolio.account.total_return,
      valueFormat: 'percent',
      tone: portfolio.account.total_return >= 0 ? 'positive' : 'negative',
    },
  ],
  positions: portfolio.positions.map((position) => ({
    key: `${position.market}-${position.symbol}`,
    market: position.market,
    symbol: position.symbol,
    name: position.name,
    quantity: position.quantity,
    averageCost: position.average_cost,
    lastPrice: position.last_price,
    marketValue: position.market_value,
    weight: position.weight,
    unrealizedPnl: position.unrealized_pnl,
    unrealizedPnlPercent: position.unrealized_pnl_percent,
  })),
  orders: portfolio.orders.map((order) => ({
    key: order.order_id,
    orderId: order.order_id,
    market: order.market,
    symbol: order.symbol,
    side: order.side,
    quantity: order.quantity,
    limitPrice: order.limit_price,
    status: order.status,
    submittedAt: order.submitted_at,
    filledAt: order.filled_at,
    source: order.source,
  })),
  riskMetrics: [
    {
      labelId: 'terminal.metric.grossExposure',
      value: portfolio.risk.gross_exposure,
      valueFormat: 'percent',
      tone: 'warning',
    },
    {
      labelId: 'terminal.metric.netExposure',
      value: portfolio.risk.net_exposure,
      valueFormat: 'percent',
    },
    {
      labelId: 'terminal.metric.largestPositionWeight',
      value: portfolio.risk.largest_position_weight,
      valueFormat: 'percent',
      tone: 'warning',
    },
    {
      labelId: 'terminal.metric.cashWeight',
      value: portfolio.risk.cash_weight,
      valueFormat: 'percent',
    },
  ],
  riskFlags: portfolio.risk.risk_flags,
});

export const toMonitorSnapshot = (
  monitor: MonitorResponse,
): MonitorSnapshot => ({
  market: monitor.market,
  timestamp: monitor.timestamp,
  timezone: monitor.timezone,
  currency: monitor.currency,
  // 只读取结构化来源；旧响应不根据事件文字或全局行情 Provider 推断。
  provenance: {
    transport: monitor.provenance?.transport ?? 'unknown',
    streamSource: monitor.provenance?.stream_source ?? 'unknown',
    signalSource: monitor.provenance?.signal_source ?? 'unknown',
    eventSource: monitor.provenance?.event_source ?? 'unknown',
    heartbeatBasis: monitor.provenance?.heartbeat_basis ?? 'unknown',
  },
  stream: {
    status: monitor.stream.status,
    latencyMs: monitor.stream.latency_ms,
    lastHeartbeatAt: monitor.stream.last_heartbeat_at,
    reconnectAttempts: monitor.stream.reconnect_attempts,
    dataStatus: monitor.stream.data_status,
  },
  streamMetrics: [
    {
      labelId: 'terminal.metric.latencyMs',
      value: monitor.stream.latency_ms,
      tone: monitor.stream.latency_ms > 150 ? 'warning' : 'positive',
    },
    {
      labelId: 'terminal.metric.reconnectAttempts',
      value: monitor.stream.reconnect_attempts,
      tone: monitor.stream.reconnect_attempts > 0 ? 'warning' : 'positive',
    },
    {
      labelId: 'terminal.metric.signalCount',
      value: monitor.signals.length,
      tone: 'accent',
    },
    {
      labelId: 'terminal.metric.eventCount',
      value: monitor.events.length,
      tone: 'accent',
    },
  ],
  signals: monitor.signals.map((signal) => ({
    key: signal.signal_id,
    signalId: signal.signal_id,
    market: signal.market,
    symbol: signal.symbol,
    title: signal.title,
    direction: directionToneMap[signal.direction] ?? 'neutral',
    severity: signal.severity,
    score: signal.score,
    triggeredAt: signal.triggered_at,
    source: signal.source ?? null,
    dataOrigin: signal.data_origin ?? 'unknown',
    evidence: signal.evidence,
  })),
  events: monitor.events.map((event) => ({
    key: event.event_id,
    eventId: event.event_id,
    market: event.market,
    source: event.source,
    title: event.title,
    summary: event.summary,
    impact: directionToneMap[event.impact] ?? 'neutral',
    confidence: event.confidence,
    createdAt: event.created_at,
  })),
});

export const toAIResearchSnapshot = (
  research: AIResearchResponse,
): AIResearchSnapshot => ({
  taskId: research.task_id,
  market: research.market,
  query: research.query,
  status: research.status,
  timestamp: research.timestamp,
  timezone: research.timezone,
  dataStatus: research.data_status,
  trace: research.trace.map((step) => ({
    key: step.step_id,
    stepId: step.step_id,
    agent: step.agent,
    status: step.status,
    title: step.title,
    summary: step.summary,
    startedAt: step.started_at,
    completedAt: step.completed_at,
  })),
  toolCalls: research.tool_calls.map((toolCall) => ({
    key: toolCall.tool_call_id,
    toolCallId: toolCall.tool_call_id,
    agent: toolCall.agent,
    toolName: toolCall.tool_name,
    status: toolCall.status,
    startedAt: toolCall.started_at,
    completedAt: toolCall.completed_at,
    summary: toolCall.summary,
  })),
  evidence: research.evidence.map((item) => ({
    key: item.evidence_id,
    evidenceId: item.evidence_id,
    evidenceType: item.evidence_type,
    market: item.market,
    symbol: item.symbol,
    title: item.title,
    value: item.value,
    source: item.source,
    dataStatus: item.data_status,
    timestamp: item.timestamp,
  })),
  result: {
    headline: research.result.headline,
    direction: directionToneMap[research.result.direction] ?? 'neutral',
    confidence: research.result.confidence,
    horizon: research.result.horizon,
    keyPoints: research.result.key_points,
    riskFlags: research.result.risk_flags,
    evidenceIds: research.result.evidence_ids,
  },
});

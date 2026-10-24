import { QuestionCircleOutlined } from '@ant-design/icons';
import { Tooltip } from 'antd';
import { useIntl } from '@umijs/max';

export type GlossaryKey =
  | 'PE'
  | 'PB'
  | 'ROE'
  | 'ROIC'
  | 'FCF'
  | 'RSI'
  | 'MACD'
  | 'MOMENTUM_20D'
  | 'TREND_STRENGTH'
  | 'VOLATILITY_20D'
  | 'QUALITY_SCORE'
  | 'COMPOSITE_SCORE'
  | 'SHARPE'
  | 'MAX_DRAWDOWN'
  | 'SLIPPAGE'
  | 'NAV'
  | 'GROSS_EXPOSURE'
  | 'NET_EXPOSURE'
  | 'CASH_WEIGHT'
  | 'TOTAL_RETURN'
  | 'ANNUALIZED_RETURN'
  | 'BENCHMARK_RETURN'
  | 'WIN_RATE'
  | 'TRADE_COUNT';

export const glossaryTerms: Record<GlossaryKey, { labelId: string; descriptionId: string }> = {
  PE: {
    labelId: 'terminal.glossary.pe.label',
    descriptionId: 'terminal.glossary.pe.description',
  },
  PB: {
    labelId: 'terminal.glossary.pb.label',
    descriptionId: 'terminal.glossary.pb.description',
  },
  ROE: {
    labelId: 'terminal.glossary.roe.label',
    descriptionId: 'terminal.glossary.roe.description',
  },
  ROIC: {
    labelId: 'terminal.glossary.roic.label',
    descriptionId: 'terminal.glossary.roic.description',
  },
  FCF: {
    labelId: 'terminal.glossary.fcf.label',
    descriptionId: 'terminal.glossary.fcf.description',
  },
  RSI: {
    labelId: 'terminal.glossary.rsi.label',
    descriptionId: 'terminal.glossary.rsi.description',
  },
  MACD: {
    labelId: 'terminal.glossary.macd.label',
    descriptionId: 'terminal.glossary.macd.description',
  },
  MOMENTUM_20D: {
    labelId: 'terminal.glossary.momentum20d.label',
    descriptionId: 'terminal.glossary.momentum20d.description',
  },
  TREND_STRENGTH: {
    labelId: 'terminal.glossary.trendStrength.label',
    descriptionId: 'terminal.glossary.trendStrength.description',
  },
  VOLATILITY_20D: {
    labelId: 'terminal.glossary.volatility20d.label',
    descriptionId: 'terminal.glossary.volatility20d.description',
  },
  QUALITY_SCORE: {
    labelId: 'terminal.glossary.qualityScore.label',
    descriptionId: 'terminal.glossary.qualityScore.description',
  },
  COMPOSITE_SCORE: {
    labelId: 'terminal.glossary.compositeScore.label',
    descriptionId: 'terminal.glossary.compositeScore.description',
  },
  SHARPE: {
    labelId: 'terminal.glossary.sharpe.label',
    descriptionId: 'terminal.glossary.sharpe.description',
  },
  MAX_DRAWDOWN: {
    labelId: 'terminal.glossary.maxDrawdown.label',
    descriptionId: 'terminal.glossary.maxDrawdown.description',
  },
  SLIPPAGE: {
    labelId: 'terminal.glossary.slippage.label',
    descriptionId: 'terminal.glossary.slippage.description',
  },
  NAV: {
    labelId: 'terminal.glossary.nav.label',
    descriptionId: 'terminal.glossary.nav.description',
  },
  GROSS_EXPOSURE: {
    labelId: 'terminal.glossary.grossExposure.label',
    descriptionId: 'terminal.glossary.grossExposure.description',
  },
  NET_EXPOSURE: {
    labelId: 'terminal.glossary.netExposure.label',
    descriptionId: 'terminal.glossary.netExposure.description',
  },
  CASH_WEIGHT: {
    labelId: 'terminal.glossary.cashWeight.label',
    descriptionId: 'terminal.glossary.cashWeight.description',
  },
  TOTAL_RETURN: {
    labelId: 'terminal.glossary.totalReturn.label',
    descriptionId: 'terminal.glossary.totalReturn.description',
  },
  ANNUALIZED_RETURN: {
    labelId: 'terminal.glossary.annualizedReturn.label',
    descriptionId: 'terminal.glossary.annualizedReturn.description',
  },
  BENCHMARK_RETURN: {
    labelId: 'terminal.glossary.benchmarkReturn.label',
    descriptionId: 'terminal.glossary.benchmarkReturn.description',
  },
  WIN_RATE: {
    labelId: 'terminal.glossary.winRate.label',
    descriptionId: 'terminal.glossary.winRate.description',
  },
  TRADE_COUNT: {
    labelId: 'terminal.glossary.tradeCount.label',
    descriptionId: 'terminal.glossary.tradeCount.description',
  },
};

export const metricGlossaryMap: Record<string, GlossaryKey> = {
  'terminal.metric.peTtm': 'PE',
  'terminal.metric.pb': 'PB',
  'terminal.metric.pfcfTtm': 'FCF',
  'terminal.metric.roeTtm': 'ROE',
  'terminal.metric.roicTtm': 'ROIC',
  'terminal.metric.fcfTtm': 'FCF',
  'terminal.metric.rsi14': 'RSI',
  'terminal.metric.macd': 'MACD',
  'terminal.metric.macdSignal': 'MACD',
  'terminal.metric.macdHistogram': 'MACD',
  'terminal.metric.momentum20d': 'MOMENTUM_20D',
  'terminal.metric.trendStrength': 'TREND_STRENGTH',
  'terminal.metric.volatility20d': 'VOLATILITY_20D',
  'terminal.metric.qualityScore': 'QUALITY_SCORE',
  'terminal.metric.compositeScore': 'COMPOSITE_SCORE',
  'terminal.metric.sharpeRatio': 'SHARPE',
  'terminal.metric.maxDrawdown': 'MAX_DRAWDOWN',
  'terminal.metric.nav': 'NAV',
  'terminal.metric.grossExposure': 'GROSS_EXPOSURE',
  'terminal.metric.netExposure': 'NET_EXPOSURE',
  'terminal.metric.cashWeight': 'CASH_WEIGHT',
  'terminal.metric.totalReturn': 'TOTAL_RETURN',
  'terminal.metric.annualizedReturn': 'ANNUALIZED_RETURN',
  'terminal.metric.benchmarkReturn': 'BENCHMARK_RETURN',
  'terminal.metric.winRate': 'WIN_RATE',
  'terminal.metric.tradeCount': 'TRADE_COUNT',
};

export const GlossaryTerm = ({ term, compact = false }: { term: GlossaryKey; compact?: boolean }) => {
  const intl = useIntl();
  const item = glossaryTerms[term];

  return (
    <Tooltip title={intl.formatMessage({ id: item.descriptionId })}>
      <span className={compact ? 'terminal-glossary-term terminal-glossary-term-compact' : 'terminal-glossary-term'}>
        {compact ? null : intl.formatMessage({ id: item.labelId })}
        <QuestionCircleOutlined />
      </span>
    </Tooltip>
  );
};

import { useIntl } from '@umijs/max';
import { App, Progress } from 'antd';
import { CompactDataSourceBadge } from './DataSourceBadge';
import { GlossaryTerm } from './glossary';
import { TerminalTableText } from './TerminalShared';
import { terminalTheme } from './theme';
import type { DataSourceStatus } from './types';

export const ScoreStack = () => {
  const intl = useIntl();
  const { message } = App.useApp();
  const scoreSource = {
    source: 'mock_provider',
    detail: intl.formatMessage({ id: 'terminal.dashboard.source.quantScores' }),
    fallbackActive: false,
    dataStatus: 'unavailable',
  } satisfies DataSourceStatus;
  const showPrototypeMessage = () => {
    void message.info(intl.formatMessage({ id: 'terminal.prototypeOnly' }));
  };
  const scores = [
    ['terminal.score.quant', 78],
    ['terminal.score.trend', 84],
    ['terminal.score.momentum', 82],
    ['terminal.score.fundamental', 71],
    ['terminal.score.valuation', 63],
    ['terminal.score.risk', 42],
    ['terminal.score.sentiment', 68],
  ] as const;

  return (
    <div className="terminal-score-stack">
      <div className="terminal-glossary-row">
        <CompactDataSourceBadge source={scoreSource} />
      </div>
      <div className="terminal-glossary-row">
        <GlossaryTerm term="PE" />
        <GlossaryTerm term="PB" />
        <GlossaryTerm term="ROE" />
        <GlossaryTerm term="ROIC" />
        <GlossaryTerm term="FCF" />
      </div>
      {scores.map(([labelId, value]) => (
        <div className="terminal-score-row" key={labelId}>
          <TerminalTableText>{intl.formatMessage({ id: labelId })}</TerminalTableText>
          <Progress percent={value} size="small" showInfo={false} strokeColor={value > 70 ? terminalTheme.positiveColor : terminalTheme.warningColor} railColor={terminalTheme.chartTrailColor} />
          <button type="button" onClick={showPrototypeMessage}>{intl.formatMessage({ id: 'terminal.action.why' })}</button>
        </div>
      ))}
    </div>
  );
};

export const ResearchTrace = () => {
  const intl = useIntl();
  const steps = [
    'terminal.trace.taskStarted',
    'terminal.trace.marketDataLoaded',
    'terminal.trace.metricsCalculated',
    'terminal.trace.eventAgentCompleted',
    'terminal.trace.riskAgentCompleted',
    'terminal.trace.evidenceAttached',
  ];

  return (
    <div className="terminal-trace">
      {steps.map((step, index) => (
        <div className="terminal-trace-row" key={step}>
          <span>{String(index + 1).padStart(2, '0')}</span>
          <TerminalTableText className="terminal-trace-title">
            {intl.formatMessage({ id: step })}
          </TerminalTableText>
          <em>{intl.formatMessage({ id: index < 4 ? 'terminal.status.completed' : 'terminal.status.queued' })}</em>
        </div>
      ))}
    </div>
  );
};

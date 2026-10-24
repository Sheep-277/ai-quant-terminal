import { useIntl } from '@umijs/max';
import { Tooltip } from 'antd';
import type { ReactNode } from 'react';
import { formatCurrency, formatDateTime, formatNumber, formatPercent } from './formatters';
import { getDataSourceLabelText } from './DataSourceBadge';
import { GlossaryTerm, metricGlossaryMap } from './glossary';
import { getToneClass } from './mockData';
import { useMarket } from './MarketContext';
import { terminalTheme } from './theme';
import type { Metric } from './types';

const useLocaleCode = () => {
  const intl = useIntl();
  return intl.locale?.startsWith('en') ? 'en-US' : 'zh-CN';
};

const shouldUseCompactMetricValue = (value: number) => Math.abs(value) >= 100_000;

const formatMetricValue = (metric: Metric, market: ReturnType<typeof useMarket>['market'], locale: string) => {
  const compactOptions = shouldUseCompactMetricValue(metric.value)
    ? { notation: 'compact' as const, maximumFractionDigits: 1 }
    : {};

  if (metric.valueFormat === 'currency') return formatCurrency(metric.value, market, compactOptions);
  if (metric.valueFormat === 'percent') return formatPercent(metric.value, {}, locale);
  return formatNumber(metric.value, compactOptions, locale);
};

const formatFullMetricValue = (metric: Metric, market: ReturnType<typeof useMarket>['market'], locale: string) => {
  if (metric.valueFormat === 'currency') return formatCurrency(metric.value, market);
  if (metric.valueFormat === 'percent') return formatPercent(metric.value, {}, locale);
  return formatNumber(metric.value, {}, locale);
};

const formatMetricChange = (metric: Metric, locale: string) => {
  if (typeof metric.change !== 'number') return null;
  if (metric.changeFormat === 'basisPoint') return `${metric.change > 0 ? '+' : ''}${formatNumber(metric.change, {}, locale)} bp`;
  if (metric.changeFormat === 'percent') return formatPercent(metric.change, {}, locale);
  return formatNumber(metric.change, { signDisplay: 'exceptZero' }, locale);
};

export const MetricStrip = ({ metrics, market }: { metrics: Metric[]; market?: ReturnType<typeof useMarket>['market'] }) => {
  const intl = useIntl();
  const locale = useLocaleCode();
  const marketState = useMarket();
  const currentMarket = market ?? marketState.market;

  return (
    <div className="terminal-metric-strip">
      {metrics.map((metric) => {
        const unavailable = metric.dataSource?.status === 'unavailable';
        const changeText = unavailable ? null : formatMetricChange(metric, locale);
        const source = metric.dataSource;
        const sourceText = source
          ? `${getDataSourceLabelText(source.source, intl)} · ${intl.formatMessage({ id: `terminal.dataStatus.${source.status}` })}`
          : null;
        const timeText = source?.timestamp
          ? formatDateTime(source.timestamp, { timezone: marketState.snapshot.timezone, locale })
          : intl.formatMessage({ id: 'terminal.footer.time.unavailable' });

        return (
          <div className="terminal-metric" key={metric.labelId}>
            <span>
              {intl.formatMessage({ id: metric.labelId })}
              {metricGlossaryMap[metric.labelId] ? <GlossaryTerm term={metricGlossaryMap[metric.labelId]} compact /> : null}
            </span>
            <strong title={unavailable ? intl.formatMessage({ id: 'terminal.dataStatus.unavailable' }) : formatFullMetricValue(metric, currentMarket, locale)}>
              {unavailable ? '--' : formatMetricValue(metric, currentMarket, locale)}
            </strong>
            {changeText ? <em className={getToneClass(metric.tone)}>{changeText}</em> : null}
            {sourceText ? <Tooltip title={`${sourceText} · ${timeText}`}><span>{sourceText}</span></Tooltip> : null}
          </div>
        );
      })}
    </div>
  );
};

export const TerminalTableText = ({
  children,
  className,
  code = false,
}: {
  children: ReactNode;
  className?: string;
  code?: boolean;
}) => {
  const content = typeof children === 'string' || typeof children === 'number' ? String(children) : undefined;

  const text = (
    <span className={`terminal-table-text ${code ? 'terminal-table-text-code' : ''} ${className ?? ''}`}>
      {children}
    </span>
  );

  return content ? <Tooltip title={content}>{text}</Tooltip> : text;
};

export const Panel = ({
  title,
  icon,
  extra,
  children,
  className,
}: {
  title: string;
  icon?: ReactNode;
  extra?: ReactNode;
  children: ReactNode;
  className?: string;
}) => (
  <section className={`terminal-panel ${className ?? ''}`}>
    <div className="terminal-panel-header">
      <h2>
        {icon}
        <TerminalTableText>{title}</TerminalTableText>
      </h2>
      {extra}
    </div>
    {children}
  </section>
);

export const MockChart = () => {
  const intl = useIntl();
  const bars = [38, 44, 41, 52, 49, 57, 61, 55, 64, 69, 66, 74, 71, 79, 84, 80, 88, 92];

  return (
    <div className="terminal-chart" role="img" aria-label={intl.formatMessage({ id: 'terminal.chart.aria' })}>
      <div className="terminal-chart-grid" />
      <svg viewBox="0 0 720 260" role="img">
        <title>{intl.formatMessage({ id: 'terminal.chart.title' })}</title>
        <polyline
          points="0,184 42,172 84,178 126,151 168,159 210,133 252,121 294,138 336,106 378,94 420,103 462,78 504,86 546,62 588,44 630,56 672,31 720,24"
          fill="none"
          stroke={terminalTheme.positiveColor}
          strokeWidth="2"
        />
        {bars.map((height, index) => {
          const x = 14 + index * 39;
          const positive = index % 4 !== 2;
          const color = positive ? terminalTheme.positiveColor : terminalTheme.negativeColor;
          return (
            <g key={`${height}-${x}`}>
              <line x1={x + 6} x2={x + 6} y1={210 - height} y2={216} stroke={color} />
              <rect x={x} y={210 - height / 1.2} width="12" height={Math.max(18, height / 1.9)} fill={color} opacity="0.86" />
            </g>
          );
        })}
      </svg>
      <div className="terminal-chart-footer">
        <TerminalTableText>{intl.formatMessage({ id: 'terminal.chart.klineContainer' })}</TerminalTableText>
        <span>
          <GlossaryTerm term="RSI" /> / <GlossaryTerm term="MACD" />
        </span>
      </div>
    </div>
  );
};

export const SectorTape = ({ sectors, market }: { sectors: Metric[]; market?: ReturnType<typeof useMarket>['market'] }) => {
  const intl = useIntl();
  const locale = useLocaleCode();
  const marketState = useMarket();
  const currentMarket = market ?? marketState.market;

  return (
    <ul className="terminal-sector-tape">
      {sectors.map((sector) => {
        // 行业涨跌幅按数值正负着色，避免静态 tone 与实际数值不一致。
        const tone = sector.valueFormat === 'percent'
          ? sector.value > 0 ? 'positive' : sector.value < 0 ? 'negative' : 'neutral'
          : sector.tone;

        return (
          <li className="terminal-sector-item" key={sector.labelId}>
            <TerminalTableText className="terminal-sector-name">
              {intl.formatMessage({ id: sector.labelId })}
            </TerminalTableText>
            <TerminalTableText className={`terminal-sector-value ${getToneClass(tone)}`}>
              {formatMetricValue(sector, currentMarket, locale)}
            </TerminalTableText>
          </li>
        );
      })}
    </ul>
  );
};

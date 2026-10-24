import { useIntl } from '@umijs/max';
import type { ReactNode } from 'react';
import { formatCurrency, formatNumber, formatPercent } from './formatters';
import { GlossaryTerm, metricGlossaryMap } from './glossary';
import { getToneClass } from './mockData';
import type { MarketCode, Metric } from './types';

const useLocaleCode = () => {
  const intl = useIntl();
  return intl.locale?.startsWith('en') ? 'en-US' : 'zh-CN';
};

const shouldUseCompactMetricValue = (value: number) => Math.abs(value) >= 100_000;

const formatMetricValue = (metric: Metric, market: MarketCode, locale: string) => {
  const compactOptions = shouldUseCompactMetricValue(metric.value)
    ? { notation: 'compact' as const, maximumFractionDigits: 1 }
    : {};

  if (metric.valueFormat === 'currency') return formatCurrency(metric.value, market, compactOptions);
  if (metric.valueFormat === 'percent') return formatPercent(metric.value, {}, locale);
  return formatNumber(metric.value, compactOptions, locale);
};

const formatFullMetricValue = (metric: Metric, market: MarketCode, locale: string) => {
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

export const StockMetricStrip = ({ metrics, market, children }: { metrics: Metric[]; market: MarketCode; children?: ReactNode }) => {
  const intl = useIntl();
  const locale = useLocaleCode();

  return (
    <div className="terminal-metric-strip">
      {metrics.map((metric) => {
        const unavailable = metric.dataSource?.status === 'unavailable';
        const changeText = unavailable ? null : formatMetricChange(metric, locale);

        return (
          <div className="terminal-metric" key={metric.labelId}>
            <span>
              {intl.formatMessage({ id: metric.labelId })}
              {metricGlossaryMap[metric.labelId] ? <GlossaryTerm term={metricGlossaryMap[metric.labelId]} compact /> : null}
            </span>
            <strong title={unavailable ? intl.formatMessage({ id: 'terminal.dataStatus.unavailable' }) : formatFullMetricValue(metric, market, locale)}>
              {unavailable ? '--' : formatMetricValue(metric, market, locale)}
            </strong>
            {changeText ? <em className={getToneClass(metric.tone)}>{changeText}</em> : null}
          </div>
        );
      })}
      {children}
    </div>
  );
};

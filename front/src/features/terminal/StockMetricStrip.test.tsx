import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import enUS from '../../locales/en-US/terminal';
import zhCN from '../../locales/zh-CN/terminal';
import { StockMetricStrip } from './StockMetricStrip';
import type { Metric } from './types';

const localeState = vi.hoisted(() => ({ locale: 'zh-CN' }));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: localeState.locale,
    formatMessage: ({ id }: { id: string }) => {
      const dictionary = localeState.locale === 'en-US' ? enUS : zhCN;
      return dictionary[id as keyof typeof dictionary] ?? id;
    },
  }),
}));

beforeEach(() => {
  localeState.locale = 'zh-CN';
});

afterEach(cleanup);

describe('StockMetricStrip values', () => {
  it.each([
    ['US', '$1,234.56'],
    ['HK', '$1,234.56'],
    ['CN', '¥1,234.56'],
  ] as const)('formats currency using the %s market', (market, expected) => {
    render(
      <StockMetricStrip
        market={market}
        metrics={[
          {
            labelId: 'terminal.metric.turnover',
            value: 1234.56,
            valueFormat: 'currency',
          },
        ]}
      />,
    );

    expect(screen.getByText('成交额 Turnover')).toBeInTheDocument();
    expect(screen.getByText(expected)).toHaveAttribute('title', expected);
  });

  it.each([
    [99_999, '99,999', '99,999'],
    [100_000, '10万', '100,000'],
    [-123_456, '-12.3万', '-123,456'],
  ])('keeps the full value when displaying %s compactly', (value, text, title) => {
    render(
      <StockMetricStrip
        market="CN"
        metrics={[{ labelId: 'terminal.metric.turnover', value }]}
      />,
    );

    expect(screen.getByText(text)).toHaveAttribute('title', title);
  });

  it('compacts large currency values and preserves the precise amount on hover', () => {
    render(
      <StockMetricStrip
        market="US"
        metrics={[
          {
            labelId: 'terminal.metric.fcfTtm',
            value: 123_456.78,
            valueFormat: 'currency',
          },
        ]}
      />,
    );

    expect(screen.getByText('$123.5K')).toHaveAttribute('title', '$123,456.78');
  });

  it.each([
    [0.125, '+12.50%'],
    [-0.025, '-2.50%'],
    [0, '0.00%'],
  ])('formats percentage value %s without treating it as a whole percent', (value, expected) => {
    render(
      <StockMetricStrip
        market="CN"
        metrics={[
          { labelId: 'terminal.metric.roeTtm', value, valueFormat: 'percent' },
        ]}
      />,
    );

    expect(screen.getByText(expected)).toHaveAttribute('title', expected);
  });

  it.each([
    [0.0123, 'percent', 'positive', '+1.23%'],
    [-2.5, 'number', 'negative', '-2.5'],
    [0, 'number', 'neutral', '0'],
  ] as const)('shows change %s with its format and semantic color', (change, changeFormat, tone, expected) => {
    render(
      <StockMetricStrip
        market="US"
        metrics={[
          {
            labelId: 'terminal.metric.turnover',
            value: 100,
            change,
            changeFormat,
            tone,
          },
        ]}
      />,
    );

    expect(screen.getByText(expected)).toHaveClass(`terminal-tone-${tone}`);
  });

  it('omits the change row when no change is supplied', () => {
    const { container } = render(
      <StockMetricStrip
        market="US"
        metrics={[{ labelId: 'terminal.metric.pb', value: 2.5 }]}
      />,
    );

    expect(screen.getByText('2.5')).toBeInTheDocument();
    expect(container.querySelector('em')).not.toBeInTheDocument();
  });

  it.each([
    ['zh-CN', '数据不可用'],
    ['en-US', 'Unavailable'],
  ])('hides unavailable values and changes in %s', (locale, title) => {
    localeState.locale = locale;
    const metric: Metric = {
      labelId: 'terminal.metric.peTtm',
      value: 0,
      change: 0.1,
      changeFormat: 'percent',
      dataSource: { source: 'database', status: 'unavailable' },
    };
    const { container } = render(
      <StockMetricStrip market="US" metrics={[metric]} />,
    );

    expect(screen.getByText('--')).toHaveAttribute('title', title);
    expect(screen.queryByText('0')).not.toBeInTheDocument();
    expect(container.querySelector('em')).not.toBeInTheDocument();
  });

  it('uses the shared glossary explanation for a stock metric', async () => {
    const { container } = render(
      <StockMetricStrip
        market="US"
        metrics={[{ labelId: 'terminal.metric.peTtm', value: 24.5 }]}
      />,
    );
    const trigger = container.querySelector('.terminal-glossary-term');
    expect(trigger).toHaveClass('terminal-glossary-term-compact');
    fireEvent.mouseOver(trigger as HTMLElement);

    expect(await screen.findByRole('tooltip')).toHaveTextContent(
      zhCN['terminal.glossary.pe.description'],
    );
  });

  it('switches labels, compact units and glossary explanations to English', async () => {
    localeState.locale = 'en-US';
    const { container } = render(
      <StockMetricStrip
        market="US"
        metrics={[{ labelId: 'terminal.metric.peTtm', value: 123_456 }]}
      />,
    );

    expect(screen.getByText(enUS['terminal.metric.peTtm'])).toBeInTheDocument();
    expect(screen.getByText('123.5K')).toHaveAttribute('title', '123,456');
    fireEvent.mouseOver(
      container.querySelector('.terminal-glossary-term') as HTMLElement,
    );
    expect(await screen.findByRole('tooltip')).toHaveTextContent(
      enUS['terminal.glossary.pe.description'],
    );
  });

  it('renders an empty metric group without placeholder zero values', () => {
    const { container } = render(<StockMetricStrip market="US" metrics={[]} />);
    expect(container.querySelectorAll('.terminal-metric')).toHaveLength(0);
    expect(screen.queryByText('0')).not.toBeInTheDocument();
  });
});

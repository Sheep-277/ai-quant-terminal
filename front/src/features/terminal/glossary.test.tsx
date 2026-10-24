import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import enUS from '../../locales/en-US/terminal';
import zhCN from '../../locales/zh-CN/terminal';
import { GlossaryTerm, glossaryTerms, metricGlossaryMap } from './glossary';

const localeState = vi.hoisted(() => ({ locale: 'zh-CN' }));

vi.mock('@ant-design/icons', () => ({
  QuestionCircleOutlined: () => (
    <span role="img" aria-label="术语说明">
      ?
    </span>
  ),
}));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: localeState.locale,
    formatMessage: ({ id }: { id: string }) => {
      const dictionary = localeState.locale === 'en-US' ? enUS : zhCN;
      return dictionary[id as keyof typeof dictionary] ?? id;
    },
  }),
}));

const renderTerm = (term: keyof typeof glossaryTerms, compact = false) =>
  render(
    <App>
      <GlossaryTerm term={term} compact={compact} />
    </App>,
  );

beforeEach(() => {
  localeState.locale = 'zh-CN';
});

afterEach(cleanup);

describe('glossary data', () => {
  it('keeps all 24 terms and their locale identifiers unique', () => {
    const terms = Object.values(glossaryTerms);
    const localeIds = terms.flatMap(({ labelId, descriptionId }) => [
      labelId,
      descriptionId,
    ]);

    expect(terms).toHaveLength(24);
    expect(new Set(localeIds).size).toBe(48);
  });

  it.each([
    ['zh-CN', zhCN],
    ['en-US', enUS],
  ] as const)('has a label and description for every term in %s', (_locale, dictionary) => {
    Object.values(glossaryTerms).forEach(({ labelId, descriptionId }) => {
      expect(dictionary[labelId as keyof typeof dictionary]).toBeTruthy();
      expect(dictionary[descriptionId as keyof typeof dictionary]).toBeTruthy();
    });
  });

  it('only maps metric labels to registered glossary terms', () => {
    Object.values(metricGlossaryMap).forEach((term) => {
      expect(glossaryTerms).toHaveProperty(term);
    });
  });

  it('shares one explanation across related metric variants', () => {
    expect(metricGlossaryMap['terminal.metric.macd']).toBe('MACD');
    expect(metricGlossaryMap['terminal.metric.macdSignal']).toBe('MACD');
    expect(metricGlossaryMap['terminal.metric.macdHistogram']).toBe('MACD');
    expect(metricGlossaryMap['terminal.metric.pfcfTtm']).toBe('FCF');
    expect(metricGlossaryMap['terminal.metric.fcfTtm']).toBe('FCF');
  });
});

describe('GlossaryTerm', () => {
  it('shows the Chinese professional label and explanation', async () => {
    renderTerm('PE');

    const trigger = screen.getByText('PE 市盈率');
    fireEvent.mouseOver(trigger);

    expect(await screen.findByRole('tooltip')).toHaveTextContent(
      'PE 市盈率 = 股价 / 每股收益，用于衡量市场愿意为公司盈利支付的倍数。',
    );
  });

  it('switches both the label and explanation to English', async () => {
    localeState.locale = 'en-US';
    renderTerm('RSI');

    const trigger = screen.getByText('RSI Relative Strength Index');
    fireEvent.mouseOver(trigger);

    expect(await screen.findByRole('tooltip')).toHaveTextContent(
      'RSI measures relative upside and downside momentum over a selected lookback window.',
    );
    expect(screen.queryByText('RSI 相对强弱指标')).not.toBeInTheDocument();
  });

  it('keeps compact terms icon-only while preserving the explanation tooltip', async () => {
    const { container } = renderTerm('SHARPE', true);
    const trigger = container.querySelector('.terminal-glossary-term');

    expect(trigger).toHaveClass('terminal-glossary-term-compact');
    expect(screen.queryByText('Sharpe Ratio 夏普比率')).not.toBeInTheDocument();
    expect(screen.getByLabelText('术语说明')).toBeInTheDocument();

    fireEvent.mouseOver(trigger as HTMLElement);
    expect(await screen.findByRole('tooltip')).toHaveTextContent(
      'Sharpe Ratio 夏普比率衡量策略每承担一单位波动风险，换来的超额收益水平。',
    );
  });
});

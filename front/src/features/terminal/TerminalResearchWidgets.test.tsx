import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, describe, expect, it, vi } from 'vitest';
import enUS from '../../locales/en-US/terminal';
import zhCN from '../../locales/zh-CN/terminal';
import { ScoreStack } from './TerminalResearchWidgets';

const localeState = vi.hoisted(() => ({ locale: 'zh-CN' }));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: localeState.locale,
    formatMessage: ({ id }: { id: string }, values: Record<string, string | number> = {}) => {
      const dictionary = localeState.locale === 'en-US' ? enUS : zhCN;
      return Object.entries(values).reduce(
        (text, [key, value]) => text.replaceAll(`{${key}}`, String(value)),
        dictionary[id as keyof typeof dictionary] ?? id,
      );
    },
  }),
}));

afterEach(() => {
  cleanup();
  localeState.locale = 'zh-CN';
});

describe('quant score provenance', () => {
  it('marks the fixed scores as Mock samples with a localized explanation', async () => {
    render(<App><ScoreStack /></App>);

    const badge = screen.getByText('Mock Provider');
    fireEvent.mouseOver(badge);

    const tooltip = await screen.findByRole('tooltip');
    expect(tooltip).toHaveTextContent(zhCN['terminal.dashboard.source.quantScores']);
  });

  it('uses the English explanation when the locale changes', async () => {
    localeState.locale = 'en-US';
    render(<App><ScoreStack /></App>);

    fireEvent.mouseOver(screen.getByText('Mock Provider'));
    expect(await screen.findByRole('tooltip')).toHaveTextContent(
      enUS['terminal.dashboard.source.quantScores'],
    );
  });
});

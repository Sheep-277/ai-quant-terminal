import { describe, expect, it } from 'vitest';
import {
  formatCurrency,
  formatDateTime,
  formatNumber,
  formatPercent,
} from './formatters';

describe('terminal number formatters', () => {
  it.each([
    ['US', 'USD'],
    ['HK', 'HKD'],
    ['CN', 'CNY'],
  ] as const)('uses the configured currency for the %s market', (market, currency) => {
    const value = formatCurrency(1234.5, market, { currencyDisplay: 'code' });

    expect(value).toMatch(new RegExp(`${currency}\\s+1,234\\.50`));
  });

  it('formats numbers with defaults while allowing precision overrides', () => {
    expect(formatNumber(1234.567)).toBe('1,234.57');
    expect(formatNumber(1234.567, { maximumFractionDigits: 0 })).toBe('1,235');
  });

  it('formats positive, negative and zero percentages with financial signs', () => {
    expect(formatPercent(0.1234)).toBe('+12.34%');
    expect(formatPercent(-0.1234)).toBe('-12.34%');
    expect(formatPercent(0)).toBe('0.00%');
  });

  it('honors a caller-provided maximum percentage precision', () => {
    expect(formatPercent(0.856, {
      signDisplay: 'never',
      maximumFractionDigits: 0,
    })).toBe('86%');
  });
});

describe('terminal date-time formatter', () => {
  const timestamp = '2026-10-15T00:00:00Z';

  it('converts the same timestamp using the selected market timezone', () => {
    expect(formatDateTime(timestamp, {
      timezone: 'America/New_York',
      locale: 'zh-CN',
    })).toBe('2026/10/14 20:00:00');
    expect(formatDateTime(timestamp, {
      timezone: 'Asia/Shanghai',
      locale: 'zh-CN',
    })).toBe('2026/10/15 08:00:00');
  });

  it('honors the time-only pattern used by the live event stream', () => {
    expect(formatDateTime(timestamp, {
      timezone: 'Asia/Hong_Kong',
      locale: 'zh-CN',
      pattern: 'HH:mm:ss',
    })).toBe('08:00:00');
  });

  it.each([
    ['America/New_York', '10/14'],
    ['Asia/Hong_Kong', '10/15'],
    ['Asia/Shanghai', '10/15'],
  ])('formats compact chart dates in %s', (timezone, expected) => {
    expect(formatDateTime(timestamp, { timezone, locale: 'zh-CN', pattern: 'MM/dd' })).toBe(expected);
  });

  it('keeps invalid timestamps visible without fabricating a date or throwing', () => {
    expect(formatDateTime('invalid-date', { timezone: 'America/New_York' })).toBe('invalid-date');
  });

  it('falls back to ISO time when the timezone is invalid', () => {
    expect(formatDateTime(timestamp, {
      timezone: 'Invalid/Timezone',
      locale: 'zh-CN',
    })).toBe('2026-10-15T00:00:00.000Z');
  });
});

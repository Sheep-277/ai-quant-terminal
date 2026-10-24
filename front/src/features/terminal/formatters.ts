import type { MarketCode } from './types';

const marketCurrency: Record<MarketCode, 'USD' | 'HKD' | 'CNY'> = {
  US: 'USD',
  HK: 'HKD',
  CN: 'CNY',
};

const marketLocale: Record<MarketCode, string> = {
  US: 'en-US',
  HK: 'zh-HK',
  CN: 'zh-CN',
};

export const formatNumber = (
  value: number,
  options: Intl.NumberFormatOptions = {},
  locale = 'zh-CN',
) => {
  try {
    return new Intl.NumberFormat(locale, {
      maximumFractionDigits: 2,
      ...options,
    }).format(value);
  } catch {
    return String(value);
  }
};

export const formatCurrency = (
  value: number,
  market: MarketCode,
  options: Intl.NumberFormatOptions = {},
) => {
  try {
    return new Intl.NumberFormat(marketLocale[market], {
      style: 'currency',
      currency: marketCurrency[market],
      currencyDisplay: 'narrowSymbol',
      maximumFractionDigits: 2,
      ...options,
    }).format(value);
  } catch {
    return `${marketCurrency[market]} ${value}`;
  }
};

export const formatPercent = (
  value: number,
  options: Intl.NumberFormatOptions = {},
  locale = 'zh-CN',
) => {
  // 调用方只覆盖最大精度时，最小精度必须同步收窄，否则 Intl 会保留默认两位小数。
  const minimumFractionDigits = options.minimumFractionDigits
    ?? Math.min(2, options.maximumFractionDigits ?? 2);
  const maximumFractionDigits = options.maximumFractionDigits
    ?? Math.max(2, minimumFractionDigits);
  try {
    return new Intl.NumberFormat(locale, {
      style: 'percent',
      signDisplay: 'exceptZero',
      minimumFractionDigits,
      maximumFractionDigits,
      ...options,
    }).format(value);
  } catch {
    return `${(value * 100).toFixed(2)}%`;
  }
};

export const formatDateTime = (
  value: string | number | Date,
  options: { timezone?: string; locale?: string; pattern?: string } = {},
) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const locale = options.locale ?? 'zh-CN';
  // 坐标轴保留短日期，悬浮详情与其他场景显示完整日期时间。
  const dateTimeOptions: Intl.DateTimeFormatOptions = options.pattern === 'MM/dd'
    ? {
        month: '2-digit',
        day: '2-digit',
        timeZone: options.timezone,
      }
    : options.pattern === 'HH:mm:ss'
    ? {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
        timeZone: options.timezone,
      }
    : {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
        timeZone: options.timezone,
      };
  try {
    return new Intl.DateTimeFormat(locale, dateTimeOptions).format(date);
  } catch {
    return date.toISOString();
  }
};

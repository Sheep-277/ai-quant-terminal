import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import enUS from '../../locales/en-US/terminal';
import zhCN from '../../locales/zh-CN/terminal';
import {
  CompactDataSourceBadge,
  DataSourceBadge,
  getDataSourceColor,
  getProviderBadgeColor,
} from './DataSourceBadge';

const localeState = vi.hoisted(() => ({ locale: 'zh-CN' }));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: localeState.locale,
    formatMessage: (
      { id }: { id: string },
      values: Record<string, string | number> = {},
    ) => {
      const dictionary = localeState.locale === 'en-US' ? enUS : zhCN;
      return Object.entries(values).reduce(
        (text, [key, value]) => text.replaceAll(`{${key}}`, String(value)),
        dictionary[id as keyof typeof dictionary] ?? id,
      );
    },
  }),
}));

beforeEach(() => {
  localeState.locale = 'zh-CN';
});

afterEach(cleanup);

describe('data source color semantics', () => {
  it('keeps real, computed, fallback and unknown sources visually distinct', () => {
    expect(getDataSourceColor('yahoo_finance')).toBe('cyan');
    expect(getDataSourceColor('quant_pipeline')).toBe('purple');
    expect(getDataSourceColor('yahoo_finance', true)).toBe('gold');
    expect(getDataSourceColor('custom_source')).toBe('default');
  });

  it('distinguishes ready real providers from mock and fallback providers', () => {
    expect(getProviderBadgeColor({
      provider_name: 'YahooFinance',
      mode: 'real',
      ready: true,
      data_status: 'delayed',
      fallback_active: false,
      fallback_reason: null,
    })).toBe('green');
    expect(getProviderBadgeColor({
      provider_name: 'MockProvider',
      mode: 'mock',
      ready: true,
      data_status: 'realtime',
      fallback_active: false,
      fallback_reason: null,
    })).toBe('blue');
    expect(getProviderBadgeColor({
      provider_name: 'YahooFinance',
      mode: 'real',
      ready: false,
      data_status: 'unavailable',
      fallback_active: true,
      fallback_reason: '公开行情请求失败',
    })).toBe('gold');
  });
});

describe('data source badge content', () => {
  it.each(['zh-CN', 'en-US'])('exposes database unavailability and its reason on keyboard focus in %s', async locale => {
    localeState.locale = locale;
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    const detail = 'Database K-line validation failed; no sample replacement';
    render(<App><DataSourceBadge labelId="terminal.dataSource.kline" source={{
      source: 'database', detail, fallbackActive: false, dataStatus: 'unavailable',
    }} /></App>);
    const badge = screen.getByText(`${dictionary['terminal.dataSource.kline']}: ${dictionary['terminal.dataSource.database']} · ${dictionary['terminal.dataStatus.unavailable']}`);
    expect(badge).toHaveClass('ant-tag-gold');
    expect(badge).toHaveAttribute('tabindex', '0');
    expect(badge.getAttribute('aria-label')).toContain(detail);
    fireEvent.focus(badge);
    const tooltip = await screen.findByRole('tooltip');
    expect(tooltip).toHaveTextContent(detail);
    expect(tooltip).toHaveTextContent(dictionary['terminal.dataSource.tooltip.fallbackInactive']);
    expect(badge).not.toHaveTextContent(dictionary['terminal.dataSource.mockFallback']);
  });

  it('shows the unavailable state for derived results and restores the normal badge on refresh', async () => {
    const source = { source: 'quant_pipeline', detail: 'K-line data unavailable', fallbackActive: false, dataStatus: 'unavailable' as const };
    const view = render(<App><CompactDataSourceBadge source={source} /></App>);
    const badge = screen.getByText('即时 Quant Pipeline · 数据不可用');
    expect(badge).toHaveClass('ant-tag-gold');
    expect(badge).toHaveAttribute('tabindex', '0');
    fireEvent.focus(badge);
    expect(await screen.findByRole('tooltip')).toHaveTextContent(source.detail);
    fireEvent.blur(badge);
    view.rerender(<App><CompactDataSourceBadge source={{ ...source, detail: 'Computed from valid bars', dataStatus: 'delayed' }} /></App>);
    expect(screen.getByText('即时 Quant Pipeline')).toHaveClass('ant-tag-purple');
    expect(screen.queryByText('即时 Quant Pipeline · 数据不可用')).not.toBeInTheDocument();
    expect(screen.getByText('即时 Quant Pipeline').getAttribute('aria-label')).toContain('Computed from valid bars');
  });

  it('shows YahooFinance provenance and delayed status in Chinese', async () => {
    render(
      <App>
        <DataSourceBadge
          labelId="terminal.dataSource.marketData"
          source={{
            source: 'yahoo_finance',
            detail: '公开日线行情',
            fallbackActive: false,
            dataStatus: 'delayed',
          }}
        />
      </App>,
    );

    const badge = screen.getByText('行情: YahooFinance 公开行情');
    expect(badge).toBeInTheDocument();

    fireEvent.mouseOver(badge);
    expect(await screen.findByText(/来源：YahooFinance 公开行情/)).toBeInTheDocument();
    expect(await screen.findByText(/状态：延迟数据/)).toBeInTheDocument();
    expect(await screen.findByText(/说明：公开日线行情/)).toBeInTheDocument();
  });

  it('labels an active fallback without hiding its original source', async () => {
    render(
      <App>
        <CompactDataSourceBadge
          source={{
            source: 'yahoo_finance',
            detail: '请求超时后使用本地数据',
            fallbackActive: true,
            dataStatus: 'unavailable',
          }}
        />
      </App>,
    );

    const badge = screen.getByText('Mock 回退');
    fireEvent.mouseOver(badge);

    expect(await screen.findByText(/来源：YahooFinance 公开行情/)).toBeInTheDocument();
    expect(await screen.findByText(/回退：已启用 Mock 回退/)).toBeInTheDocument();
    expect(await screen.findByText(/状态：数据不可用/)).toBeInTheDocument();
  });

  it('uses the English locale instead of hard-coded Chinese labels', () => {
    localeState.locale = 'en-US';

    render(
      <App>
        <CompactDataSourceBadge
          source={{
            source: 'quant_pipeline',
            detail: 'Computed from market bars',
            fallbackActive: false,
            dataStatus: 'delayed',
          }}
        />
      </App>,
    );

    expect(screen.getByText('Computed Quant Pipeline')).toBeInTheDocument();
    expect(screen.queryByText('即时 Quant Pipeline')).not.toBeInTheDocument();
  });
});

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import enUS from '../../locales/en-US/terminal';
import zhCN from '../../locales/zh-CN/terminal';
import type { ProviderStatusResponse } from './apiTypes';
import { marketSnapshots, pageDefinitions } from './mockData';
import { TerminalPageHeader } from './TerminalPageHeader';
import type { TerminalPageKey } from './types';

const localeState = vi.hoisted(() => ({ locale: 'zh-CN' }));

vi.mock('@ant-design/icons', () => ({
  HistoryOutlined: () => null,
  InfoCircleOutlined: () => null,
  PlayCircleOutlined: () => null,
}));

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

// Header 只需要日志查询的静态状态；日志弹窗本身不属于本组状态标签测试。
vi.mock('./useProviderStatus', () => ({
  useProviderStatusLogs: () => ({
    data: undefined,
    isFetching: false,
  }),
}));

const apiStatusMap: Record<
  TerminalPageKey,
  { isError: boolean; isFetching: boolean }
> = {
  dashboard: { isError: false, isFetching: false },
  'stock-research': { isError: false, isFetching: false },
  'ai-research': { isError: false, isFetching: false },
  'strategy-lab': { isError: false, isFetching: false },
  backtest: { isError: false, isFetching: false },
  portfolio: { isError: false, isFetching: false },
  monitor: { isError: false, isFetching: false },
};

const realProviderStatus: ProviderStatusResponse = {
  provider_name: 'YahooFinance',
  mode: 'real',
  ready: true,
  data_status: 'delayed',
  fallback_active: false,
  fallback_reason: null,
  source_type: 'provider',
  active_source: 'yahoo_finance',
  missing_configuration: [],
  next_action: null,
  last_logged_at: '2026-10-15T01:00:00Z',
  recent_log_count: 3,
};

type QueryStatus = { isError: boolean; isFetching: boolean };

const headerFor = (
  providerStatus: ProviderStatusResponse,
  status: QueryStatus = { isError: false, isFetching: false },
  pageKey: TerminalPageKey = 'dashboard',
) => (
  <App>
    <TerminalPageHeader
      pageKey={pageKey}
      page={pageDefinitions[pageKey]}
      snapshot={marketSnapshots.US}
      providerStatus={providerStatus}
      providerStatusLoading={false}
      providerStatusError={false}
      apiStatusMap={{ ...apiStatusMap, [pageKey]: status }}
      primaryActionLoading={false}
      onMockDataClick={vi.fn()}
      onPrimaryActionClick={vi.fn()}
    />
  </App>
);

const renderHeader = (
  providerStatus: ProviderStatusResponse,
  status?: QueryStatus,
  pageKey?: TerminalPageKey,
) => render(headerFor(providerStatus, status, pageKey));

beforeEach(() => {
  localeState.locale = 'zh-CN';
});

afterEach(cleanup);

describe('terminal page header provider status', () => {
  it('shows a real provider and exposes delayed public quote details', async () => {
    renderHeader(realProviderStatus);

    const providerTag = screen.getByText('真实数据源');
    expect(providerTag).toBeInTheDocument();
    expect(screen.getByText('后端已同步')).toBeInTheDocument();
    expect(screen.getByText('S&P 500')).toBeInTheDocument();

    fireEvent.mouseOver(providerTag);
    expect(
      await screen.findByText(/当前实际来源：YahooFinance 公开行情/),
    ).toBeInTheDocument();
    expect(await screen.findByText(/数据状态：延迟数据/)).toBeInTheDocument();
  });

  it('shows fallback before real mode and exposes the fallback reason', async () => {
    renderHeader({
      ...realProviderStatus,
      ready: false,
      fallback_active: true,
      fallback_reason: '公开行情请求超时',
      active_source: 'mock_fallback',
      data_status: 'unavailable',
    });

    const providerTag = screen.getByText('数据源回退中');
    expect(providerTag).toBeInTheDocument();
    expect(screen.queryByText('真实数据源')).not.toBeInTheDocument();

    fireEvent.mouseOver(providerTag);
    expect(
      await screen.findByText(/回退原因：公开行情请求超时/),
    ).toBeInTheDocument();
    expect(await screen.findByText(/数据状态：数据不可用/)).toBeInTheDocument();
  });

  it('labels a normal mock provider without presenting it as real data', () => {
    renderHeader({
      ...realProviderStatus,
      provider_name: 'MockProvider',
      mode: 'mock',
      data_status: 'realtime',
      source_type: 'mock_provider',
      active_source: 'mock_provider',
      last_logged_at: null,
      recent_log_count: 0,
    });

    expect(screen.getByText('Mock 数据源')).toBeInTheDocument();
    expect(screen.queryByText('真实数据源')).not.toBeInTheDocument();
    expect(screen.queryByText('数据源回退中')).not.toBeInTheDocument();
  });
});

describe('terminal page header query status', () => {
  it.each([
    ['zh-CN', '数据读取失败', '真实数据源'],
    ['en-US', 'Data request failed', 'Real provider'],
  ])('在 %s 中将查询失败与真实数据源状态分别显示', (locale, failureLabel, providerLabel) => {
    localeState.locale = locale;
    renderHeader(
      realProviderStatus,
      { isError: true, isFetching: false },
      'stock-research',
    );

    const status = screen.getByText(failureLabel);
    expect(status.closest('.ant-tag')).toHaveAttribute('title', failureLabel);
    expect(status.closest('.ant-tag')).toHaveClass('ant-tag-gold');
    expect(screen.getByText(providerLabel)).toBeInTheDocument();
    expect(
      screen.queryByText(/使用本地 Mock|using local mock/),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(zhCN['terminal.providerStatus.fallback']),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(enUS['terminal.providerStatus.fallback']),
    ).not.toBeInTheDocument();
  });

  it('重试期间优先显示同步中，不保留上一次读取失败标签', () => {
    renderHeader(
      realProviderStatus,
      { isError: true, isFetching: true },
      'stock-research',
    );

    const status = screen.getByText('同步中');
    expect(status.closest('.ant-tag')).toHaveAttribute('title', '同步中');
    expect(status.closest('.ant-tag')).toHaveClass('ant-tag-blue');
    expect(screen.queryByText('数据读取失败')).not.toBeInTheDocument();
    expect(screen.getByText('真实数据源')).toBeInTheDocument();
  });

  it('重新读取成功后恢复同步成功标签', () => {
    const view = renderHeader(
      realProviderStatus,
      { isError: true, isFetching: false },
      'stock-research',
    );
    expect(screen.getByText('数据读取失败')).toBeInTheDocument();

    view.rerender(
      headerFor(
        realProviderStatus,
        { isError: false, isFetching: true },
        'stock-research',
      ),
    );
    expect(screen.getByText('同步中')).toBeInTheDocument();
    expect(screen.queryByText('后端已同步')).not.toBeInTheDocument();

    view.rerender(
      headerFor(
        realProviderStatus,
        { isError: false, isFetching: false },
        'stock-research',
      ),
    );
    expect(screen.getByText('后端已同步')).toBeInTheDocument();
    expect(screen.queryByText('数据读取失败')).not.toBeInTheDocument();
    expect(screen.queryByText('同步中')).not.toBeInTheDocument();
  });

  it('只有 Provider 明确启用回退时显示数据源回退标签', () => {
    renderHeader(
      {
        ...realProviderStatus,
        ready: false,
        fallback_active: true,
        active_source: 'mock_fallback',
        data_status: 'unavailable',
        fallback_reason: '公开行情请求超时',
      },
      { isError: true, isFetching: false },
    );

    expect(screen.getByText('数据读取失败')).toBeInTheDocument();
    expect(screen.getByText('数据源回退中')).toBeInTheDocument();
    expect(screen.queryByText('真实数据源')).not.toBeInTheDocument();
  });
});

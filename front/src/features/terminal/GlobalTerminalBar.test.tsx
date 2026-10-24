import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { App, ConfigProvider, theme } from 'antd';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import enUS from '../../locales/en-US/terminal';
import zhCN from '../../locales/zh-CN/terminal';
import { formatDateTime } from './formatters';
import { GlobalTerminalBar } from './GlobalTerminalBar';
import { MarketProvider } from './MarketContext';
import { marketSnapshots } from './mockData';

const localeState = vi.hoisted(() => ({ locale: 'zh-CN' }));

vi.mock('@ant-design/icons', () => ({
  RobotOutlined: () => (
    <span role="img" aria-label="AI助手图标">
      AI
    </span>
  ),
  StarOutlined: () => (
    <span role="img" aria-label="自选列表图标">
      *
    </span>
  ),
}));

vi.mock('@umijs/max', () => ({
  getLocale: () => localeState.locale,
  getIntl: () => ({
    locale: localeState.locale,
    formatMessage: ({ id }: { id: string }) => {
      const dictionary = localeState.locale === 'en-US' ? enUS : zhCN;
      return dictionary[id as keyof typeof dictionary] ?? id;
    },
  }),
}));

const renderBar = () =>
  render(
    <App>
      <MarketProvider>
        <GlobalTerminalBar />
      </MarketProvider>
    </App>,
  );

const expectedTime = (
  market: keyof typeof marketSnapshots,
  locale = 'zh-CN',
) => {
  const snapshot = marketSnapshots[market];
  return formatDateTime(snapshot.updatedAt, {
    timezone: snapshot.timezone,
    locale,
  });
};

beforeEach(() => {
  localeState.locale = 'zh-CN';
  window.localStorage.clear();
  vi.mocked(window.localStorage.setItem).mockClear();
});

afterEach(cleanup);

describe('GlobalTerminalBar market switching', () => {
  it('marks the default market status as a sample and hides the stale timestamp', () => {
    renderBar();

    expect(screen.getByText('美股').closest('.ant-segmented-item')).toHaveClass(
      'ant-segmented-item-selected',
    );
    expect(screen.getByText('港股')).toBeInTheDocument();
    expect(screen.getByText('A股')).toBeInTheDocument();
    expect(screen.getByText('Mock 样例 · 开盘')).toBeInTheDocument();
    expect(screen.queryByText(expectedTime('US'))).not.toBeInTheDocument();
  });

  it.each([
    ['港股', 'HK', '休市'],
    ['A股', 'CN', '休市'],
  ] as const)('switches to %s and updates its visible market state', (label, market, status) => {
    renderBar();

    fireEvent.click(screen.getByText(label));

    expect(screen.getByText(label).closest('.ant-segmented-item')).toHaveClass(
      'ant-segmented-item-selected',
    );
    expect(screen.getByText(`Mock 样例 · ${status}`)).toBeInTheDocument();
    expect(screen.queryByText(expectedTime(market))).not.toBeInTheDocument();
    expect(window.localStorage.setItem).toHaveBeenCalledWith(
      'ai-quant-terminal-market',
      market,
    );
  });

  it('restores a previously selected market into the segmented control', () => {
    window.localStorage.setItem('ai-quant-terminal-market', 'CN');
    renderBar();

    expect(screen.getByText('A股').closest('.ant-segmented-item')).toHaveClass(
      'ant-segmented-item-selected',
    );
    expect(screen.getByText('Mock 样例 · 休市')).toBeInTheDocument();
    expect(screen.queryByText(expectedTime('CN'))).not.toBeInTheDocument();
  });

  it('uses the English locale for labels, status and date-time', () => {
    localeState.locale = 'en-US';
    renderBar();

    expect(screen.getByText('US')).toBeInTheDocument();
    expect(screen.getByText('HK')).toBeInTheDocument();
    expect(screen.getByText('CN')).toBeInTheDocument();
    expect(screen.getByText('Mock sample · Open')).toBeInTheDocument();
    expect(screen.queryByText(expectedTime('US', 'en-US'))).not.toBeInTheDocument();
    expect(screen.queryByText('美股')).not.toBeInTheDocument();
  });
});

describe('GlobalTerminalBar sample provenance', () => {
  it.each(['zh-CN', 'en-US'])('explains the sample timestamp in %s', async (locale) => {
    localeState.locale = locale;
    renderBar();
    const label = locale === 'en-US' ? 'Mock sample · Open' : 'Mock 样例 · 开盘';

    if (locale === 'en-US') {
      fireEvent.focus(screen.getByText(label));
    } else {
      fireEvent.mouseOver(screen.getByText(label));
    }

    const tooltip = await screen.findByRole('tooltip');
    expect(tooltip).toHaveTextContent(expectedTime('US', locale));
    expect(tooltip).toHaveTextContent(marketSnapshots.US.timezone);
    expect(tooltip).toHaveTextContent(
      locale === 'en-US' ? 'not the current trading session' : '不代表当前开闭市状态',
    );
  });
});

describe('GlobalTerminalBar theme switching', () => {
  it.each(['zh-CN', 'en-US'])('preserves market selection and interactions across themes in %s', async (locale) => {
    localeState.locale = locale;
    // 只切换主题，不重建市场上下文，以验证真实使用中的状态保留。
    const themedBar = (mode: 'light' | 'dark') => (
      <MarketProvider>
        <ConfigProvider theme={{ algorithm: mode === 'dark' ? theme.darkAlgorithm : theme.defaultAlgorithm }}>
          <App>
            <GlobalTerminalBar />
          </App>
        </ConfigProvider>
      </MarketProvider>
    );
    const labels = locale === 'en-US'
      ? { hk: 'HK', cn: 'CN', status: 'Mock sample · Closed' }
      : { hk: '港股', cn: 'A股', status: 'Mock 样例 · 休市' };
    const view = render(themedBar('light'));
    fireEvent.click(screen.getByRole('radio', { name: labels.hk }));
    expect(window.localStorage.setItem).toHaveBeenCalledWith('ai-quant-terminal-market', 'HK');
    vi.mocked(window.localStorage.setItem).mockClear();

    view.rerender(themedBar('dark'));
    expect(screen.getByRole('radio', { name: labels.hk })).toBeChecked();
    expect(screen.getByText(labels.status)).toBeInTheDocument();
    expect(window.localStorage.setItem).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('radio', { name: labels.cn }));
    expect(screen.getByRole('radio', { name: labels.cn })).toBeChecked();
    expect(window.localStorage.setItem).toHaveBeenCalledWith('ai-quant-terminal-market', 'CN');
    vi.mocked(window.localStorage.setItem).mockClear();

    view.rerender(themedBar('light'));
    expect(screen.getByRole('radio', { name: labels.cn })).toBeChecked();
    expect(window.localStorage.setItem).not.toHaveBeenCalled();
    fireEvent.focus(screen.getByText(labels.status));
    const tooltip = await screen.findByRole('tooltip');
    expect(tooltip).toHaveTextContent(expectedTime('CN', locale));
    expect(tooltip).toHaveTextContent(marketSnapshots.CN.timezone);
    expect(tooltip).toHaveTextContent(
      locale === 'en-US' ? 'not the current trading session' : '不代表当前开闭市状态',
    );
  });
});

describe('GlobalTerminalBar prototype actions', () => {
  it('names both icon buttons and explains the watchlist entry on hover', async () => {
    renderBar();

    const watchlistButton = screen.getByRole('button', {
      name: '自选列表图标',
    });
    expect(
      screen.getByRole('button', { name: 'AI助手图标' }),
    ).toBeInTheDocument();

    fireEvent.mouseOver(watchlistButton);
    expect(await screen.findByRole('tooltip')).toHaveTextContent(
      '自选列表 Watchlist',
    );
  });

  it('shows the prototype boundary message instead of changing data', async () => {
    renderBar();

    fireEvent.click(screen.getByRole('button', { name: 'AI助手图标' }));

    expect(
      await screen.findByText(
        '当前为原型说明入口：页面会标注 Mock、数据库、回退和模拟交易边界；点击不会切换或重新生成数据。',
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('美股').closest('.ant-segmented-item')).toHaveClass(
      'ant-segmented-item-selected',
    );
  });
});

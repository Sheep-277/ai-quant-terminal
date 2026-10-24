import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, describe, expect, it, vi } from 'vitest';
import enUS from '../../locales/en-US/terminal';
import zhCN from '../../locales/zh-CN/terminal';
import { StockKLineMockChart } from './StockKLineMockChart';
import type { KLinePoint, StockMarketDataSourceStatus } from './types';

const localeState = vi.hoisted(() => ({ locale: 'zh-CN' }));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: localeState.locale,
    formatMessage: (
      { id }: { id: string },
      values: Record<string, string | number> = {},
    ) => Object.entries(values).reduce(
      (text, [key, value]) => text.replaceAll(`{${key}}`, String(value)),
      (localeState.locale === 'en-US' ? enUS : zhCN)[id as keyof typeof zhCN] ?? id,
    ),
  }),
}));

const bars: KLinePoint[] = Array.from({ length: 48 }, (_, index) => {
  const open = 100 + index;
  return {
    timestamp: new Date(Date.UTC(2026, 8, index + 1, 16)).toISOString(),
    open,
    high: open + 2,
    low: open - 1,
    close: open + (index % 2 === 0 ? 1 : -0.5),
    volume: 1_000_000 + index * 10_000,
  };
});

const dataSource: StockMarketDataSourceStatus = {
  source: 'yahoo_finance',
  detail: 'YahooFinance 日线',
  fallbackActive: false,
  dataStatus: 'delayed',
};

const renderChart = () => render(
  <App>
    <StockKLineMockChart bars={bars} dataSource={dataSource} timezone="America/New_York" />
  </App>,
);

afterEach(() => {
  cleanup();
  localeState.locale = 'zh-CN';
});

describe('stock K-line chart', () => {
  it.each([
    { name: 'NaN price', patch: { open: Number.NaN } },
    { name: 'infinite price', patch: { high: Number.POSITIVE_INFINITY } },
    { name: 'zero price', patch: { low: 0 } },
    { name: 'negative price', patch: { low: -1 } },
    { name: 'low above open', patch: { low: 101 } },
    { name: 'high below close', patch: { high: 100 } },
    { name: 'negative volume', patch: { volume: -1 } },
    { name: 'NaN volume', patch: { volume: Number.NaN } },
    { name: 'infinite volume', patch: { volume: Number.POSITIVE_INFINITY } },
    { name: 'invalid timestamp', patch: { timestamp: 'invalid-date' } },
    { name: 'duplicate timestamp', patch: { timestamp: bars[1].timestamp } },
    { name: 'unordered timestamp', patch: { timestamp: bars[2].timestamp } },
  ])('pauses rendering for $name even outside the visible window', ({ patch }) => {
    const invalidBars = bars.map((bar, index) => index === 0 ? { ...bar, ...patch } : { ...bar });
    const { container } = render(<StockKLineMockChart bars={invalidBars} dataSource={dataSource} timezone="America/New_York" />);
    expect(screen.getByRole('status')).toHaveTextContent(zhCN['terminal.chart.invalidData']);
    expect(container.querySelector('.terminal-chart > svg')).toBeNull();
    expect(container.querySelector('.terminal-chart-tooltip')).toBeNull();
    for (const button of screen.getAllByRole('button')) expect(button).toBeDisabled();
    fireEvent.wheel(screen.getByRole('region', { name: '交互式 K 线图' }), { deltaY: -100 });
    expect(container.innerHTML).not.toMatch(/NaN|Infinity/);
  });

  it.each(['zh-CN', 'en-US'])('clears an invalidated chart and restores valid rendering in %s', locale => {
    localeState.locale = locale;
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    const { container, rerender } = render(<StockKLineMockChart bars={bars} dataSource={dataSource} timezone="America/New_York" />);
    const candle = container.querySelector('rect[fill="transparent"]')?.parentElement;
    fireEvent.mouseEnter(candle as unknown as SVGGElement);
    expect(container.querySelector('.terminal-chart-tooltip')).not.toBeNull();
    const invalidBars = [{ ...bars[0], volume: -1 }];
    rerender(<StockKLineMockChart bars={invalidBars} dataSource={dataSource} timezone="America/New_York" />);
    expect(screen.getByRole('status')).toHaveTextContent(dictionary['terminal.chart.invalidData']);
    expect(container.querySelector('.terminal-chart-tooltip')).toBeNull();
    expect(container.querySelector('.terminal-chart-crosshair')).toBeNull();
    expect(invalidBars[0].volume).toBe(-1);
    rerender(<StockKLineMockChart bars={bars} dataSource={dataSource} timezone="America/New_York" />);
    expect(screen.queryByText(dictionary['terminal.chart.invalidData'])).not.toBeInTheDocument();
    expect(container.querySelectorAll('rect[fill="transparent"]')).toHaveLength(36);
    expect(container.innerHTML).not.toMatch(/NaN|Infinity/);
  });

  it.each(['US:MSFT:1d', 'HK:AAPL:1d'])('resets zoom, pan and hover for a new chart identity %s', (nextKey) => {
    const { container, rerender } = render(<StockKLineMockChart key="US:AAPL:1d" bars={bars} dataSource={dataSource} timezone="America/New_York" />);
    fireEvent.click(screen.getByRole('button', { name: '放大 K 线' }));
    fireEvent.click(screen.getByRole('button', { name: '查看更早 K 线' }));
    expect(screen.getByText('显示 30 / 48 根 K 线，滚轮可缩放')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '查看更新 K 线' })).toBeEnabled();
    const candle = container.querySelector('rect[fill="transparent"]')?.parentElement;
    fireEvent.mouseEnter(candle as unknown as SVGGElement);
    expect(container.querySelector('.terminal-chart-tooltip')).not.toBeNull();

    rerender(<StockKLineMockChart key={nextKey} bars={bars} dataSource={dataSource} timezone="America/New_York" />);
    expect(screen.getByText('显示 36 / 48 根 K 线，滚轮可缩放')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '查看更新 K 线' })).toBeDisabled();
    expect(container.querySelector('.terminal-chart-tooltip')).toBeNull();
    expect(container.querySelector('.terminal-chart-crosshair')).toBeNull();
    const lastCandle = container.querySelectorAll('rect[fill="transparent"]')[35];
    fireEvent.mouseEnter(lastCandle.parentElement as unknown as SVGGElement);
    expect(screen.getByText('O 147')).toBeInTheDocument();
  });

  it('preserves zoom and pan when the same target receives new bar objects', () => {
    const { rerender } = render(<StockKLineMockChart key="US:AAPL:1d" bars={bars} dataSource={dataSource} timezone="America/New_York" />);
    fireEvent.click(screen.getByRole('button', { name: '放大 K 线' }));
    fireEvent.click(screen.getByRole('button', { name: '查看更早 K 线' }));
    rerender(<StockKLineMockChart key="US:AAPL:1d" bars={bars.map(bar => ({ ...bar, volume: bar.volume + 100 }))} dataSource={{ ...dataSource }} timezone="America/New_York" />);
    expect(screen.getByText('显示 30 / 48 根 K 线，滚轮可缩放')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '查看更新 K 线' })).toBeEnabled();
  });

  it('renders an empty state without axes and disables every chart control', () => {
    const { container } = render(<StockKLineMockChart bars={[]} dataSource={dataSource} timezone="America/New_York" />);

    expect(screen.getByText('暂无 K 线数据')).toBeInTheDocument();
    expect(container.querySelector('.terminal-chart > svg')).toBeNull();
    for (const button of screen.getAllByRole('button')) {
      expect(button).toBeDisabled();
    }
    fireEvent.wheel(screen.getByRole('region', { name: '交互式 K 线图' }), { deltaY: -100 });
    expect(container.innerHTML).not.toMatch(/NaN|Infinity/);
  });

  it.each(['zh-CN', 'en-US'])('distinguishes unavailable data from an empty history and recovers in %s', locale => {
    localeState.locale = locale;
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    const unavailableSource = { ...dataSource, source: 'database', dataStatus: 'unavailable' as const };
    const { container, rerender } = render(<StockKLineMockChart bars={[]} dataSource={unavailableSource} timezone="America/New_York" />);

    expect(screen.getByRole('status')).toHaveTextContent(dictionary['terminal.chart.emptyUnavailable']);
    expect(screen.queryByText(dictionary['terminal.chart.empty'])).not.toBeInTheDocument();
    expect(container.querySelector('.terminal-chart > svg')).toBeNull();
    for (const button of screen.getAllByRole('button')) expect(button).toBeDisabled();

    rerender(<StockKLineMockChart bars={[]} dataSource={dataSource} timezone="America/New_York" />);
    expect(screen.getByRole('status')).toHaveTextContent(dictionary['terminal.chart.empty']);
    expect(screen.queryByText(dictionary['terminal.chart.emptyUnavailable'])).not.toBeInTheDocument();

    rerender(<StockKLineMockChart bars={bars} dataSource={dataSource} timezone="America/New_York" />);
    expect(container.querySelectorAll('rect[fill="transparent"]')).toHaveLength(36);
    expect(screen.queryByText(dictionary['terminal.chart.empty'])).not.toBeInTheDocument();

    rerender(<StockKLineMockChart bars={[]} dataSource={unavailableSource} timezone="America/New_York" />);
    expect(screen.getByRole('status')).toHaveTextContent(dictionary['terminal.chart.emptyUnavailable']);
    expect(container.querySelector('.terminal-chart > svg')).toBeNull();
    expect(container.querySelector('.terminal-chart-tooltip')).toBeNull();
  });

  it('prioritizes invalid supplied bars over source unavailability', () => {
    render(<StockKLineMockChart bars={[{ ...bars[0], volume: -1 }]} dataSource={{ ...dataSource, dataStatus: 'unavailable' }} timezone="America/New_York" />);
    expect(screen.getByRole('status')).toHaveTextContent(zhCN['terminal.chart.invalidData']);
    expect(screen.queryByText(zhCN['terminal.chart.emptyUnavailable'])).not.toBeInTheDocument();
  });

  it('renders a single flat candle with zero volume without fabricating samples', () => {
    const bar = { ...bars[0], open: 100, close: 100, high: 100, low: 100, volume: 0 };
    const { container } = render(<StockKLineMockChart bars={[bar]} dataSource={dataSource} timezone="America/New_York" />);

    expect(screen.getByText('样本有限：仅 1 根 K 线')).toBeInTheDocument();
    expect(container.querySelectorAll('rect[fill="transparent"]')).toHaveLength(1);
    expect(container.innerHTML).not.toMatch(/NaN|Infinity/);
    for (const button of screen.getAllByRole('button')) {
      expect(button).toBeDisabled();
    }
  });

  it.each([
    [{ ...dataSource, dataStatus: 'unavailable' as const }, '数据源不可用 · 当前显示已有 K 线'],
    [{ ...dataSource, source: 'mock_provider', fallbackActive: true, dataStatus: 'unavailable' as const }, '回退数据 · 非真实行情'],
  ])('keeps supplied candles visible with a source boundary notice', (source, notice) => {
    const { container } = render(<StockKLineMockChart bars={bars} dataSource={source} timezone="America/New_York" />);

    expect(screen.getByText(notice)).toBeInTheDocument();
    expect(container.querySelectorAll('rect[fill="transparent"]')).toHaveLength(36);
  });

  it('follows the latest candles after an initially empty response and clears the chart on empty refresh', () => {
    const { container, rerender } = render(<StockKLineMockChart bars={[]} dataSource={dataSource} timezone="America/New_York" />);
    rerender(<StockKLineMockChart bars={bars} dataSource={dataSource} timezone="America/New_York" />);

    expect(screen.queryByText('暂无 K 线数据')).not.toBeInTheDocument();
    expect(screen.getByText('显示 36 / 48 根 K 线，滚轮可缩放')).toBeInTheDocument();
    const candles = container.querySelectorAll('rect[fill="transparent"]');
    fireEvent.mouseEnter(candles[candles.length - 1].parentElement as unknown as SVGGElement);
    expect(screen.getByText('O 147')).toBeInTheDocument();

    rerender(<StockKLineMockChart bars={[]} dataSource={dataSource} timezone="America/New_York" />);
    expect(screen.getByText('暂无 K 线数据')).toBeInTheDocument();
    expect(screen.queryByText('O 147')).not.toBeInTheDocument();
    expect(container.querySelector('.terminal-chart > svg')).toBeNull();
  });

  it('shows axes, volume, provenance and the default visible range', () => {
    const { container } = renderChart();

    expect(screen.getByRole('region', { name: '交互式 K 线图' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'K 线价格与成交量图' })).toBeInTheDocument();
    expect(screen.getByText('K线: YahooFinance 公开行情')).toBeInTheDocument();
    expect(screen.getByText('成交量 Volume')).toBeInTheDocument();
    expect(screen.getByText('显示 36 / 48 根 K 线，滚轮可缩放')).toBeInTheDocument();
    expect(screen.getByText('09/13')).toBeInTheDocument();
    expect(container.querySelectorAll('.terminal-chart-axis-label').length).toBeGreaterThan(6);
  });

  it('zooms with buttons and the mouse wheel, then enables right panning', () => {
    renderChart();

    const chart = screen.getByRole('region', { name: '交互式 K 线图' });
    const zoomIn = screen.getByRole('button', { name: '放大 K 线' });
    const panLeft = screen.getByRole('button', { name: '查看更早 K 线' });
    const panRight = screen.getByRole('button', { name: '查看更新 K 线' });

    expect(panLeft).toBeEnabled();
    expect(panRight).toBeDisabled();

    fireEvent.click(zoomIn);
    expect(screen.getByText('显示 30 / 48 根 K 线，滚轮可缩放')).toBeInTheDocument();

    fireEvent.wheel(chart, { deltaY: -100 });
    expect(screen.getByText('显示 24 / 48 根 K 线，滚轮可缩放')).toBeInTheDocument();

    fireEvent.click(panLeft);
    expect(panRight).toBeEnabled();
  });

  it('exposes named controls and a tooltip when an enabled button receives focus', async () => {
    renderChart();
    for (const name of ['放大 K 线', '缩小 K 线', '查看更早 K 线', '查看更新 K 线']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument();
    }
    fireEvent.focus(screen.getByRole('button', { name: '放大 K 线' }));
    expect(await screen.findByRole('tooltip')).toHaveTextContent('放大 K 线');
  });

  it('shows a tooltip for a disabled control without enabling panning', async () => {
    renderChart();
    const panRight = screen.getByRole('button', { name: '查看更新 K 线' });
    fireEvent.mouseEnter(panRight.parentElement as HTMLSpanElement);
    expect(await screen.findByRole('tooltip')).toHaveTextContent('查看更新 K 线');
    expect(panRight).toBeDisabled();
    expect(screen.getByText('显示 36 / 48 根 K 线，滚轮可缩放')).toBeInTheDocument();
  });

  it('localizes control names and tooltip text in English', async () => {
    localeState.locale = 'en-US';
    renderChart();
    for (const name of ['Zoom in on candles', 'Zoom out on candles', 'View earlier candles', 'View newer candles']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument();
    }
    fireEvent.focus(screen.getByRole('button', { name: 'Zoom in on candles' }));
    expect(await screen.findByRole('tooltip')).toHaveTextContent('Zoom in on candles');
    expect(screen.queryByRole('button', { name: '放大 K 线' })).not.toBeInTheDocument();
  });

  it('shows OHLCV details when a candle is hovered', () => {
    const { container } = renderChart();
    const firstCandle = Array.from(container.querySelectorAll('svg > g')).find(
      (group) => group.querySelector('rect[fill="transparent"]'),
    );

    expect(firstCandle).toBeDefined();
    fireEvent.mouseEnter(firstCandle as SVGGElement);

    expect(screen.getByText('09/13')).toBeInTheDocument();
    expect(screen.getByText('2026/09/13 12:00:00')).toBeInTheDocument();
    expect(screen.getByText('America/New_York')).toBeInTheDocument();
    expect(screen.getByText('O 112')).toBeInTheDocument();
    expect(screen.getByText('H 114')).toBeInTheDocument();
    expect(screen.getByText('L 111')).toBeInTheDocument();
    expect(screen.getByText('C 113')).toBeInTheDocument();
    expect(screen.getByText(/^V /)).toBeInTheDocument();

    fireEvent.mouseLeave(firstCandle as SVGGElement);
    expect(screen.queryByText('O 112')).not.toBeInTheDocument();
  });

  it.each([
    ['America/New_York', '2026-10-15T00:30:00Z', '10/14', '2026/10/14 20:30:00'],
    ['America/New_York', '2026-01-15T00:30:00Z', '01/14', '2026/01/14 19:30:00'],
    ['Asia/Hong_Kong', '2026-10-15T00:30:00Z', '10/15', '2026/10/15 08:30:00'],
    ['Asia/Shanghai', '2026-10-15T00:30:00Z', '10/15', '2026/10/15 08:30:00'],
  ])('uses %s for both axis and hover time at %s', (timezone, timestamp, axisDate, hoverDate) => {
    const { container } = render(<StockKLineMockChart bars={[{ ...bars[0], timestamp }]} dataSource={dataSource} timezone={timezone} />);
    expect(screen.getByText(axisDate)).toBeInTheDocument();
    const candle = container.querySelector('rect[fill="transparent"]')?.parentElement;
    expect(candle).not.toBeNull();
    fireEvent.mouseEnter(candle as unknown as SVGGElement);
    expect(screen.getByText(hoverDate)).toBeInTheDocument();
    expect(screen.getByText(timezone)).toBeInTheDocument();
  });
});

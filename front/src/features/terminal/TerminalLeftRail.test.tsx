import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import zhCN from '../../locales/zh-CN/terminal';
import enUS from '../../locales/en-US/terminal';
import { marketSnapshots } from './mockData';
import { TerminalLeftRail } from './TerminalLeftRail';
import type { MarketCode, TerminalPageKey } from './types';

const state = vi.hoisted(() => ({
  market: 'US' as MarketCode,
  locale: 'zh-CN',
  selectedSymbol: undefined as string | undefined,
  setSelectedSymbol: vi.fn(),
}));

// 仅替换应用上下文；真实 Ant Design 表格、标记和 Tooltip 仍参与测试。
vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: state.locale,
    formatMessage: ({ id }: { id: string }, values: Record<string, string | number> = {}) => {
      const dictionary = state.locale === 'en-US' ? enUS : zhCN;
      return Object.entries(values).reduce(
        (text, [key, value]) => text.replaceAll(`{${key}}`, String(value)),
        dictionary[id as keyof typeof dictionary] ?? id,
      );
    },
  }),
}));

vi.mock('./MarketContext', () => ({
  useMarket: () => ({ ...state, snapshot: marketSnapshots[state.market] }),
}));

const renderRail = (pageKey: TerminalPageKey) => render(
  <App><TerminalLeftRail pageKey={pageKey} snapshot={marketSnapshots[state.market]} /></App>,
);

beforeEach(() => {
  state.market = 'US';
  state.locale = 'zh-CN';
  state.selectedSymbol = undefined;
  state.setSelectedSymbol.mockClear();
});
afterEach(cleanup);

describe('left rail sample provenance', () => {
  it.each(['zh-CN', 'en-US'])('keeps strategy reference tabs and toggle accessible in %s', locale => {
    state.locale = locale;
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    const { container } = renderRail('strategy-lab');
    const toggle = screen.getByRole('button', { name: dictionary['terminal.strategy.marketReference'] });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(container.querySelector('.terminal-strategy-reference')).toHaveAttribute('data-expanded', 'true');
    fireEvent.click(screen.getByRole('tab', { name: dictionary['terminal.strategy.referenceSectors'] }));
    expect(screen.getByText(dictionary[marketSnapshots.US.sectors[0].labelId as keyof typeof dictionary])).toBeInTheDocument();
    expect(screen.getByText(dictionary['terminal.dataSource.mockProvider'])).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: dictionary['terminal.strategy.referenceCandidates'] }));
    fireEvent.click(screen.getByRole('button', { name: marketSnapshots.US.watchlist[0].symbol }));
    expect(state.setSelectedSymbol).toHaveBeenCalledWith(marketSnapshots.US.watchlist[0].symbol);
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });
  it.each((['US', 'HK', 'CN'] as const).flatMap(market =>
    ['zh-CN', 'en-US'].map(locale => ({ market, locale })),
  ))('labels research-target sample fields in $locale for $market', ({ market, locale }) => {
    state.market = market;
    state.locale = locale;
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    const first = marketSnapshots[market].watchlist[0];
    state.selectedSymbol = first.symbol;
    const { container } = renderRail('stock-research');

    expect(screen.getByText(dictionary['terminal.leftRail.researchTargets.sampleNote'])).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: dictionary['terminal.table.symbol'] })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: dictionary['terminal.leftRail.researchTargets.sampleChange'] })).toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: dictionary['terminal.table.change'] })).not.toBeInTheDocument();
    const activeRow = container.querySelector('.terminal-watchlist-row-active') as HTMLElement;
    expect(within(activeRow).getByText(dictionary['terminal.leftRail.researchTargets.sampleSignal'].replace('{signal}', dictionary[first.signalId as keyof typeof dictionary]))).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: first.symbol }));
    expect(state.setSelectedSymbol).toHaveBeenCalledWith(first.symbol);
  });

  it.each(['dashboard', 'ai-research', 'strategy-lab', 'backtest', 'portfolio'] as const)('keeps existing quote headings outside stock research: %s', (pageKey) => {
    renderRail(pageKey);
    expect(screen.getByRole('columnheader', { name: zhCN['terminal.table.change'] })).toBeInTheDocument();
    expect(screen.queryByText(zhCN['terminal.leftRail.researchTargets.sampleNote'])).not.toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: zhCN['terminal.leftRail.researchTargets.sampleChange'] })).not.toBeInTheDocument();
  });

  it.each([
    ['dashboard', 1], ['stock-research', 1], ['ai-research', 2],
    ['strategy-lab', 1], ['backtest', 2], ['portfolio', 1], ['monitor', 1],
  ] as const)('labels every sample panel on %s', (pageKey, badgeCount) => {
    renderRail(pageKey);
    expect(screen.getAllByText('Mock 样例')).toHaveLength(badgeCount);
    expect(screen.queryByText('YahooFinance 公开行情')).not.toBeInTheDocument();
  });

  it.each(['US', 'HK', 'CN'] as const)('keeps labels when the market is %s', (market) => {
    state.market = market;
    renderRail('dashboard');
    expect(screen.getAllByText('Mock 样例')).toHaveLength(1);
    expect(screen.getByText('Mock Provider')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: marketSnapshots[market].watchlist[0].symbol })).toBeInTheDocument();
  });

  it('uses the English locale rather than inline Chinese text', () => {
    state.locale = 'en-US';
    renderRail('dashboard');
    expect(screen.getAllByText('Mock sample')).toHaveLength(1);
    expect(screen.getByText('Mock Provider')).toBeInTheDocument();
    expect(screen.queryByText('Mock 样例')).not.toBeInTheDocument();
  });

  it('still selects a stock and keeps the selected row highlighted', () => {
    state.selectedSymbol = 'AAPL';
    const { container } = renderRail('stock-research');
    expect(within(container.querySelector('.terminal-watchlist-row-active') as HTMLElement)
      .getByRole('button', { name: 'AAPL' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'NVDA' }));
    expect(state.setSelectedSymbol).toHaveBeenCalledWith('NVDA');
  });

  it.each([
    ['dashboard', 0, 'terminal.leftRail.source.quotes'],
    ['monitor', 0, 'terminal.leftRail.source.events'],
    ['backtest', 0, 'terminal.leftRail.source.benchmark'],
  ] as const)('shows the appropriate provenance detail for %s panel %i', async (pageKey, index, detailId) => {
    renderRail(pageKey);
    const badge = screen.getAllByText('Mock 样例')[index];
    fireEvent.mouseOver(badge);
    const tooltip = await screen.findByText(zhCN[detailId]);
    // happy-dom 不计算定位尺寸；这里验证关联，实际可见性在浏览器检查。
    expect(tooltip).toHaveAttribute('role', 'tooltip');
    expect(badge).toHaveAttribute('aria-describedby', tooltip.id);
  });
});

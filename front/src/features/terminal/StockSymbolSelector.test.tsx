import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import enUS from '../../locales/en-US/terminal';
import zhCN from '../../locales/zh-CN/terminal';
import { formatDateTime } from './formatters';
import { MarketProvider, useMarket } from './MarketContext';
import { marketSnapshots } from './mockData';
import {
  type StockResearchTarget,
  StockSymbolSelector,
} from './StockSymbolSelector';

const localeState = vi.hoisted(() => ({ locale: 'zh-CN' }));

vi.mock('@ant-design/icons', () => ({
  SearchOutlined: () => null,
}));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: localeState.locale,
    formatMessage: (
      { id }: { id: string },
      values: Record<string, string | number | undefined> = {},
    ) => {
      const dictionary = localeState.locale === 'en-US' ? enUS : zhCN;
      return Object.entries(values).reduce(
        (text, [key, value]) =>
          text.replaceAll(`{${key}}`, String(value ?? '')),
        dictionary[id as keyof typeof dictionary] ?? id,
      );
    },
  }),
}));

const ContextProbe = () => {
  const { selectedSymbol, setMarket } = useMarket();
  return (
    <div>
      <span data-testid="selected-symbol">{selectedSymbol ?? ''}</span>
      <button type="button" onClick={() => setMarket('US')}>
        测试切换美股
      </button>
      <button type="button" onClick={() => setMarket('HK')}>
        测试切换港股
      </button>
    </div>
  );
};

const selectorFor = (researchTarget?: StockResearchTarget) => (
  <App>
    <MarketProvider>
      <StockSymbolSelector researchTarget={researchTarget} />
      <ContextProbe />
    </MarketProvider>
  </App>
);

const renderSelector = (researchTarget?: StockResearchTarget) =>
  render(selectorFor(researchTarget));

const saveSelectedSymbols = (symbols: Record<string, string>) => {
  window.localStorage.setItem(
    'ai-quant-terminal-selected-symbols',
    JSON.stringify(symbols),
  );
};

beforeEach(() => {
  localeState.locale = 'zh-CN';
  window.localStorage.clear();
});

afterEach(cleanup);

describe('StockSymbolSelector response identity', () => {
  it.each(['zh-CN', 'en-US'])('identifies a mismatched response in %s without changing the selection', locale => {
    localeState.locale = locale;
    saveSelectedSymbols({ US: 'MSFT' });
    const view = renderSelector({ market: 'US', symbol: 'AAPL', quoteTimestamp: '2026-10-19T02:30:00Z' });
    const notice = screen.getByRole('status');
    expect(notice).toHaveTextContent('US / MSFT');
    expect(notice).toHaveTextContent('US / AAPL');
    expect(screen.getByRole('combobox')).toHaveValue('MSFT');
    expect(screen.getByTestId('selected-symbol')).toHaveTextContent('MSFT');
    expect(JSON.parse(window.localStorage.getItem('ai-quant-terminal-selected-symbols') ?? '{}')).toEqual({ US: 'MSFT' });
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    expect(screen.getByText(dictionary['terminal.footer.time.unavailable'])).toBeInTheDocument();

    view.rerender(selectorFor({ market: 'US', symbol: 'MSFT', quoteTimestamp: '2026-10-19T02:30:00Z' }));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.queryByText(dictionary['terminal.footer.time.unavailable'])).not.toBeInTheDocument();
  });

  it('compares market explicitly even when symbol text is identical', () => {
    saveSelectedSymbols({ US: 'ABC' });
    renderSelector({ market: 'HK', symbol: 'ABC', quoteTimestamp: '2026-10-19T02:30:00Z' });
    expect(screen.getByRole('status')).toHaveTextContent('US / ABC；当前返回：HK / ABC');
    expect(screen.getByText(zhCN['terminal.footer.time.unavailable'])).toBeInTheDocument();
  });

  it('identifies an unexpected market for a default request without persisting a symbol', () => {
    renderSelector({ market: 'HK', symbol: '00700.HK' });
    expect(screen.getByRole('status')).toHaveTextContent('US / 默认标的；当前返回：HK / 00700.HK');
    expect(screen.getByTestId('selected-symbol')).toBeEmptyDOMElement();
  });

  it('does not treat an absent response or a normal default response as a mismatch', () => {
    const view = renderSelector();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    view.rerender(selectorFor({ market: 'US', symbol: 'NVDA' }));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    // 候选列表中的草稿不是已提交请求，不产生身份不一致提示。
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'AAPL' } });
    expect(screen.queryByText(/请求标的：/)).not.toBeInTheDocument();
  });

  it('keeps response identity visible alongside input validation and clears it when response is absent', () => {
    saveSelectedSymbols({ US: 'MSFT' });
    const view = renderSelector({ market: 'US', symbol: 'AAPL' });
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'AAPL?' } });
    fireEvent.click(screen.getByRole('button', { name: /研\s*究/ }));
    expect(screen.getByRole('alert')).toHaveTextContent(zhCN['terminal.stockSelector.invalid']);
    expect(screen.getByRole('status')).toHaveTextContent('US / MSFT；当前返回：US / AAPL');
    view.rerender(selectorFor());
    expect(screen.queryByText(/请求标的：/)).not.toBeInTheDocument();
    expect(screen.getByRole('combobox')).toHaveValue('AAPL?');
  });
});

describe('StockSymbolSelector presentation', () => {
  it('keeps a draft typed before the initial default response arrives', () => {
    const view = renderSelector();
    const input = screen.getByRole('combobox');
    fireEvent.change(input, { target: { value: 'MSFT' } });
    view.rerender(selectorFor());
    expect(input).toHaveValue('MSFT');

    view.rerender(selectorFor({ market: 'US', symbol: 'NVDA' }));
    expect(screen.getByText('当前标的：NVDA')).toBeInTheDocument();
    expect(input).toHaveValue('MSFT');
    expect(screen.getByTestId('selected-symbol')).toBeEmptyDOMElement();

    fireEvent.click(screen.getByRole('button', { name: '测试切换港股' }));
    expect(input).toHaveValue('');
  });

  it('preserves invalid draft feedback when the first default response arrives', () => {
    const view = renderSelector();
    const input = screen.getByRole('combobox');
    fireEvent.change(input, { target: { value: 'AAPL?' } });
    fireEvent.click(screen.getByRole('button', { name: /研\s*究/ }));
    view.rerender(selectorFor({ market: 'US', symbol: 'NVDA' }));
    expect(input).toHaveValue('AAPL?');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('alert')).toHaveTextContent(zhCN['terminal.stockSelector.invalid']);
  });

  it.each(['zh-CN', 'en-US'])('shows an explicit unselected state in %s before data is loaded', locale => {
    localeState.locale = locale;
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    renderSelector();
    expect(screen.getByText(dictionary['terminal.stockSelector.noSelection'])).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toHaveValue('');
    expect(screen.getByTestId('selected-symbol')).toBeEmptyDOMElement();
    expect(window.localStorage.getItem('ai-quant-terminal-selected-symbols')).toBeNull();
  });

  it.each([
    ['zh-CN', '当前标的：NVDA', '输入 US 股票代码后回车'],
    ['en-US', 'Current symbol: NVDA', 'Enter US symbol and press Enter'],
  ])('在 %s 中显示后端默认标的但不写入用户选择', (locale, title, placeholder) => {
    localeState.locale = locale;
    renderSelector({ market: 'US', symbol: 'NVDA' });

    expect(screen.getByText(title)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(placeholder)).toHaveValue('NVDA');
    expect(screen.getByTestId('selected-symbol')).toBeEmptyDOMElement();
    expect(
      window.localStorage.getItem('ai-quant-terminal-selected-symbols'),
    ).toBeNull();
    expect(
      screen.queryByText(/已切换研究标的|Research symbol switched/),
    ).not.toBeInTheDocument();
  });

  it('已保存的手选标的优先于后端默认值', () => {
    saveSelectedSymbols({ US: 'AAPL' });
    const view = renderSelector({ market: 'US', symbol: 'NVDA' });
    view.rerender(selectorFor({ market: 'US', symbol: 'MSFT' }));

    expect(screen.getByText('当前标的：AAPL')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('输入 US 股票代码后回车')).toHaveValue(
      'AAPL',
    );
    expect(screen.getByTestId('selected-symbol')).toHaveTextContent('AAPL');
  });

  it('未手选时随实际研究标的更新标题和输入值', () => {
    const view = renderSelector();
    view.rerender(selectorFor({ market: 'US', symbol: 'NVDA' }));
    expect(screen.getByText('当前标的：NVDA')).toBeInTheDocument();

    view.rerender(selectorFor({ market: 'US', symbol: 'AAPL' }));
    expect(screen.getByText('当前标的：AAPL')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('输入 US 股票代码后回车')).toHaveValue(
      'AAPL',
    );
    expect(screen.queryByText('当前标的：NVDA')).not.toBeInTheDocument();
    expect(
      window.localStorage.getItem('ai-quant-terminal-selected-symbols'),
    ).toBeNull();
  });

  it('shows search controls and labels actual quote time without a sample session status', () => {
    saveSelectedSymbols({ US: 'AAPL' });
    const quoteTimestamp = '2026-10-19T02:30:00Z';
    renderSelector({
      market: 'US',
      symbol: 'AAPL',
      quoteTimestamp,
      timezone: 'America/New_York',
    });

    expect(screen.getByText('个股研究标的')).toBeInTheDocument();
    expect(screen.getByText('当前标的：AAPL')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('输入 US 股票代码后回车')).toHaveValue(
      'AAPL',
    );
    expect(screen.getByRole('button', { name: /研\s*究/ })).toBeInTheDocument();
    expect(screen.queryByText('开盘')).not.toBeInTheDocument();
    expect(screen.getByText(/行情时间 ·/)).toBeInTheDocument();
    expect(
      screen.getByText(
        formatDateTime(quoteTimestamp, {
          timezone: 'America/New_York',
          locale: 'zh-CN',
        }),
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(
        formatDateTime(marketSnapshots.US.updatedAt, {
          timezone: marketSnapshots.US.timezone,
          locale: 'zh-CN',
        }),
      ),
    ).not.toBeInTheDocument();
  });

  it('uses English locale for labels, placeholder and quote time', () => {
    localeState.locale = 'en-US';
    saveSelectedSymbols({ US: 'AAPL' });
    renderSelector();

    expect(screen.getByText('Stock research symbol')).toBeInTheDocument();
    expect(screen.getByText('Current symbol: AAPL')).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText('Enter US symbol and press Enter'),
    ).toHaveValue('AAPL');
    expect(
      screen.getByRole('button', { name: 'Research' }),
    ).toBeInTheDocument();
    expect(screen.queryByText('Open')).not.toBeInTheDocument();
    expect(screen.getByText(/Quote time ·/)).toBeInTheDocument();
    expect(screen.getByText('Data time unavailable')).toBeInTheDocument();
  });
});

describe('StockSymbolSelector quote time', () => {
  it.each([
    ['US', 'AAPL', 'America/New_York', '2026/10/18 22:30:00'],
    ['HK', '00700.HK', 'Asia/Hong_Kong', '2026/10/19 10:30:00'],
    ['CN', '600519.SH', 'Asia/Shanghai', '2026/10/19 10:30:00'],
  ] as const)('按 %s 当前标的时区展示行情时间', (market, symbol, timezone, expected) => {
    window.localStorage.setItem('ai-quant-terminal-market', market);
    renderSelector({
      market,
      symbol,
      timezone,
      quoteTimestamp: '2026-10-19T02:30:00Z',
    });
    expect(screen.getByText(expected)).toBeInTheDocument();
    expect(screen.getByText(/行情时间 ·/)).toBeInTheDocument();
    expect(screen.queryByText(/^(开盘|休市|盘前|午间休市)$/)).not.toBeInTheDocument();
  });

  it.each([
    undefined,
    null,
    'invalid-time',
  ])('行情时间为 %s 时显示暂无数据时间', (quoteTimestamp) => {
    renderSelector({
      market: 'US',
      symbol: 'AAPL',
      timezone: 'America/New_York',
      quoteTimestamp,
    });
    expect(screen.getByText('暂无数据时间')).toBeInTheDocument();
    expect(
      screen.queryByText(
        formatDateTime(marketSnapshots.US.updatedAt, {
          timezone: marketSnapshots.US.timezone,
          locale: 'zh-CN',
        }),
      ),
    ).not.toBeInTheDocument();
  });

  it('手选标的与研究快照不一致时不显示旧标的时间', () => {
    saveSelectedSymbols({ US: 'MSFT' });
    const view = renderSelector({
      market: 'US',
      symbol: 'AAPL',
      timezone: 'America/New_York',
      quoteTimestamp: '2026-10-19T02:30:00Z',
    });
    expect(screen.getByText('当前标的：MSFT')).toBeInTheDocument();
    expect(screen.getByText('暂无数据时间')).toBeInTheDocument();
    view.rerender(
      selectorFor({
        market: 'US',
        symbol: 'MSFT',
        timezone: 'America/New_York',
        quoteTimestamp: '2026-10-19T03:30:00Z',
      }),
    );
    expect(screen.getByText('2026/10/18 23:30:00')).toBeInTheDocument();
    expect(screen.queryByText('暂无数据时间')).not.toBeInTheDocument();
  });

  it('同一标的刷新仅按响应更新时间，且不清除未提交的输入', () => {
    const target: StockResearchTarget = {
      market: 'US',
      symbol: 'NVDA',
      timezone: 'America/New_York',
      quoteTimestamp: '2026-10-19T02:30:00Z',
    };
    const view = renderSelector(target);
    const input = screen.getByPlaceholderText('输入 US 股票代码后回车');
    fireEvent.change(input, { target: { value: 'MSFT' } });
    view.rerender(selectorFor({ ...target }));
    expect(screen.getByText('2026/10/18 22:30:00')).toBeInTheDocument();

    view.rerender(
      selectorFor({ ...target, quoteTimestamp: '2026-10-19T03:30:00Z' }),
    );
    expect(screen.getByText('2026/10/18 23:30:00')).toBeInTheDocument();
    expect(screen.queryByText('2026/10/18 22:30:00')).not.toBeInTheDocument();
    expect(input).toHaveValue('MSFT');
  });
});

describe('StockSymbolSelector interaction', () => {
  it.each(['zh-CN', 'en-US'].flatMap(locale => [
    { locale, value: '   ', error: 'empty' },
    { locale, value: 'AAPL?', error: 'invalid' },
    { locale, value: 'AA PL', error: 'invalid' },
    { locale, value: 'A'.repeat(33), error: 'invalid' },
  ]))('rejects invalid input $value in $locale without changing the target', ({ locale, value, error }) => {
    localeState.locale = locale;
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    saveSelectedSymbols({ US: 'AAPL' });
    renderSelector({ market: 'US', symbol: 'AAPL' });
    const input = screen.getByRole('combobox');
    fireEvent.change(input, { target: { value } });
    fireEvent.click(screen.getByRole('button', { name: locale === 'en-US' ? 'Research' : /研\s*究/ }));
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent(dictionary[`terminal.stockSelector.${error}` as keyof typeof dictionary]);
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAttribute('aria-describedby', alert.id);
    expect(screen.getByTestId('selected-symbol')).toHaveTextContent('AAPL');
    expect(window.localStorage.getItem('ai-quant-terminal-selected-symbols')).toBe(JSON.stringify({ US: 'AAPL' }));

    fireEvent.change(input, { target: { value: 'MSFT' } });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(input).toHaveAttribute('aria-invalid', 'false');
  });

  it.each(['zh-CN', 'en-US'])('filters local candidates but accepts an unlisted symbol in %s', async locale => {
    localeState.locale = locale;
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    renderSelector({ market: 'US', symbol: 'NVDA' });
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'nv' } });
    expect(await screen.findByText(`NVDA · ${dictionary['terminal.stock.nvda']}`)).toBeInTheDocument();
    expect(screen.queryByText(`AAPL · ${dictionary['terminal.stock.aapl']}`)).not.toBeInTheDocument();
    fireEvent.change(input, { target: { value: 'TSLA' } });
    expect(screen.getByRole('status')).toHaveTextContent(dictionary['terminal.stockSelector.noCandidate']);
    fireEvent.click(screen.getByRole('button', { name: locale === 'en-US' ? 'Research' : /研\s*究/ }));
    expect(screen.getByTestId('selected-symbol')).toHaveTextContent('TSLA');
    expect(screen.queryByText(dictionary['terminal.stockSelector.noCandidate'])).not.toBeInTheDocument();
  });

  it.each([
    ['US', ' brk.b ', 'BRK.B'],
    ['US', 'brk-b', 'BRK-B'],
    ['HK', '00700.hk', '00700.HK'],
    ['CN', '600519.sh', '600519.SH'],
  ] as const)('accepts contract-compatible symbols for %s: %s', (market, value, expected) => {
    window.localStorage.setItem('ai-quant-terminal-market', market);
    renderSelector();
    fireEvent.change(screen.getByRole('combobox'), { target: { value } });
    fireEvent.click(screen.getByRole('button', { name: /研\s*究/ }));
    expect(screen.getByTestId('selected-symbol')).toHaveTextContent(expected);
    expect(screen.getByRole('combobox')).toHaveAttribute('aria-invalid', 'false');
  });

  it('clears an invalid draft without submitting an empty symbol', () => {
    saveSelectedSymbols({ US: 'AAPL' });
    const { container } = renderSelector({ market: 'US', symbol: 'AAPL' });
    const input = screen.getByRole('combobox');
    fireEvent.change(input, { target: { value: 'AAPL?' } });
    fireEvent.click(screen.getByRole('button', { name: /研\s*究/ }));
    expect(screen.getByRole('alert')).toBeInTheDocument();
    fireEvent.click(container.querySelector('.ant-input-clear-icon') as HTMLElement);
    expect(input).toHaveValue('');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByTestId('selected-symbol')).toHaveTextContent('AAPL');
  });

  it('同一默认标的刷新不覆盖输入草稿，提交后切换为用户选择', async () => {
    const view = renderSelector({ market: 'US', symbol: 'NVDA' });
    const input = screen.getByPlaceholderText('输入 US 股票代码后回车');
    fireEvent.change(input, { target: { value: ' msft ' } });
    view.rerender(selectorFor({ market: 'US', symbol: 'NVDA' }));

    expect(input).toHaveValue(' msft ');
    expect(screen.getByText('当前标的：NVDA')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /研\s*究/ }));

    expect(screen.getByText('当前标的：MSFT')).toBeInTheDocument();
    expect(screen.getByTestId('selected-symbol')).toHaveTextContent('MSFT');
    expect(
      window.localStorage.getItem('ai-quant-terminal-selected-symbols'),
    ).toBe(JSON.stringify({ US: 'MSFT' }));
    expect(await screen.findByText('已切换研究标的：MSFT')).toBeInTheDocument();
  });

  it('切换市场清除未提交草稿且不采用旧市场的研究标的', () => {
    const view = renderSelector({
      market: 'US',
      symbol: 'NVDA',
      timezone: 'America/New_York',
      quoteTimestamp: '2026-10-19T02:30:00Z',
    });
    fireEvent.change(screen.getByPlaceholderText('输入 US 股票代码后回车'), {
      target: { value: 'AMD' },
    });
    fireEvent.click(screen.getByRole('button', { name: '测试切换港股' }));

    expect(screen.getByPlaceholderText('输入 HK 股票代码后回车')).toHaveValue(
      '',
    );
    expect(screen.queryByText('当前标的：NVDA')).not.toBeInTheDocument();
    expect(screen.getByText('暂无数据时间')).toBeInTheDocument();
    expect(screen.queryByText('2026/10/18 22:30:00')).not.toBeInTheDocument();
    view.rerender(selectorFor({ market: 'HK', symbol: '00700.HK' }));
    expect(screen.getByText('当前标的：00700.HK')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('输入 HK 股票代码后回车')).toHaveValue(
      '00700.HK',
    );
    expect(
      window.localStorage.getItem('ai-quant-terminal-selected-symbols'),
    ).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: '测试切换美股' }));
    expect(screen.getByPlaceholderText('输入 US 股票代码后回车')).toHaveValue(
      '',
    );
    view.rerender(selectorFor({ market: 'US', symbol: 'NVDA' }));
    expect(screen.getByPlaceholderText('输入 US 股票代码后回车')).toHaveValue(
      'NVDA',
    );
  });

  it('normalizes a manually entered symbol and confirms the selection', async () => {
    renderSelector();
    const input = screen.getByPlaceholderText('输入 US 股票代码后回车');

    fireEvent.change(input, { target: { value: ' msft ' } });
    fireEvent.click(screen.getByRole('button', { name: /研\s*究/ }));

    expect(screen.getByTestId('selected-symbol')).toHaveTextContent('MSFT');
    expect(input).toHaveValue('MSFT');
    expect(
      window.localStorage.getItem('ai-quant-terminal-selected-symbols'),
    ).toBe(JSON.stringify({ US: 'MSFT' }));
    expect(await screen.findByText('已切换研究标的：MSFT')).toBeInTheDocument();
  });

  it('selects a symbol from the current market autocomplete options', async () => {
    renderSelector();
    const input = screen.getByPlaceholderText('输入 US 股票代码后回车');

    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'NV' } });
    const option = await screen.findByText('NVDA · 英伟达 NVIDIA');
    fireEvent.click(option);

    expect(screen.getByTestId('selected-symbol')).toHaveTextContent('NVDA');
    expect(input).toHaveValue('NVDA');
  });

  it('ignores an empty normalized search value', () => {
    saveSelectedSymbols({ US: 'AAPL' });
    renderSelector();
    const input = screen.getByPlaceholderText('输入 US 股票代码后回车');

    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: /研\s*究/ }));

    expect(screen.getByTestId('selected-symbol')).toHaveTextContent('AAPL');
    expect(
      window.localStorage.getItem('ai-quant-terminal-selected-symbols'),
    ).toBe(JSON.stringify({ US: 'AAPL' }));
    expect(screen.queryByText(/已切换研究标的/)).not.toBeInTheDocument();
  });

  it('restores the independently selected symbol when the market changes', () => {
    saveSelectedSymbols({ US: 'AAPL', HK: '00700.HK' });
    renderSelector();

    fireEvent.click(screen.getByRole('button', { name: '测试切换港股' }));
    expect(screen.getByText('当前标的：00700.HK')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('输入 HK 股票代码后回车')).toHaveValue(
      '00700.HK',
    );
    expect(screen.queryByText('休市')).not.toBeInTheDocument();
    expect(screen.getByText(/行情时间 ·/)).toHaveTextContent('暂无数据时间');

    fireEvent.click(screen.getByRole('button', { name: '测试切换美股' }));
    expect(screen.getByText('当前标的：AAPL')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('输入 US 股票代码后回车')).toHaveValue(
      'AAPL',
    );
  });
});

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MarketProvider, useMarket } from './MarketContext';

const MarketProbe = () => {
  const { market, selectedSymbol, snapshot, setMarket, setSelectedSymbol } =
    useMarket();

  return (
    <div>
      <span data-testid="market">{market}</span>
      <span data-testid="symbol">{selectedSymbol ?? ''}</span>
      <span data-testid="benchmark">{snapshot.benchmark}</span>
      <span data-testid="currency">{snapshot.currency}</span>
      <span data-testid="timezone">{snapshot.timezone}</span>
      <button type="button" onClick={() => setMarket('US')}>
        切换美股
      </button>
      <button type="button" onClick={() => setMarket('HK')}>
        切换港股
      </button>
      <button type="button" onClick={() => setMarket('CN')}>
        切换A股
      </button>
      <button type="button" onClick={() => setSelectedSymbol(' aapl ')}>
        选择美股标的
      </button>
      <button type="button" onClick={() => setSelectedSymbol(' 00700.hk ')}>
        选择港股标的
      </button>
      <button type="button" onClick={() => setSelectedSymbol(' 600519.sh ')}>
        选择A股标的
      </button>
      <button type="button" onClick={() => setSelectedSymbol('   ')}>
        清空标的
      </button>
    </div>
  );
};

const renderProvider = () =>
  render(
    <MarketProvider>
      <MarketProbe />
    </MarketProvider>,
  );

beforeEach(() => {
  window.localStorage.clear();
  vi.mocked(window.localStorage.getItem).mockClear();
  vi.mocked(window.localStorage.setItem).mockClear();
});

afterEach(cleanup);

describe('MarketProvider initialization', () => {
  it('defaults to the US market and its matching snapshot', () => {
    renderProvider();

    expect(screen.getByTestId('market')).toHaveTextContent('US');
    expect(screen.getByTestId('symbol').textContent).toBe('');
    expect(screen.getByTestId('benchmark')).toHaveTextContent('S&P 500');
    expect(screen.getByTestId('currency')).toHaveTextContent('USD');
    expect(screen.getByTestId('timezone')).toHaveTextContent(
      'America/New_York',
    );
  });

  it('restores the saved market and that market selected symbol', () => {
    window.localStorage.setItem('ai-quant-terminal-market', 'HK');
    window.localStorage.setItem(
      'ai-quant-terminal-selected-symbols',
      JSON.stringify({
        US: 'AAPL',
        HK: '00700.HK',
        CN: '600519.SH',
      }),
    );

    renderProvider();

    expect(screen.getByTestId('market')).toHaveTextContent('HK');
    expect(screen.getByTestId('symbol')).toHaveTextContent('00700.HK');
    expect(screen.getByTestId('benchmark')).toHaveTextContent('恒生指数 HSI');
    expect(screen.getByTestId('currency')).toHaveTextContent('HKD');
    expect(screen.getByTestId('timezone')).toHaveTextContent('Asia/Hong_Kong');
  });

  it('falls back safely when stored values are invalid', () => {
    window.localStorage.setItem('ai-quant-terminal-market', 'JP');
    window.localStorage.setItem(
      'ai-quant-terminal-selected-symbols',
      '{invalid json',
    );

    renderProvider();

    expect(screen.getByTestId('market')).toHaveTextContent('US');
    expect(screen.getByTestId('symbol').textContent).toBe('');
    expect(screen.getByTestId('benchmark')).toHaveTextContent('S&P 500');
  });
});

describe('MarketProvider updates', () => {
  it.each([
    ['切换港股', 'HK', '恒生指数 HSI', 'HKD', 'Asia/Hong_Kong'],
    ['切换A股', 'CN', '沪深300 CSI 300', 'CNY', 'Asia/Shanghai'],
  ] as const)('switches the complete market context through %s', (buttonName, market, benchmark, currency, timezone) => {
    renderProvider();

    fireEvent.click(screen.getByRole('button', { name: buttonName }));

    expect(screen.getByTestId('market')).toHaveTextContent(market);
    expect(screen.getByTestId('benchmark')).toHaveTextContent(benchmark);
    expect(screen.getByTestId('currency')).toHaveTextContent(currency);
    expect(screen.getByTestId('timezone')).toHaveTextContent(timezone);
    expect(window.localStorage.setItem).toHaveBeenCalledWith(
      'ai-quant-terminal-market',
      market,
    );
  });

  it('normalizes and preserves an independent selected symbol for each market', () => {
    renderProvider();

    fireEvent.click(screen.getByRole('button', { name: '选择美股标的' }));
    expect(screen.getByTestId('symbol')).toHaveTextContent('AAPL');

    fireEvent.click(screen.getByRole('button', { name: '切换港股' }));
    expect(screen.getByTestId('symbol').textContent).toBe('');
    fireEvent.click(screen.getByRole('button', { name: '选择港股标的' }));
    expect(screen.getByTestId('symbol')).toHaveTextContent('00700.HK');

    fireEvent.click(screen.getByRole('button', { name: '切换A股' }));
    fireEvent.click(screen.getByRole('button', { name: '选择A股标的' }));
    expect(screen.getByTestId('symbol')).toHaveTextContent('600519.SH');

    fireEvent.click(screen.getByRole('button', { name: '切换美股' }));
    expect(screen.getByTestId('symbol')).toHaveTextContent('AAPL');
    expect(
      window.localStorage.getItem('ai-quant-terminal-selected-symbols'),
    ).toBe(
      JSON.stringify({
        US: 'AAPL',
        HK: '00700.HK',
        CN: '600519.SH',
      }),
    );
  });

  it('removes a selected symbol when the normalized input is empty', () => {
    renderProvider();
    fireEvent.click(screen.getByRole('button', { name: '选择美股标的' }));
    fireEvent.click(screen.getByRole('button', { name: '清空标的' }));

    expect(screen.getByTestId('symbol').textContent).toBe('');
    expect(
      window.localStorage.getItem('ai-quant-terminal-selected-symbols'),
    ).toBe('{}');
  });
});

describe('useMarket', () => {
  it('rejects consumers rendered outside MarketProvider', () => {
    const consoleError = vi
      .spyOn(console, 'error')
      .mockImplementation(() => undefined);

    expect(() => render(<MarketProbe />)).toThrow(
      'useMarket must be used within MarketProvider',
    );

    consoleError.mockRestore();
  });
});

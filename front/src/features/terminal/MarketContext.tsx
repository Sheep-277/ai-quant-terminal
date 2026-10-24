import React, { createContext, useContext, useMemo, useState } from 'react';
import { marketSnapshots } from './mockData';
import type { MarketCode, MarketSnapshot } from './types';

type MarketContextValue = {
  market: MarketCode;
  selectedSymbol?: string;
  snapshot: MarketSnapshot;
  setMarket: (market: MarketCode) => void;
  setSelectedSymbol: (symbol?: string) => void;
};

const MarketContext = createContext<MarketContextValue | undefined>(undefined);

const readInitialMarket = (): MarketCode => {
  if (typeof window === 'undefined') {
    return 'US';
  }
  const stored = window.localStorage.getItem('ai-quant-terminal-market');
  return stored === 'US' || stored === 'HK' || stored === 'CN' ? stored : 'US';
};

const readInitialSelectedSymbols = (): Partial<Record<MarketCode, string>> => {
  if (typeof window === 'undefined') {
    return {};
  }

  try {
    const stored = window.localStorage.getItem('ai-quant-terminal-selected-symbols');
    const parsed = stored ? JSON.parse(stored) : {};
    return {
      US: typeof parsed.US === 'string' ? parsed.US : undefined,
      HK: typeof parsed.HK === 'string' ? parsed.HK : undefined,
      CN: typeof parsed.CN === 'string' ? parsed.CN : undefined,
    };
  } catch {
    return {};
  }
};

const normalizeSymbol = (symbol?: string) => {
  const normalized = symbol?.trim().toUpperCase();
  return normalized || undefined;
};

export const MarketProvider = ({ children }: { children: React.ReactNode }) => {
  const [market, setMarketState] = useState<MarketCode>(readInitialMarket);
  const [selectedSymbols, setSelectedSymbols] = useState<Partial<Record<MarketCode, string>>>(
    readInitialSelectedSymbols,
  );

  const setMarket = (nextMarket: MarketCode) => {
    setMarketState(nextMarket);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('ai-quant-terminal-market', nextMarket);
    }
  };

  const setSelectedSymbol = (symbol?: string) => {
    const nextSymbol = normalizeSymbol(symbol);
    setSelectedSymbols((currentSymbols) => {
      const nextSymbols = {
        ...currentSymbols,
        [market]: nextSymbol,
      };

      if (typeof window !== 'undefined') {
        window.localStorage.setItem('ai-quant-terminal-selected-symbols', JSON.stringify(nextSymbols));
      }

      return nextSymbols;
    });
  };

  const value = useMemo(
    () => ({
      market,
      selectedSymbol: selectedSymbols[market],
      snapshot: marketSnapshots[market],
      setMarket,
      setSelectedSymbol,
    }),
    [market, selectedSymbols],
  );

  return <MarketContext.Provider value={value}>{children}</MarketContext.Provider>;
};

export const useMarket = () => {
  const value = useContext(MarketContext);
  if (!value) {
    throw new Error('useMarket must be used within MarketProvider');
  }
  return value;
};

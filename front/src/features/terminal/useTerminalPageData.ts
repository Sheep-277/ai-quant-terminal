import { mergeMarketOverviewSnapshot, toAIResearchSnapshot, toBacktestSnapshot, toMonitorSnapshot, toPortfolioSnapshot, toStockResearchSnapshot, toStrategyLabSnapshot } from './apiAdapters';
import { useMarket } from './MarketContext';
import type { TerminalPageKey } from './types';
import { useAIResearchLLMStatus, useAIResearchTask, useCreateAIResearchTask } from './useAIResearchTask';
import { useBacktestResult, useCreateBacktestTask } from './useBacktestResult';
import { useMarketOverview } from './useMarketOverview';
import { useMonitorStream } from './useMonitorStream';
import { useCreatePaperOrder, usePortfolioSummary } from './usePortfolioSummary';
import { usePreTradeRiskCheck } from './usePreTradeRiskCheck';
import { useProviderStatus } from './useProviderStatus';
import { useStockResearch } from './useStockResearch';
import { useCreateStrategyDraft, useStrategyLab } from './useStrategyLab';

export const useTerminalPageData = (pageKey: TerminalPageKey) => {
  const { market, selectedSymbol, snapshot: contextSnapshot } = useMarket();
  const isDashboardPage = pageKey === 'dashboard';
  const providerStatusQuery = useProviderStatus();
  const marketOverviewQuery = useMarketOverview(market, {
    enabled: isDashboardPage,
  });
  const stockResearchQuery = useStockResearch({
    market,
    symbol: selectedSymbol,
    enabled: pageKey === 'stock-research',
  });
  const strategyLabQuery = useStrategyLab({
    market,
    enabled: pageKey === 'strategy-lab',
  });
  const createStrategyDraftMutation = useCreateStrategyDraft();
  const backtestQuery = useBacktestResult({
    market,
    enabled: pageKey === 'backtest',
  });
  const createBacktestTaskMutation = useCreateBacktestTask();
  const createAIResearchTaskMutation = useCreateAIResearchTask();
  const aiResearchLLMStatusQuery = useAIResearchLLMStatus(pageKey === 'ai-research');
  const aiResearchQuery = useAIResearchTask({
    market,
    enabled: pageKey === 'ai-research',
  });
  const portfolioQuery = usePortfolioSummary({
    market,
    enabled: pageKey === 'portfolio',
  });
  const createPaperOrderMutation = useCreatePaperOrder();
  const preTradeRiskCheckMutation = usePreTradeRiskCheck();
  const monitorQuery = useMonitorStream({
    market,
    enabled: pageKey === 'monitor',
  });

  // 只有市场总览页使用后端 overview 覆盖首页 Mock 快照，其它页继续以 MarketContext 作为全局市场上下文。
  const snapshot = isDashboardPage
    ? mergeMarketOverviewSnapshot(contextSnapshot, marketOverviewQuery.data)
    : contextSnapshot;

  return {
    market,
    selectedSymbol,
    snapshot,
    stockResearch: stockResearchQuery.data ? toStockResearchSnapshot(stockResearchQuery.data) : undefined,
    strategyLab: strategyLabQuery.data ? toStrategyLabSnapshot(strategyLabQuery.data) : undefined,
    backtest: backtestQuery.data ? toBacktestSnapshot(backtestQuery.data) : undefined,
    aiResearch: aiResearchQuery.data ? toAIResearchSnapshot(aiResearchQuery.data) : undefined,
    portfolio: portfolioQuery.data ? toPortfolioSnapshot(portfolioQuery.data) : undefined,
    monitor: monitorQuery.data ? toMonitorSnapshot(monitorQuery.data) : undefined,
    providerStatus: providerStatusQuery.data,
    providerStatusQuery,
    marketOverviewQuery,
    stockResearchQuery,
    strategyLabQuery,
    createStrategyDraftMutation,
    backtestQuery,
    createBacktestTaskMutation,
    createAIResearchTaskMutation,
    aiResearchLLMStatusQuery,
    aiResearchQuery,
    portfolioQuery,
    createPaperOrderMutation,
    preTradeRiskCheckMutation,
    monitorQuery,
  };
};

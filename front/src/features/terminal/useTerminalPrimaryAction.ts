import { useQueryClient } from '@tanstack/react-query';
import { useIntl } from '@umijs/max';
import { App } from 'antd';
import type { AIResearchLLMStatusResponse } from '@/services/terminal/aiResearch';
import { getPortfolioAccountSummary } from '@/services/terminal/portfolio';
import type {
  AIResearchRequest,
  AIResearchTaskCreateResponse,
  BacktestRequest,
  BacktestTaskCreateResponse,
  PaperOrderCreateResponse,
  PaperOrderRequest,
  PreTradeRiskCheckRequest,
  PreTradeRiskCheckResponse,
  StrategyDraftCreateRequest,
  StrategyDraftDto,
} from './apiTypes';
import { buildPaperOrderCreatePayload, buildPreTradeRiskCheckPayload } from './portfolioOrderPayloads';
import { buildBacktestTaskCreatePayload, buildStrategyDraftCreatePayload, getAIResearchSymbols } from './terminalActionPayloads';
import type { AIResearchSnapshot, BacktestSnapshot, MarketCode, PortfolioSnapshot, TerminalPageKey } from './types';
import { portfolioAccountSummaryQueryKey, portfolioSummaryQueryKey } from './usePortfolioSummary';

type MutationLike<TInput, TOutput> = {
  mutateAsync: (payload: TInput) => Promise<TOutput>;
};

type RefetchLike = {
  refetch: () => Promise<unknown>;
};

type UseTerminalPrimaryActionParams = {
  pageKey: TerminalPageKey;
  market: MarketCode;
  selectedSymbol?: string;
  strategyDraft?: StrategyDraftDto;
  strategyDraftPayload?: StrategyDraftCreateRequest;
  backtest?: BacktestSnapshot;
  portfolio?: PortfolioSnapshot;
  aiResearch?: AIResearchSnapshot;
  aiResearchLLMStatus?: AIResearchLLMStatusResponse;
  marketOverviewQuery: RefetchLike;
  stockResearchQuery: RefetchLike;
  createStrategyDraftMutation: MutationLike<StrategyDraftCreateRequest, StrategyDraftDto>;
  strategyLabQuery: RefetchLike;
  createBacktestTaskMutation: MutationLike<BacktestRequest, BacktestTaskCreateResponse>;
  preTradeRiskCheckMutation: MutationLike<PreTradeRiskCheckRequest, PreTradeRiskCheckResponse>;
  createPaperOrderMutation: MutationLike<PaperOrderRequest, PaperOrderCreateResponse>;
  portfolioQuery: RefetchLike;
  createAIResearchTaskMutation: MutationLike<AIResearchRequest, AIResearchTaskCreateResponse>;
  monitorQuery: RefetchLike;
};

export const useTerminalPrimaryAction = ({
  pageKey,
  market,
  selectedSymbol,
  strategyDraft,
  strategyDraftPayload,
  backtest,
  portfolio,
  aiResearch,
  aiResearchLLMStatus,
  marketOverviewQuery,
  stockResearchQuery,
  createStrategyDraftMutation,
  strategyLabQuery,
  createBacktestTaskMutation,
  preTradeRiskCheckMutation,
  createPaperOrderMutation,
  portfolioQuery,
  createAIResearchTaskMutation,
  monitorQuery,
}: UseTerminalPrimaryActionParams) => {
  const intl = useIntl();
  const { message } = App.useApp();
  const queryClient = useQueryClient();

  const showPrototypeMessage = () => {
    void message.info(intl.formatMessage({ id: 'terminal.prototypeOnly' }));
  };

  const runRefreshAction = async (refetchTarget: RefetchLike, successMessageId: string, failedMessageId: string) => {
    try {
      await refetchTarget.refetch();
      void message.success(intl.formatMessage({ id: successMessageId }));
    } catch {
      void message.error(intl.formatMessage({ id: failedMessageId }));
    }
  };

  const runStrategyDraftAction = async () => {
    if (!strategyDraft) {
      void message.warning(intl.formatMessage({ id: 'terminal.strategy.createUnavailable' }));
      return;
    }

    try {
      const createdDraft = await createStrategyDraftMutation.mutateAsync(strategyDraftPayload ?? buildStrategyDraftCreatePayload(strategyDraft));
      const messageContent = intl.formatMessage(
        { id: createdDraft.parameters.fallback_active === true ? 'terminal.strategy.createFallback' : 'terminal.strategy.createSuccess' },
        { strategyId: createdDraft.strategy_id },
      );
      if (createdDraft.parameters.fallback_active === true) {
        void message.warning(messageContent);
      } else {
        void message.success(messageContent);
      }
      await strategyLabQuery.refetch();
    } catch {
      void message.error(intl.formatMessage({ id: 'terminal.strategy.createFailed' }));
    }
  };

  const runBacktestAction = async () => {
    if (!backtest) {
      void message.warning(intl.formatMessage({ id: 'terminal.backtest.createUnavailable' }));
      return;
    }

    try {
      const task = await createBacktestTaskMutation.mutateAsync(buildBacktestTaskCreatePayload(backtest));
      const messageContent = intl.formatMessage(
        { id: task.fallback_active ? 'terminal.backtest.createFallback' : 'terminal.backtest.createSuccess' },
        { backtestId: task.backtest_id, pollUrl: task.poll_url },
      );
      if (task.fallback_active) {
        void message.warning(messageContent);
      } else {
        void message.success(messageContent);
      }
    } catch {
      void message.error(intl.formatMessage({ id: 'terminal.backtest.createFailed' }));
    }
  };

  const refreshPortfolioAfterPaperOrder = async (accountId: string) => {
    try {
      const accountSummary = await getPortfolioAccountSummary({ accountId });
      queryClient.setQueryData(portfolioAccountSummaryQueryKey(accountId), accountSummary);
      queryClient.setQueryData(portfolioSummaryQueryKey(accountSummary.market), accountSummary);
    } catch {
      // 账户级读取依赖数据库开关；失败时回退市场级刷新，避免影响模拟下单成功回执。
      try {
        await portfolioQuery.refetch();
      } catch {
        // 刷新失败不改变订单已经被后端接收的事实，后续自动轮询或手动刷新仍可恢复页面。
      }
    }
  };

  const runPaperOrderAction = async () => {
    if (!portfolio) {
      void message.warning(intl.formatMessage({ id: 'terminal.portfolio.orderUnavailable' }));
      return;
    }

    try {
      const riskCheck = await preTradeRiskCheckMutation.mutateAsync(buildPreTradeRiskCheckPayload(portfolio));
      if (riskCheck.decision === 'rejected') {
        void message.error(
          intl.formatMessage(
            { id: 'terminal.portfolio.riskRejected' },
            { reason: riskCheck.reasons[0]?.message ?? riskCheck.decision },
          ),
        );
        return;
      }

      if (riskCheck.decision === 'warning') {
        void message.warning(
          intl.formatMessage(
            { id: 'terminal.portfolio.riskWarning' },
            { reason: riskCheck.reasons[0]?.message ?? riskCheck.decision },
          ),
        );
      } else {
        void message.success(intl.formatMessage({ id: 'terminal.portfolio.riskApproved' }));
      }

      const order = await createPaperOrderMutation.mutateAsync(buildPaperOrderCreatePayload(portfolio));
      const messageContent = intl.formatMessage(
        { id: order.fallback_active ? 'terminal.portfolio.orderFallback' : 'terminal.portfolio.orderSuccess' },
        {
          orderId: order.order_id,
          symbol: order.symbol,
          status: intl.formatMessage({ id: `terminal.portfolio.status.${order.status}` }),
        },
      );
      if (order.fallback_active) {
        void message.warning(messageContent);
      } else {
        void message.success(messageContent);
        await refreshPortfolioAfterPaperOrder(order.account_id);
      }
    } catch {
      void message.error(intl.formatMessage({ id: 'terminal.portfolio.orderFailed' }));
    }
  };

  const runAIResearchAction = async () => {
    try {
      const task = await createAIResearchTaskMutation.mutateAsync({
        market,
        query: aiResearch?.query ?? intl.formatMessage({ id: 'terminal.aiTask.mock' }),
        symbols: selectedSymbol ? [selectedSymbol] : getAIResearchSymbols(aiResearch),
        include_strategy_idea: true,
      });

      const messageContent = intl.formatMessage(
        { id: task.fallback_active ? 'terminal.aiResearch.createFallback' : 'terminal.aiResearch.createSuccess' },
        { taskId: task.task_id, pollUrl: task.poll_url },
      );
      if (task.fallback_active) {
        void message.warning(messageContent);
      } else if (aiResearchLLMStatus && !aiResearchLLMStatus.configured) {
        void message.warning(
          intl.formatMessage(
            { id: 'terminal.aiResearch.createSuccessWithoutLlm' },
            {
              taskId: task.task_id,
              pollUrl: task.poll_url,
              nextAction: aiResearchLLMStatus.next_action,
            },
          ),
        );
      } else {
        void message.success(messageContent);
      }
    } catch {
      void message.error(intl.formatMessage({ id: 'terminal.aiResearch.createFailed' }));
    }
  };

  const runPrimaryAction = async () => {
    switch (pageKey) {
      case 'strategy-lab':
        await runStrategyDraftAction();
        return;

      case 'backtest':
        await runBacktestAction();
        return;

      case 'portfolio':
        await runPaperOrderAction();
        return;

      case 'ai-research':
        await runAIResearchAction();
        return;

      case 'dashboard':
        await runRefreshAction(
          marketOverviewQuery,
          'terminal.dashboard.refreshSuccess',
          'terminal.dashboard.refreshFailed',
        );
        return;

      case 'stock-research':
        await runRefreshAction(
          stockResearchQuery,
          'terminal.stockResearch.refreshSuccess',
          'terminal.stockResearch.refreshFailed',
        );
        return;

      case 'monitor':
        await runRefreshAction(
          monitorQuery,
          'terminal.monitor.refreshSuccess',
          'terminal.monitor.refreshFailed',
        );
        return;
    }
  };

  return {
    runPrimaryAction,
    showPrototypeMessage,
  };
};

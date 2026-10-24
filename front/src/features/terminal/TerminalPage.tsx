import { useIntl } from '@umijs/max';
import { useEffect, useState } from 'react';
import type { StrategyDraftCreateRequest } from './apiTypes';
import { getDataSourceLabelText } from './DataSourceBadge';
import { formatDateTime } from './formatters';
import { pageDefinitions } from './mockData';
import { TerminalEventStreamPanel } from './TerminalEventStreamPanel';
import { TerminalLeftRail } from './TerminalLeftRail';
import { TerminalMainContent } from './TerminalMainContent';
import { TerminalPageHeader } from './TerminalPageHeader';
import { TerminalRightRail } from './TerminalRightRail';
import { MetricStrip } from './TerminalShared';
import { useEventColumns } from './terminalEventColumns';
import type { TerminalPageKey } from './types';
import { useTerminalPageData } from './useTerminalPageData';
import { useTerminalPrimaryAction } from './useTerminalPrimaryAction';
import './terminal.less';

const useLocaleCode = () => {
  const intl = useIntl();
  return intl.locale?.startsWith('en') ? 'en-US' : 'zh-CN';
};

type TerminalLayoutMode = 'market' | 'research' | 'workflow' | 'monitor';

// 仅决定展示区域的比例；数据查询和业务操作仍按原页面配置执行。
const pageLayoutModes: Record<TerminalPageKey, TerminalLayoutMode> = {
  dashboard: 'market',
  'stock-research': 'research',
  'ai-research': 'research',
  'strategy-lab': 'workflow',
  backtest: 'workflow',
  portfolio: 'workflow',
  monitor: 'monitor',
};

export const TerminalPage = ({ pageKey }: { pageKey: TerminalPageKey }) => {
  const intl = useIntl();
  const locale = useLocaleCode();
  const {
    market,
    selectedSymbol,
    snapshot,
    stockResearch,
    strategyLab,
    backtest,
    aiResearch,
    portfolio,
    monitor,
    providerStatus,
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
  } = useTerminalPageData(pageKey);
  const page = pageDefinitions[pageKey];
  const eventColumns = useEventColumns();
  const showIndexOverview = pageKey === 'dashboard';
  // 个股事件已集中在“新闻与事件”页签，外层公共事件面板只保留在市场总览。
  const showContextEventPanel = pageKey === 'dashboard';
  const strategyDraftSource = strategyLabQuery.data?.drafts[0];
  const [strategyDraftPayload, setStrategyDraftPayload] = useState<StrategyDraftCreateRequest | undefined>();

  // 模块时间取自对应响应，不使用预置市场上下文时间冒充当前数据时间。
  const pageDataTimes: Record<TerminalPageKey, {
    timestamp?: string | null;
    timezone?: string;
    labelId: string;
  }> = {
    dashboard: {
      timestamp: marketOverviewQuery.data?.timestamp,
      timezone: marketOverviewQuery.data?.timezone,
      labelId: 'terminal.footer.time.overview',
    },
    'stock-research': {
      timestamp: stockResearch?.quote.timestamp,
      timezone: stockResearch?.timezone,
      labelId: 'terminal.footer.time.quote',
    },
    'ai-research': {
      timestamp: aiResearch?.timestamp,
      timezone: aiResearch?.timezone,
      labelId: 'terminal.footer.time.research',
    },
    'strategy-lab': {
      timestamp: strategyLab?.timestamp,
      labelId: 'terminal.footer.time.strategy',
    },
    backtest: {
      timestamp: backtest?.timestamp,
      timezone: backtest?.timezone,
      labelId: 'terminal.footer.time.backtest',
    },
    portfolio: {
      timestamp: portfolio?.account.updatedAt,
      timezone: portfolio?.timezone,
      labelId: 'terminal.footer.time.account',
    },
    monitor: {
      timestamp: monitor?.timestamp,
      timezone: monitor?.timezone,
      labelId: 'terminal.footer.time.monitor',
    },
  };
  const pageDataTime = pageDataTimes[pageKey];
  const providerSource = providerStatusQuery.isError
    ? intl.formatMessage({ id: 'terminal.providerStatus.error' })
    : providerStatus
      ? getDataSourceLabelText(
          providerStatus.fallback_active
            ? 'mock_fallback'
            : providerStatus.active_source ?? providerStatus.source_type
              ?? (providerStatus.mode === 'mock' ? 'mock_provider' : providerStatus.provider_name),
          intl,
        )
      : intl.formatMessage({
          id: providerStatusQuery.isFetching
            ? 'terminal.providerStatus.loading'
            : 'terminal.providerStatus.unknown',
        });
  const footerText = intl.formatMessage(
    { id: 'terminal.dataFootnote' },
    {
      market: snapshot.code,
      benchmark: pageKey === 'backtest' ? backtest?.benchmark ?? snapshot.benchmark : snapshot.benchmark,
      source: providerSource,
      timestampLabel: intl.formatMessage({ id: pageDataTime.labelId }),
      timestamp: pageDataTime.timestamp
        ? formatDateTime(pageDataTime.timestamp, { timezone: pageDataTime.timezone ?? snapshot.timezone, locale })
        : intl.formatMessage({ id: 'terminal.footer.time.unavailable' }),
    },
  );

  useEffect(() => {
    setStrategyDraftPayload(undefined);
  }, [market, strategyDraftSource?.strategy_id]);

  const { runPrimaryAction, showPrototypeMessage } = useTerminalPrimaryAction({
    pageKey,
    market,
    selectedSymbol,
    strategyDraft: strategyDraftSource,
    strategyDraftPayload,
    backtest,
    portfolio,
    aiResearch,
    marketOverviewQuery,
    stockResearchQuery,
    createStrategyDraftMutation,
    strategyLabQuery,
    createBacktestTaskMutation,
    preTradeRiskCheckMutation,
    createPaperOrderMutation,
    portfolioQuery,
    createAIResearchTaskMutation,
    aiResearchLLMStatus: aiResearchLLMStatusQuery.data,
    monitorQuery,
  });
  const runHeaderPrimaryAction = () => {
    if (pageKey !== 'ai-research') {
      void runPrimaryAction();
      return;
    }

    const inputPanel = document.getElementById('terminal-ai-research-task-input');
    inputPanel?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    inputPanel?.querySelector('textarea')?.focus();
  };

  return (
    <main className="terminal-page">
      <TerminalPageHeader
        pageKey={pageKey}
        page={page}
        snapshot={snapshot}
        providerStatus={providerStatus}
        providerStatusLoading={providerStatusQuery.isFetching}
        providerStatusError={providerStatusQuery.isError}
        apiStatusMap={{
          dashboard: { isError: marketOverviewQuery.isError, isFetching: marketOverviewQuery.isFetching },
          'stock-research': { isError: stockResearchQuery.isError, isFetching: stockResearchQuery.isFetching },
          'strategy-lab': { isError: strategyLabQuery.isError, isFetching: strategyLabQuery.isFetching },
          backtest: { isError: backtestQuery.isError, isFetching: backtestQuery.isFetching },
          'ai-research': { isError: aiResearchQuery.isError, isFetching: aiResearchQuery.isFetching },
          portfolio: { isError: portfolioQuery.isError, isFetching: portfolioQuery.isFetching },
          monitor: { isError: monitorQuery.isError, isFetching: monitorQuery.isFetching },
        }}
        primaryActionLoading={
          (pageKey === 'ai-research' && false) ||
          (pageKey === 'strategy-lab' && createStrategyDraftMutation.isPending) ||
          (pageKey === 'backtest' && createBacktestTaskMutation.isPending) ||
          (pageKey === 'portfolio' && (preTradeRiskCheckMutation.isPending || createPaperOrderMutation.isPending)) ||
          (pageKey === 'dashboard' && marketOverviewQuery.isFetching) ||
          (pageKey === 'stock-research' && stockResearchQuery.isFetching) ||
          (pageKey === 'monitor' && monitorQuery.isFetching)
        }
        onMockDataClick={showPrototypeMessage}
        onPrimaryActionClick={runHeaderPrimaryAction}
      />

      {showIndexOverview ? <div className="terminal-dashboard-indices"><MetricStrip metrics={snapshot.indices} market={snapshot.code} /></div> : null}

      {pageKey === 'ai-research' ? (
        <details className="terminal-ai-reference">
          <summary>{intl.formatMessage({ id: 'terminal.aiResearch.referenceDetails' })}</summary>
          <div className="terminal-ai-reference-panels">
            <TerminalLeftRail pageKey={pageKey} snapshot={snapshot} />
            <TerminalRightRail pageKey={pageKey} />
          </div>
        </details>
      ) : null}

      {pageKey === 'portfolio' ? (
        <details className="terminal-portfolio-reference">
          <summary>{intl.formatMessage({ id: 'terminal.portfolio.referenceDetails' })}</summary>
          <div className="terminal-portfolio-reference-panels">
            <TerminalLeftRail pageKey={pageKey} snapshot={snapshot} />
            <TerminalRightRail pageKey={pageKey} />
          </div>
        </details>
      ) : null}

      {pageKey === 'monitor' ? (
        <details className="terminal-monitor-reference">
          <summary>{intl.formatMessage({ id: 'terminal.monitor.referenceDetails' })}</summary>
          <div className="terminal-monitor-reference-panels">
            <TerminalLeftRail pageKey={pageKey} snapshot={snapshot} />
            <TerminalRightRail pageKey={pageKey} />
          </div>
        </details>
      ) : null}

      {pageKey === 'backtest' ? (
        <details className="terminal-backtest-reference">
          <summary>{intl.formatMessage({ id: 'terminal.backtest.referenceDetails' })}</summary>
          <div className="terminal-backtest-reference-panels">
            <TerminalLeftRail pageKey={pageKey} snapshot={snapshot} />
            <TerminalRightRail pageKey={pageKey} />
          </div>
        </details>
      ) : null}

      {pageKey === 'stock-research' ? (
        <details className="terminal-stock-reference">
          <summary>{intl.formatMessage({ id: 'terminal.stockResearch.referenceDetails' })}</summary>
          <div className="terminal-stock-reference-panels">
            <TerminalLeftRail pageKey={pageKey} snapshot={snapshot} />
            <TerminalRightRail pageKey={pageKey} />
          </div>
        </details>
      ) : null}

      <div className="terminal-shell" data-layout={pageLayoutModes[pageKey]} data-page={pageKey}>
        <section className="terminal-center">
          <TerminalMainContent
            pageKey={pageKey}
            snapshot={snapshot}
            eventColumns={eventColumns}
            providerStatus={providerStatus}
            aiResearch={aiResearch}
            aiResearchTaskReceipt={createAIResearchTaskMutation.data}
            backtest={backtest}
            backtestQueryState={backtestQuery}
            backtestTaskReceipt={createBacktestTaskMutation.data}
            monitor={monitor}
            portfolio={portfolio}
            paperOrderReceipt={createPaperOrderMutation.data}
            preTradeRiskCheckReceipt={preTradeRiskCheckMutation.data}
            stockResearch={stockResearch}
            requestedStockSymbol={selectedSymbol}
            stockResearchQueryState={stockResearchQuery}
            strategyLab={strategyLab}
            strategyDraftSource={strategyDraftSource}
            strategyDraftReceipt={createStrategyDraftMutation.data}
            onStrategyDraftPayloadChange={setStrategyDraftPayload}
          />
        </section>

        {pageKey === 'dashboard' ? <TerminalLeftRail pageKey={pageKey} snapshot={snapshot} /> : null}

        {showContextEventPanel ? (
          <div className="terminal-dashboard-events">
            <TerminalEventStreamPanel pageKey={pageKey} events={snapshot.events} eventColumns={eventColumns} />
          </div>
        ) : null}

        {pageKey === 'dashboard' ? (
          <details className="terminal-dashboard-reference">
            <summary>{intl.formatMessage({ id: 'terminal.dashboard.referenceDetails' })}</summary>
            <TerminalRightRail pageKey={pageKey} />
          </details>
        ) : null}
      </div>

      <footer className="terminal-footer-note" title={footerText}>
        {footerText}
      </footer>
    </main>
  );
};

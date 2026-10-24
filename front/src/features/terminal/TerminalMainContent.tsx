import { LoadingOutlined, ReloadOutlined } from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { Alert, Button, Spin, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { ReactNode } from 'react';
import { AIResearchContent } from './AIResearchContent';
import type { AIResearchTaskCreateResponse, BacktestTaskCreateResponse, PaperOrderCreateResponse, PreTradeRiskCheckResponse, ProviderStatusResponse, StrategyDraftCreateRequest, StrategyDraftDto } from './apiTypes';
import { BacktestContent } from './BacktestContent';
import { DashboardContent } from './DashboardContent';
import { MonitorContent } from './MonitorContent';
import { PortfolioContent } from './PortfolioContent';
import { StockResearchContent } from './StockResearchContent';
import { StockSymbolSelector } from './StockSymbolSelector';
import { StrategyLabContent } from './StrategyLabContent';
import { TerminalLeftRail } from './TerminalLeftRail';
import { DataSourceBadge, getDataSourceColor, getDataSourceLabelText, getProviderBadgeColor, SimpleDataSourceBadge } from './DataSourceBadge';
import { formatDateTime } from './formatters';
import { Panel, TerminalTableText } from './TerminalShared';
import type { AIResearchSnapshot, BacktestSnapshot, EventRow, MarketSnapshot, MonitorSnapshot, PortfolioSnapshot, StockResearchSnapshot, StrategyLabSnapshot, TerminalPageKey } from './types';

const pageTitleIdMap: Record<TerminalPageKey, string> = {
  dashboard: 'terminal.page.dashboard.title',
  'stock-research': 'terminal.page.stockResearch.title',
  'ai-research': 'terminal.page.aiResearch.title',
  'strategy-lab': 'terminal.page.strategyLab.title',
  backtest: 'terminal.page.backtest.title',
  portfolio: 'terminal.page.portfolio.title',
  monitor: 'terminal.page.monitor.title',
};

const fallbackPanelIdMap: Record<TerminalPageKey, string> = {
  dashboard: 'terminal.panel.marketDataPreparing',
  'stock-research': 'terminal.panel.stockDataPreparing',
  'ai-research': 'terminal.panel.aiResearchPreparing',
  'strategy-lab': 'terminal.panel.strategyDataPreparing',
  backtest: 'terminal.panel.backtestDataPreparing',
  portfolio: 'terminal.panel.portfolioDataPreparing',
  monitor: 'terminal.panel.monitorDataPreparing',
};

const buildDataSourceTags = ({
  pageKey,
  providerStatus,
  snapshot,
  stockResearch,
  aiResearch,
  strategyLab,
  backtest,
  portfolio,
  monitor,
  intl,
}: Pick<TerminalMainContentProps, 'pageKey' | 'providerStatus' | 'snapshot' | 'stockResearch' | 'aiResearch' | 'strategyLab' | 'backtest' | 'portfolio' | 'monitor'> & {
  intl: ReturnType<typeof useIntl>;
}): ReactNode[] => {
  const providerSource = getDataSourceLabelText(
    providerStatus?.active_source ?? providerStatus?.source_type ?? providerStatus?.mode,
    intl,
  );
  const providerDataStatus = providerStatus?.data_status ?? 'unavailable';
  const providerDataStatusLabel = intl.formatMessage({ id: `terminal.dataStatus.${providerDataStatus}` });
  const providerColor = getProviderBadgeColor(providerStatus);
  const providerTooltip = [
    providerStatus?.provider_name
      ? intl.formatMessage(
          { id: 'terminal.providerStatus.tooltip.provider' },
          { provider: providerStatus.provider_name },
        )
      : undefined,
    intl.formatMessage(
      { id: 'terminal.providerStatus.tooltip.activeSource' },
      { source: providerSource },
    ),
    intl.formatMessage(
      { id: 'terminal.providerStatus.tooltip.dataStatus' },
      { status: providerDataStatusLabel },
    ),
    providerStatus?.fallback_reason,
    providerStatus?.next_action,
    providerStatus?.missing_configuration?.length
      ? intl.formatMessage(
          { id: 'terminal.providerStatus.tooltip.missingConfiguration' },
          { items: providerStatus.missing_configuration.join(', ') },
        )
      : undefined,
  ].filter(Boolean).join(' / ');
  const simpleSourceBadge = (
    key: string,
    labelId: string,
    value: number | string,
    tooltip?: string,
    color?: string,
  ) => (
    <SimpleDataSourceBadge
      className="terminal-status-tag"
      color={color}
      key={key}
      labelId={labelId}
      tooltip={tooltip}
      value={value}
    />
  );
  const backtestDataMode = backtest?.dataMode;
  const backtestDataModeLabel = getDataSourceLabelText(backtestDataMode, intl);
  const backtestDataModeTooltip = backtest
    ? [
        intl.formatMessage({ id: 'terminal.dataSource.tooltip.source' }, { source: backtestDataModeLabel }),
        intl.formatMessage({ id: 'terminal.backtest.dataModeTooltip' }, { dataMode: backtestDataModeLabel }),
      ].join(' / ')
    : undefined;

  switch (pageKey) {
    case 'stock-research':
      return [
        stockResearch?.quoteDataSource ? (
          <DataSourceBadge
            className="terminal-status-tag"
            key="quote-source"
            labelId="terminal.dataSource.marketData"
            source={stockResearch.quoteDataSource}
          />
        ) : simpleSourceBadge('quote-source', 'terminal.dataSource.marketData', intl.formatMessage({ id: 'terminal.dataSource.unknown' })),
        stockResearch?.klineDataSource ? (
          <DataSourceBadge
            className="terminal-status-tag"
            key="kline-source"
            labelId="terminal.dataSource.kline"
            source={stockResearch.klineDataSource}
          />
        ) : simpleSourceBadge('kline-source', 'terminal.dataSource.kline', intl.formatMessage({ id: 'terminal.dataSource.unknown' })),
        simpleSourceBadge('fundamental-source', 'terminal.dataSource.fundamental', getDataSourceLabelText(stockResearch?.fundamentalDataStatus.source, intl)),
        simpleSourceBadge('factor-source', 'terminal.dataSource.factor', getDataSourceLabelText(stockResearch?.factorDataStatus.source, intl)),
      ];

    case 'ai-research':
      return [
        simpleSourceBadge('task-source', 'terminal.dataSource.task', intl.formatMessage({ id: `terminal.dataStatus.${aiResearch?.dataStatus ?? providerDataStatus}` })),
        simpleSourceBadge('evidence-source', 'terminal.dataSource.evidence', aiResearch?.evidence.length ?? 0),
        simpleSourceBadge('provider-source', 'terminal.dataSource.provider', providerSource, providerTooltip, providerColor),
      ];

    case 'strategy-lab':
      return [
        simpleSourceBadge('strategy-source', 'terminal.dataSource.strategyDraft', strategyLab?.drafts.length ?? 0),
        simpleSourceBadge('provider-source', 'terminal.dataSource.provider', providerSource, providerTooltip, providerColor),
        simpleSourceBadge('market-source', 'terminal.dataSource.market', snapshot.code),
      ];

    case 'backtest':
      return [
        simpleSourceBadge(
          'backtest-source',
          'terminal.dataSource.backtestData',
          backtestDataModeLabel,
          backtestDataModeTooltip,
          getDataSourceColor(backtestDataMode),
        ),
        simpleSourceBadge('backtest-status', 'terminal.table.status', backtest ? intl.formatMessage({ id: `terminal.backtest.status.${backtest.status}` }) : '-'),
        simpleSourceBadge('provider-source', 'terminal.dataSource.provider', providerSource, providerTooltip, providerColor),
      ];

    case 'portfolio':
      return [
        simpleSourceBadge('account-source', 'terminal.dataSource.account', getDataSourceLabelText(portfolio?.dataMode, intl)),
        simpleSourceBadge('orders-source', 'terminal.dataSource.orders', portfolio?.orders.length ?? 0),
        simpleSourceBadge('provider-source', 'terminal.dataSource.provider', providerSource, providerTooltip, providerColor),
      ];

    case 'monitor':
      return [
        simpleSourceBadge('stream-source', 'terminal.dataSource.stream', intl.formatMessage({ id: `terminal.dataStatus.${monitor?.stream.dataStatus ?? providerDataStatus}` })),
        simpleSourceBadge('signals-source', 'terminal.dataSource.signals', monitor?.signals.length ?? 0),
        simpleSourceBadge('provider-source', 'terminal.dataSource.provider', providerSource, providerTooltip, providerColor),
      ];

    default:
      return [
        simpleSourceBadge('market-data-source', 'terminal.dataSource.marketData', providerDataStatusLabel),
        simpleSourceBadge('provider-source', 'terminal.dataSource.provider', providerSource, providerTooltip, providerColor),
        simpleSourceBadge('market-source', 'terminal.dataSource.market', snapshot.code),
      ];
  }
};

const DataSourceStrip = (props: TerminalMainContentProps) => {
  const intl = useIntl();
  const tags = buildDataSourceTags({ ...props, intl });

  return (
    <div className="terminal-data-footnote terminal-data-source-strip">
      <TerminalTableText className="terminal-data-footnote-title">
        {intl.formatMessage({ id: 'terminal.dataSourceStrip.title' })}
      </TerminalTableText>
      <div className="terminal-data-footnote-tags">
        {tags}
      </div>
    </div>
  );
};

const PageDataFallback = ({
  pageKey,
  snapshot,
}: {
  pageKey: TerminalPageKey;
  snapshot: MarketSnapshot;
}) => {
  const intl = useIntl();

  return (
    <Panel
      title={intl.formatMessage({ id: fallbackPanelIdMap[pageKey] })}
      icon={<LoadingOutlined />}
    >
      <div className="terminal-data-fallback">
        <Spin size="small" />
        <div>
          <TerminalTableText>
            {intl.formatMessage({ id: pageTitleIdMap[pageKey] })}
          </TerminalTableText>
          <p>
            {pageKey === 'stock-research'
              ? `${intl.formatMessage({ id: 'terminal.apiSyncing' })} · ${snapshot.code} / ${snapshot.benchmark}`
              : intl.formatMessage(
              { id: 'terminal.dataPreparing.body' },
              { market: snapshot.code, benchmark: snapshot.benchmark },
            )}
          </p>
        </div>
      </div>
    </Panel>
  );
};

const StockResearchErrorNotice = ({
  query,
  stockResearch,
}: {
  query: NonNullable<TerminalMainContentProps['stockResearchQueryState']>;
  stockResearch?: StockResearchSnapshot;
}) => {
  const intl = useIntl();
  const retryLabel = intl.formatMessage({ id: 'app.error.retry' });

  return (
    <Alert
      showIcon
      type={stockResearch ? 'warning' : 'error'}
      title={intl.formatMessage({ id: 'terminal.stockResearch.refreshFailed' })}
      description={stockResearch
        ? `${intl.formatMessage({ id: 'terminal.footer.time.quote' })}: ${stockResearch.quote.timestamp ? formatDateTime(stockResearch.quote.timestamp, {
            timezone: stockResearch.timezone,
            locale: intl.locale,
          }) : intl.formatMessage({ id: 'terminal.footer.time.unavailable' })}`
        : intl.formatMessage({ id: 'terminal.dataStatus.unavailable' })}
      action={
        <Tooltip title={retryLabel}>
          <Button
            size="small"
            icon={<ReloadOutlined />}
            aria-label={retryLabel}
            loading={query.isFetching}
            disabled={query.isFetching}
            onClick={() => { void query.refetch(); }}
          />
        </Tooltip>
      }
      style={{ marginBottom: 'var(--aqt-panel-gap)' }}
    />
  );
};

const BacktestReadNotice = ({
  query,
  backtest,
}: {
  query: NonNullable<TerminalMainContentProps['backtestQueryState']>;
  backtest?: BacktestSnapshot;
}) => {
  const intl = useIntl();
  const retryLabel = intl.formatMessage({ id: 'app.error.retry' });
  // 查询失败不等于回测任务失败；已有结果保留原始生成时间。
  return (
    <Alert
      showIcon
      type={backtest ? 'warning' : 'error'}
      title={intl.formatMessage({ id: 'terminal.backtest.readFailed' })}
      description={backtest
        ? `${intl.formatMessage({ id: 'terminal.footer.time.backtest' })}: ${formatDateTime(backtest.timestamp, { timezone: backtest.timezone, locale: intl.locale })}`
        : intl.formatMessage({ id: 'terminal.dataStatus.unavailable' })}
      action={
        <Tooltip title={retryLabel}>
          <Button size="small" icon={<ReloadOutlined />} aria-label={retryLabel}
            loading={query.isFetching} disabled={query.isFetching}
            onClick={() => { void query.refetch(); }} />
        </Tooltip>
      }
    />
  );
};

export type TerminalMainContentProps = {
  pageKey: TerminalPageKey;
  snapshot: MarketSnapshot;
  eventColumns: ColumnsType<EventRow>;
  providerStatus?: ProviderStatusResponse;
  backtest?: BacktestSnapshot;
  backtestQueryState?: {
    isError: boolean;
    isFetching: boolean;
    refetch: () => Promise<unknown>;
  };
  backtestTaskReceipt?: BacktestTaskCreateResponse;
  aiResearch?: AIResearchSnapshot;
  aiResearchTaskReceipt?: AIResearchTaskCreateResponse;
  monitor?: MonitorSnapshot;
  portfolio?: PortfolioSnapshot;
  paperOrderReceipt?: PaperOrderCreateResponse;
  preTradeRiskCheckReceipt?: PreTradeRiskCheckResponse;
  stockResearch?: StockResearchSnapshot;
  stockResearchQueryState?: {
    isError: boolean;
    isFetching: boolean;
    refetch: () => Promise<unknown>;
  };
  requestedStockSymbol?: string;
  strategyLab?: StrategyLabSnapshot;
  strategyDraftSource?: StrategyDraftDto;
  strategyDraftReceipt?: StrategyDraftDto;
  onStrategyDraftPayloadChange?: (payload: StrategyDraftCreateRequest | undefined) => void;
};

export const TerminalMainContent = ({
  pageKey,
  snapshot,
  eventColumns,
  providerStatus,
  backtest,
  backtestQueryState,
  backtestTaskReceipt,
  aiResearch,
  aiResearchTaskReceipt,
  monitor,
  portfolio,
  paperOrderReceipt,
  preTradeRiskCheckReceipt,
  stockResearch,
  stockResearchQueryState,
  requestedStockSymbol,
  strategyLab,
  strategyDraftSource,
  strategyDraftReceipt,
  onStrategyDraftPayloadChange,
}: TerminalMainContentProps) => {
  const intl = useIntl();
  const contentProps = {
    pageKey,
    snapshot,
    eventColumns,
    providerStatus,
    backtest,
    backtestTaskReceipt,
    aiResearch,
    aiResearchTaskReceipt,
    monitor,
    portfolio,
    paperOrderReceipt,
    preTradeRiskCheckReceipt,
    stockResearch,
    strategyLab,
    strategyDraftSource,
    strategyDraftReceipt,
    onStrategyDraftPayloadChange,
  };

  switch (pageKey) {
    case 'dashboard':
      return (
        <>
          <DataSourceStrip {...contentProps} />
          <DashboardContent providerStatus={providerStatus} snapshot={snapshot} eventColumns={eventColumns} />
        </>
      );

    case 'stock-research':
      return (
        <div className="terminal-stack">
          {stockResearch && stockResearchQueryState?.isError ? (
            <StockResearchErrorNotice query={stockResearchQueryState} stockResearch={stockResearch} />
          ) : null}
          {stockResearch ? <DataSourceStrip {...contentProps} /> : null}
          {/* 固定挂载搜索入口，加载或错误状态切换时不丢失用户输入。 */}
          <StockSymbolSelector researchTarget={stockResearch ? {
            market: stockResearch.market,
            symbol: stockResearch.symbol,
            quoteTimestamp: stockResearch.quote.timestamp,
            timezone: stockResearch.timezone,
          } : undefined} />
          {stockResearch ? (
            <StockResearchContent snapshot={snapshot} stockResearch={stockResearch} requestedSymbol={requestedStockSymbol} eventColumns={eventColumns} />
          ) : stockResearchQueryState?.isError ? (
            <Panel title={`${intl.formatMessage({ id: pageTitleIdMap[pageKey] })} / ${snapshot.code}`}>
              <StockResearchErrorNotice query={stockResearchQueryState} />
            </Panel>
          ) : (
            <PageDataFallback pageKey={pageKey} snapshot={snapshot} />
          )}
        </div>
      );

    case 'ai-research':
      return aiResearch ? (
        <>
          <DataSourceStrip {...contentProps} />
          <AIResearchContent research={aiResearch} taskReceipt={aiResearchTaskReceipt} />
        </>
      ) : (
        <PageDataFallback pageKey={pageKey} snapshot={snapshot} />
      );

    case 'strategy-lab':
      return strategyLab ? (
        <>
          <DataSourceStrip {...contentProps} />
          <div className="terminal-strategy-layout">
            <TerminalLeftRail pageKey="strategy-lab" snapshot={snapshot} />
            <StrategyLabContent
              strategyLab={strategyLab}
              strategyDraftReceipt={strategyDraftReceipt}
              strategyDraftSource={strategyDraftSource}
              onDraftPayloadChange={onStrategyDraftPayloadChange}
            />
          </div>
        </>
      ) : (
        <PageDataFallback pageKey={pageKey} snapshot={snapshot} />
      );

    case 'backtest':
      return (
        <div className="terminal-stack">
          {backtestQueryState?.isError ? <BacktestReadNotice query={backtestQueryState} backtest={backtest} /> : null}
          {backtest ? (
            <>
              <DataSourceStrip {...contentProps} />
              <BacktestContent backtest={backtest} taskReceipt={backtestTaskReceipt} />
            </>
          ) : backtestQueryState?.isError ? (
            <Panel title={`${intl.formatMessage({ id: pageTitleIdMap[pageKey] })} / ${snapshot.code}`}>
              <p className="terminal-data-footnote">{intl.formatMessage({ id: 'terminal.dataStatus.unavailable' })}</p>
            </Panel>
          ) : <PageDataFallback pageKey={pageKey} snapshot={snapshot} />}
        </div>
      );

    case 'portfolio':
      return portfolio ? (
        <>
          <DataSourceStrip {...contentProps} />
          <PortfolioContent
            portfolio={portfolio}
            paperOrderReceipt={paperOrderReceipt}
            preTradeRiskCheckReceipt={preTradeRiskCheckReceipt}
          />
        </>
      ) : (
        <PageDataFallback pageKey={pageKey} snapshot={snapshot} />
      );

    case 'monitor':
      return monitor ? (
        <>
          <DataSourceStrip {...contentProps} />
          <MonitorContent monitor={monitor} />
        </>
      ) : (
        <PageDataFallback pageKey={pageKey} snapshot={snapshot} />
      );
  }

  return <PageDataFallback pageKey={pageKey} snapshot={snapshot} />;
};

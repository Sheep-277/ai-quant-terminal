import { BarChartOutlined, StockOutlined } from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { App, Button, Table, Tabs, Tag, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';
import { CompactDataSourceBadge } from './DataSourceBadge';
import { formatCurrency, formatNumber, formatPercent } from './formatters';
import { useMarket } from './MarketContext';
import { Panel, SectorTape, TerminalTableText } from './TerminalShared';
import type { EventRow, MarketSnapshot, Metric, QuoteRow, TerminalPageKey } from './types';

const useLocaleCode = () => {
  const intl = useIntl();
  return intl.locale?.startsWith('en') ? 'en-US' : 'zh-CN';
};

const useQuoteColumns = (): ColumnsType<QuoteRow> => {
  const intl = useIntl();
  const locale = useLocaleCode();
  const { market, setSelectedSymbol } = useMarket();
  const { message } = App.useApp();

  const selectSymbol = (symbol: string) => {
    setSelectedSymbol(symbol);
    void message.success(intl.formatMessage({ id: 'terminal.search.selectedSymbol' }, { symbol }));
  };

  return [
    {
      title: intl.formatMessage({ id: 'terminal.table.symbol' }),
      dataIndex: 'symbol',
      width: 110,
      fixed: 'left',
      render: (value: string) => (
        <Button className="terminal-symbol-link" size="small" type="link" onClick={() => selectSymbol(value)}>
          {value}
        </Button>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.name' }),
      dataIndex: 'nameId',
      width: 150,
      render: (value: string) => <TerminalTableText>{intl.formatMessage({ id: value })}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.lastPrice' }),
      dataIndex: 'price',
      align: 'right',
      width: 92,
      render: (value: number) => <TerminalTableText>{formatCurrency(value, market)}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.change' }),
      dataIndex: 'changePercent',
      align: 'right',
      width: 82,
      render: (value: number) => (
        <TerminalTableText className={value < 0 ? 'terminal-negative' : 'terminal-positive'}>
          {formatPercent(value, {}, locale)}
        </TerminalTableText>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.volume' }),
      dataIndex: 'volume',
      align: 'right',
      width: 92,
      render: (value: number) => <TerminalTableText>{formatNumber(value, { notation: 'compact' }, locale)}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.signal' }),
      dataIndex: 'signalId',
      width: 128,
      render: (value: string) => <TerminalTableText>{intl.formatMessage({ id: value })}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.risk' }),
      dataIndex: 'riskId',
      width: 92,
      render: (value: string) => <TerminalTableText>{intl.formatMessage({ id: value })}</TerminalTableText>,
    },
  ];
};

const useCompactQuoteColumns = (showSampleLabels = false): ColumnsType<QuoteRow> => {
  const intl = useIntl();
  const locale = useLocaleCode();
  const { setSelectedSymbol } = useMarket();
  const { message } = App.useApp();

  const selectSymbol = (symbol: string) => {
    setSelectedSymbol(symbol);
    void message.success(intl.formatMessage({ id: 'terminal.search.selectedSymbol' }, { symbol }));
  };

  return [
    {
      title: showSampleLabels
        ? intl.formatMessage({ id: 'terminal.table.symbol' })
        : `${intl.formatMessage({ id: 'terminal.table.symbol' })} / ${intl.formatMessage({ id: 'terminal.table.signal' })}`,
      dataIndex: 'symbol',
      // 窄栏以纵向层级保留代码和信号，涨跌幅单独对齐。
      render: (value: string, record: QuoteRow) => (
        <div className="terminal-left-quote-cell">
          <Button
            className="terminal-symbol-link"
            size="small"
            type="link"
            title={`${value} / ${intl.formatMessage({ id: record.nameId })}`}
            onClick={() => selectSymbol(value)}
          >
            {value}
          </Button>
          <TerminalTableText className="terminal-left-quote-signal">
            {showSampleLabels ? intl.formatMessage(
              { id: 'terminal.leftRail.researchTargets.sampleSignal' },
              { signal: intl.formatMessage({ id: record.signalId }) },
            ) : intl.formatMessage({ id: record.signalId })}
          </TerminalTableText>
        </div>
      ),
    },
    {
      title: showSampleLabels
        ? <span className="terminal-research-sample-change" title={intl.formatMessage({ id: 'terminal.leftRail.researchTargets.sampleChange' })}>{intl.formatMessage({ id: 'terminal.leftRail.researchTargets.sampleChange' })}</span>
        : intl.formatMessage({ id: 'terminal.table.change' }),
      dataIndex: 'changePercent',
      align: 'right',
      width: showSampleLabels ? 96 : 80,
      render: (value: number) => (
        <TerminalTableText className={value < 0 ? 'terminal-negative' : 'terminal-positive'}>
          {formatPercent(value, {}, locale)}
        </TerminalTableText>
      ),
    },
  ];
};

const useEventContextColumns = (): ColumnsType<EventRow> => {
  const intl = useIntl();

  return [
    {
      title: `${intl.formatMessage({ id: 'terminal.table.source' })} / ${intl.formatMessage({ id: 'terminal.table.event' })}`,
      dataIndex: 'eventTitle',
      render: (value: string, record: EventRow) => (
        <div className="terminal-left-event-cell">
          <TerminalTableText className="terminal-muted">
            {intl.formatMessage({ id: record.sourceId })}
          </TerminalTableText>
          <TerminalTableText className="terminal-left-event-title">{value}</TerminalTableText>
        </div>
      ),
    },
  ];
};

const formatMetricValue = (metric: Metric, market: MarketSnapshot['code'], locale: string) => {
  if (metric.valueFormat === 'currency') {
    return formatCurrency(metric.value, market);
  }

  if (metric.valueFormat === 'percent') {
    return formatPercent(metric.value, {}, locale);
  }

  return formatNumber(metric.value, { notation: 'compact' }, locale);
};

const CompactMetricList = ({
  metrics,
  market,
}: {
  metrics: Metric[];
  market: MarketSnapshot['code'];
}) => {
  const intl = useIntl();
  const locale = useLocaleCode();

  return (
    <div className="terminal-left-metric-list">
      {metrics.map((metric) => (
        <div className="terminal-left-metric-row" key={metric.labelId}>
          <TerminalTableText>{intl.formatMessage({ id: metric.labelId })}</TerminalTableText>
          <TerminalTableText className={`terminal-tone-${metric.tone ?? 'neutral'}`}>
            {formatMetricValue(metric, market, locale)}
          </TerminalTableText>
        </div>
      ))}
    </div>
  );
};

const compactRows = <T,>(rows: T[]) => rows.slice(0, 4);

const shouldShowSectorPerformance = (pageKey: TerminalPageKey) =>
  pageKey === 'dashboard' || pageKey === 'strategy-lab';

const MockContextBadge = ({ detailId }: { detailId: string }) => {
  const intl = useIntl();

  // 这里标记左栏自身的样例来源，不继承主体区域的 Provider 就绪状态。
  return (
    <Tooltip title={intl.formatMessage({ id: detailId })}>
      <Tag>{intl.formatMessage({ id: 'terminal.leftRail.source.mock' })}</Tag>
    </Tooltip>
  );
};

export const TerminalLeftRail = ({
  pageKey,
  snapshot,
}: {
  pageKey: TerminalPageKey;
  snapshot: MarketSnapshot;
}) => {
  const intl = useIntl();
  const { selectedSymbol } = useMarket();
  const quoteColumns = useQuoteColumns();
  const compactQuoteColumns = useCompactQuoteColumns(pageKey === 'stock-research');
  const eventContextColumns = useEventContextColumns();
  const activeSymbol = selectedSymbol ?? snapshot.watchlist[0]?.symbol;
  const compactWatchlistTitle =
    pageKey === 'stock-research'
      ? 'terminal.panel.researchTargets'
      : 'terminal.panel.marketCandidates';
  const focusedWatchlist = pageKey === 'dashboard' ? snapshot.watchlist : compactRows(snapshot.watchlist);
  const focusedEvents = compactRows(snapshot.events);
  const [referenceExpanded, setReferenceExpanded] = useState(false);

  if (pageKey === 'strategy-lab') {
    return (
      <aside className="terminal-left-rail terminal-strategy-reference" data-expanded={referenceExpanded}>
        <Button
          className="terminal-strategy-reference-toggle"
          icon={<BarChartOutlined />}
          aria-expanded={referenceExpanded}
          onClick={() => setReferenceExpanded(expanded => !expanded)}
        >
          {intl.formatMessage({ id: 'terminal.strategy.marketReference' })}
        </Button>
        <div className="terminal-strategy-reference-content">
          <Panel title={intl.formatMessage({ id: 'terminal.strategy.marketReference' })} icon={<StockOutlined />}>
            <Tabs key={snapshot.code} size="small" items={[
              {
                key: 'candidates',
                label: intl.formatMessage({ id: 'terminal.strategy.referenceCandidates' }),
                children: <>
                  <MockContextBadge detailId="terminal.leftRail.source.quotes" />
                  <Table size="small" columns={compactQuoteColumns} dataSource={focusedWatchlist}
                    pagination={false} tableLayout="fixed"
                    rowClassName={record => record.symbol === activeSymbol ? 'terminal-watchlist-row-active' : ''} />
                </>,
              },
              {
                key: 'sectors',
                label: intl.formatMessage({ id: 'terminal.strategy.referenceSectors' }),
                children: <>
                  <CompactDataSourceBadge source={snapshot.sectorDataSource} />
                  <SectorTape sectors={compactRows(snapshot.sectors)} market={snapshot.code} />
                </>,
              },
            ]} />
          </Panel>
        </div>
      </aside>
    );
  }

  if (pageKey === 'ai-research' || pageKey === 'monitor') {
    return (
      <aside className="terminal-left-rail">
        <Panel title={intl.formatMessage({ id: 'terminal.panel.eventContext' })} icon={<BarChartOutlined />}
          extra={<MockContextBadge detailId="terminal.leftRail.source.events" />}>
          <Table
            size="small"
            columns={eventContextColumns}
            dataSource={focusedEvents}
            pagination={false}
            tableLayout="fixed"
          />
        </Panel>
        {pageKey === 'ai-research' ? (
          <Panel title={intl.formatMessage({ id: 'terminal.panel.marketCandidates' })} icon={<StockOutlined />}
            extra={<MockContextBadge detailId="terminal.leftRail.source.quotes" />}>
            <Table
              size="small"
              columns={compactQuoteColumns}
              dataSource={focusedWatchlist}
              pagination={false}
              tableLayout="fixed"
              rowClassName={(record) =>
                record.symbol === activeSymbol ? 'terminal-watchlist-row-active' : ''
              }
            />
          </Panel>
        ) : null}
      </aside>
    );
  }

  if (pageKey === 'backtest') {
    return (
      <aside className="terminal-left-rail">
        <Panel title={intl.formatMessage({ id: 'terminal.panel.benchmarkContext' })} icon={<BarChartOutlined />}
          extra={<MockContextBadge detailId="terminal.leftRail.source.benchmark" />}>
          <CompactMetricList metrics={[...snapshot.indices, ...snapshot.breadth.slice(0, 2)]} market={snapshot.code} />
        </Panel>
        <Panel title={intl.formatMessage({ id: 'terminal.panel.marketCandidates' })} icon={<StockOutlined />}
          extra={<MockContextBadge detailId="terminal.leftRail.source.quotes" />}>
          <Table
            size="small"
            columns={compactQuoteColumns}
            dataSource={focusedWatchlist}
            pagination={false}
            tableLayout="fixed"
            rowClassName={(record) =>
              record.symbol === activeSymbol ? 'terminal-watchlist-row-active' : ''
            }
          />
        </Panel>
      </aside>
    );
  }

  return (
    <aside className="terminal-left-rail">
      <Panel title={intl.formatMessage({ id: pageKey === 'dashboard' ? 'terminal.panel.watchlist' : compactWatchlistTitle })} icon={<StockOutlined />}
        extra={<MockContextBadge detailId="terminal.leftRail.source.quotes" />}>
        {pageKey === 'stock-research' ? (
          <p className="terminal-research-targets-note">
            {intl.formatMessage({ id: 'terminal.leftRail.researchTargets.sampleNote' })}
          </p>
        ) : null}
        <Table
          size="small"
          columns={pageKey === 'dashboard' ? quoteColumns : compactQuoteColumns}
          dataSource={focusedWatchlist}
          pagination={false}
          tableLayout="fixed"
          rowClassName={(record) =>
            record.symbol === activeSymbol ? 'terminal-watchlist-row-active' : ''
          }
          scroll={pageKey === 'dashboard' ? { x: 720 } : undefined}
        />
      </Panel>
      {shouldShowSectorPerformance(pageKey) ? (
        <Panel title={intl.formatMessage({ id: 'terminal.panel.sectorPerformance' })} icon={<BarChartOutlined />}
          extra={<CompactDataSourceBadge source={snapshot.sectorDataSource} />}>
          <SectorTape
            sectors={pageKey === 'dashboard' ? snapshot.sectors : compactRows(snapshot.sectors)}
            market={snapshot.code}
          />
        </Panel>
      ) : null}
    </aside>
  );
};

import { LineChartOutlined, RadarChartOutlined } from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { Table, Tabs, Tag, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { ProviderStatusResponse } from './apiTypes';
import { CompactDataSourceBadge, getDataSourceLabelText, getProviderBadgeColor } from './DataSourceBadge';
import { formatCurrency, formatDateTime, formatNumber, formatPercent } from './formatters';
import { ScoreStack } from './TerminalResearchWidgets';
import { MetricStrip, Panel, TerminalTableText } from './TerminalShared';
import type { DataSourceStatus, EventRow, MarketCode, MarketSnapshot, Metric, QuoteRow } from './types';

type DashboardValuationRow = {
  key: string;
  metricId: string;
  value: number;
  valueFormat: 'number' | 'percent';
  noteId: string;
};

type MarketTrendPoint = {
  value: number;
  timestamp?: string;
  source: 'historical' | 'derived';
};

const dashboardValuationRows: Record<MarketCode, DashboardValuationRow[]> = {
  US: [
    { key: 'pe', metricId: 'terminal.metric.peTtm', value: 23.4, valueFormat: 'number', noteId: 'terminal.dashboard.valuation.note.growth' },
    { key: 'pb', metricId: 'terminal.metric.pb', value: 4.8, valueFormat: 'number', noteId: 'terminal.dashboard.valuation.note.expensive' },
    { key: 'roe', metricId: 'terminal.metric.roeTtm', value: 0.184, valueFormat: 'percent', noteId: 'terminal.dashboard.valuation.note.quality' },
  ],
  HK: [
    { key: 'pe', metricId: 'terminal.metric.peTtm', value: 10.6, valueFormat: 'number', noteId: 'terminal.dashboard.valuation.note.discount' },
    { key: 'pb', metricId: 'terminal.metric.pb', value: 1.1, valueFormat: 'number', noteId: 'terminal.dashboard.valuation.note.value' },
    { key: 'roe', metricId: 'terminal.metric.roeTtm', value: 0.112, valueFormat: 'percent', noteId: 'terminal.dashboard.valuation.note.recovery' },
  ],
  CN: [
    { key: 'pe', metricId: 'terminal.metric.peTtm', value: 13.8, valueFormat: 'number', noteId: 'terminal.dashboard.valuation.note.policy' },
    { key: 'pb', metricId: 'terminal.metric.pb', value: 1.5, valueFormat: 'number', noteId: 'terminal.dashboard.valuation.note.value' },
    { key: 'roe', metricId: 'terminal.metric.roeTtm', value: 0.096, valueFormat: 'percent', noteId: 'terminal.dashboard.valuation.note.recovery' },
  ],
};

// 当前成分股与市场估值仍是前端原型数据，单独标记来源，避免被顶部真实行情标签覆盖。
const buildDashboardMockSource = (detail: string): DataSourceStatus => ({
  source: 'mock_provider',
  detail,
  fallbackActive: false,
  dataStatus: 'unavailable',
});

const buildDashboardFlowMetrics = (snapshot: MarketSnapshot): Metric[] => [
  ...snapshot.breadth,
  {
    labelId: 'terminal.metric.signalQueue',
    value: snapshot.events.length,
    tone: 'accent',
  },
];

const buildMarketTrendPoints = (snapshot: MarketSnapshot): MarketTrendPoint[] => {
  if (snapshot.chartBars.length > 0) {
    return snapshot.chartBars.map((bar) => ({
      value: bar.close,
      timestamp: bar.timestamp,
      source: 'historical',
    }));
  }

  const primaryIndex = snapshot.indices[0];
  const baseValue = primaryIndex?.value || 100;
  const change = primaryIndex?.change ?? 0;
  const changeScale = Math.max(Math.abs(change), 0.003);

  return Array.from({ length: 16 }, (_, index) => {
    const phase = index / 15;
    const wave = Math.sin(index * 0.85) * changeScale * 0.42;
    const drift = (phase - 0.5) * change * 1.8;
    return {
      value: baseValue * (1 + wave + drift),
      source: 'derived',
    };
  });
};

const MarketOverviewChart = ({
  providerStatus,
  snapshot,
}: {
  providerStatus?: ProviderStatusResponse;
  snapshot: MarketSnapshot;
}) => {
  const intl = useIntl();
  const points = buildMarketTrendPoints(snapshot);
  const chartWidth = 720;
  const chartHeight = 286;
  const plotLeft = 42;
  const plotRight = 646;
  const plotTop = 24;
  const plotBottom = 188;
  const breadthTop = 226;
  const breadthHeight = 18;
  const values = points.map((point) => point.value);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const valueRange = maxValue - minValue || 1;
  const xAt = (index: number) => plotLeft + (index / Math.max(points.length - 1, 1)) * (plotRight - plotLeft);
  const yAt = (value: number) => plotBottom - ((value - minValue) / valueRange) * (plotBottom - plotTop);
  const trendPath = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${xAt(index)} ${yAt(point.value)}`).join(' ');
  const chartPoints = points.map((point, index) => ({
    id: `market-trend-${index + 1}-${Math.round(point.value * 100)}`,
    isLatest: index === points.length - 1,
    value: point.value,
    label: point.timestamp
      ? formatDateTime(point.timestamp, { timezone: snapshot.timezone, locale: intl.locale })
      : intl.formatMessage({ id: 'terminal.dashboard.derivedPoint' }, { index: index + 1 }),
    source: intl.formatMessage({
      id: point.source === 'historical' ? 'terminal.dashboard.historicalClose' : 'terminal.dashboard.derivedClose',
    }),
    x: xAt(index),
    y: yAt(point.value),
  }));
  const yTicks = Array.from({ length: 4 }, (_, index) => {
    const ratio = index / 3;
    const value = maxValue - (maxValue - minValue) * ratio;
    return { value, y: yAt(value) };
  });
  const advancers = snapshot.breadth[0]?.value ?? 0;
  const decliners = snapshot.breadth[1]?.value ?? 0;
  const breadthWidth = plotRight - plotLeft;
  const advancersWidth = breadthWidth * advancers;
  const declinersWidth = breadthWidth * decliners;
  const unchangedWidth = Math.max(0, breadthWidth - advancersWidth - declinersWidth);
  const activeSource = providerStatus?.active_source ?? providerStatus?.source_type ?? providerStatus?.mode;
  const providerSourceLabel = getDataSourceLabelText(activeSource, intl);
  const providerDataStatus = providerStatus?.data_status ?? 'unavailable';
  const providerDataStatusLabel = intl.formatMessage({ id: `terminal.dataStatus.${providerDataStatus}` });
  const fallbackActive = providerStatus?.fallback_active ?? providerDataStatus === 'unavailable';
  const providerTooltip = [
    providerStatus?.provider_name
      ? intl.formatMessage({ id: 'terminal.providerStatus.tooltip.provider' }, { provider: providerStatus.provider_name })
      : undefined,
    intl.formatMessage({ id: 'terminal.providerStatus.tooltip.activeSource' }, { source: providerSourceLabel }),
    intl.formatMessage({ id: 'terminal.providerStatus.tooltip.dataStatus' }, { status: providerDataStatusLabel }),
    providerStatus?.fallback_reason
      ? intl.formatMessage({ id: 'terminal.providerStatus.tooltip.fallbackReason' }, { reason: providerStatus.fallback_reason })
      : undefined,
  ].filter(Boolean).join('\n');

  return (
    <div className="terminal-market-overview-chart" role="img" aria-label={intl.formatMessage({ id: 'terminal.dashboard.marketOverviewChartAria' })}>
      <div className="terminal-market-overview-status">
        <Tooltip title={<span style={{ whiteSpace: 'pre-line' }}>{providerTooltip}</span>}>
          <Tag color={getProviderBadgeColor(providerStatus)}>
            {intl.formatMessage({ id: 'terminal.dataSource.provider' })}: {providerStatus?.provider_name ?? providerSourceLabel}
          </Tag>
        </Tooltip>
        <Tag color={providerDataStatus === 'realtime' ? 'green' : providerDataStatus === 'delayed' ? 'gold' : 'red'}>
          {intl.formatMessage({ id: 'terminal.metric.dataStatus' })}: {providerDataStatusLabel}
        </Tag>
        {fallbackActive ? (
          <Tag color="gold">{intl.formatMessage({ id: 'terminal.dataSource.mockFallback' })}</Tag>
        ) : null}
      </div>
      <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} role="img">
        <title>{intl.formatMessage({ id: 'terminal.dashboard.marketOverviewChartTitle' })}</title>
        {yTicks.map((tick) => (
          <g key={tick.value}>
            <line x1={plotLeft} x2={plotRight} y1={tick.y} y2={tick.y} className="terminal-chart-grid-line" />
            <text x={plotRight + 8} y={tick.y + 4} className="terminal-chart-axis-label">
              {formatNumber(tick.value, { maximumFractionDigits: 0 }, intl.locale)}
            </text>
          </g>
        ))}
        <text x={plotRight + 8} y={plotTop - 8} className="terminal-chart-axis-label">
          {intl.formatMessage({ id: 'terminal.dashboard.priceYAxis' })}
        </text>
        <line x1={plotLeft} x2={plotRight} y1={plotBottom} y2={plotBottom} className="terminal-chart-axis-line" />
        <line x1={plotRight} x2={plotRight} y1={plotTop} y2={breadthTop + breadthHeight} className="terminal-chart-axis-line" />
        <path d={trendPath} fill="none" stroke="var(--aqt-accent)" strokeWidth="2" />
        {chartPoints.map((point) => (
          <g key={point.id}>
            <circle cx={point.x} cy={point.y} r="2.2" fill="var(--aqt-accent)" opacity={point.isLatest ? 1 : 0.32} />
            <circle cx={point.x} cy={point.y} r="9" fill="transparent">
              <title>
                {intl.formatMessage(
                  { id: 'terminal.dashboard.pointTooltip' },
                  {
                    date: point.label,
                    value: formatNumber(point.value, { maximumFractionDigits: 2 }, intl.locale),
                    source: point.source,
                  },
                )}
              </title>
            </circle>
          </g>
        ))}
        <text x={plotLeft} y={chartHeight - 72} className="terminal-chart-axis-label">
          {intl.formatMessage({ id: 'terminal.dashboard.marketBreadthStack' })}
        </text>
        <rect x={plotLeft} y={breadthTop} width={advancersWidth} height={breadthHeight} fill="var(--aqt-positive)" opacity="0.82" />
        <rect x={plotLeft + advancersWidth} y={breadthTop} width={declinersWidth} height={breadthHeight} fill="var(--aqt-negative)" opacity="0.82" />
        <rect x={plotLeft + advancersWidth + declinersWidth} y={breadthTop} width={unchangedWidth} height={breadthHeight} fill="var(--aqt-text-3)" opacity="0.38" />
        <text x={plotLeft} y={chartHeight - 18} className="terminal-chart-axis-label">
          {intl.formatMessage({ id: 'terminal.dashboard.chartStart' })}
        </text>
        <text x={plotRight} y={chartHeight - 18} textAnchor="end" className="terminal-chart-axis-label">
          {intl.formatMessage({ id: 'terminal.dashboard.chartNow' })}
        </text>
      </svg>
      <div className="terminal-market-overview-legend">
        <TerminalTableText>{snapshot.indices[0] ? intl.formatMessage({ id: snapshot.indices[0].labelId }) : snapshot.benchmark}</TerminalTableText>
        <span className="terminal-positive">{intl.formatMessage({ id: 'terminal.dashboard.advancers' })}</span>
        <span className="terminal-negative">{intl.formatMessage({ id: 'terminal.dashboard.decliners' })}</span>
        <span>{intl.formatMessage({ id: 'terminal.dashboard.unchanged' })}</span>
      </div>
      <p className="terminal-data-footnote">
        {intl.formatMessage({ id: 'terminal.dashboard.marketOverviewChartNote' }, { benchmark: snapshot.benchmark })}
      </p>
    </div>
  );
};

const useActiveQuoteColumns = (): ColumnsType<QuoteRow> => {
  const intl = useIntl();

  return [
    {
      title: intl.formatMessage({ id: 'terminal.table.symbol' }),
      dataIndex: 'symbol',
      width: 112,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.change' }),
      dataIndex: 'changePercent',
      width: 96,
      align: 'right',
      render: (value: number) => (
        <span className={value < 0 ? 'terminal-negative' : 'terminal-positive'}>
          {formatPercent(value, {}, intl.locale)}
        </span>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.volume' }),
      dataIndex: 'volume',
      width: 108,
      align: 'right',
      render: (value: number) => formatNumber(value, { notation: 'compact' }, intl.locale),
    },
  ];
};

const useValuationColumns = (market: MarketCode): ColumnsType<DashboardValuationRow> => {
  const intl = useIntl();

  return [
    {
      title: intl.formatMessage({ id: 'terminal.strategy.field' }),
      dataIndex: 'metricId',
      width: 180,
      render: (value: string) => intl.formatMessage({ id: value }),
    },
    {
      title: intl.formatMessage({ id: 'terminal.strategy.value' }),
      dataIndex: 'value',
      width: 120,
      align: 'right',
      render: (value: number, row) =>
        row.valueFormat === 'percent'
          ? formatPercent(value, {}, intl.locale)
          : formatNumber(value, {}, intl.locale),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.summary' }),
      dataIndex: 'noteId',
      width: 260,
      render: (value: string) => intl.formatMessage({ id: value }, { market }),
    },
  ];
};

export const DashboardContent = ({
  providerStatus,
  snapshot,
  eventColumns,
}: {
  providerStatus?: ProviderStatusResponse;
  snapshot: MarketSnapshot;
  eventColumns: ColumnsType<EventRow>;
}) => {
  const intl = useIntl();
  const activeQuoteColumns = useActiveQuoteColumns();
  const valuationColumns = useValuationColumns(snapshot.code);
  const activeQuotes = [...snapshot.watchlist].sort((a, b) => Math.abs(b.changePercent) - Math.abs(a.changePercent));
  const activeQuotesSource = buildDashboardMockSource(
    intl.formatMessage({ id: 'terminal.dashboard.source.activeConstituents' }),
  );
  const valuationSource = buildDashboardMockSource(
    intl.formatMessage({ id: 'terminal.dashboard.source.marketValuation' }),
  );

  return (
    <Tabs
      className="terminal-dashboard-workspace"
      size="small"
      items={[
        {
          key: 'overview',
          label: intl.formatMessage({ id: 'terminal.tab.marketOverview' }),
          children: (
            <div className="terminal-dashboard-primary-row">
                <Panel className="terminal-dashboard-chart-panel" title={intl.formatMessage({ id: 'terminal.panel.priceMarket' })} icon={<LineChartOutlined />}>
                  <MarketOverviewChart providerStatus={providerStatus} snapshot={snapshot} />
                </Panel>
                <Panel
                  className="terminal-dashboard-breadth-panel"
                  title={intl.formatMessage({ id: 'terminal.panel.marketBreadth' })}
                  icon={<RadarChartOutlined />}
                  extra={<CompactDataSourceBadge source={snapshot.breadthDataSource} />}
                >
                  <MetricStrip metrics={snapshot.breadth} market={snapshot.code} />
                </Panel>
            </div>
          ),
        },
        {
          key: 'fundamentals',
          label: intl.formatMessage({ id: 'terminal.tab.fundamentals' }),
          children: (
            <div className="terminal-dashboard-detail-row">
                <Panel title={intl.formatMessage({ id: 'terminal.panel.marketStructure' })} icon={<RadarChartOutlined />}>
                  <MetricStrip metrics={buildDashboardFlowMetrics(snapshot)} market={snapshot.code} />
                </Panel>
                <Panel
                  title={intl.formatMessage({ id: 'terminal.panel.activeConstituents' })}
                  icon={<LineChartOutlined />}
                  extra={<CompactDataSourceBadge source={activeQuotesSource} />}
                >
                  <Table
                    size="small"
                    columns={activeQuoteColumns}
                    dataSource={activeQuotes}
                    pagination={false}
                    scroll={{ x: 316 }}
                  />
                </Panel>
            </div>
          ),
        },
        {
          key: 'valuation',
          label: intl.formatMessage({ id: 'terminal.tab.valuation' }),
          children: (
            <Panel
              title={intl.formatMessage({ id: 'terminal.panel.marketValuation' })}
              icon={<RadarChartOutlined />}
              extra={<CompactDataSourceBadge source={valuationSource} />}
            >
              <Table
                size="small"
                columns={valuationColumns}
                dataSource={dashboardValuationRows[snapshot.code]}
                pagination={false}
                scroll={{ x: 560 }}
              />
              <p className="terminal-muted">
                {intl.formatMessage(
                  { id: 'terminal.dashboard.valuation.mockNote' },
                  { currency: formatCurrency(1, snapshot.code).replace(/[0-9.,\s]/g, '') },
                )}
              </p>
            </Panel>
          ),
        },
        {
          key: 'events',
          label: intl.formatMessage({ id: 'terminal.tab.newsEvents' }),
          children: <Table size="small" columns={eventColumns} dataSource={snapshot.events} pagination={false} scroll={{ x: 836 }} />,
        },
        { key: 'quant', label: intl.formatMessage({ id: 'terminal.tab.quant' }), children: <ScoreStack /> },
      ]}
    />
  );
};

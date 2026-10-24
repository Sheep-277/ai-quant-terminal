import { LineChartOutlined, RadarChartOutlined } from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { Empty, Table, Tabs, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { ReactNode } from 'react';
import { CompactDataSourceBadge, DataSourceBadge } from './DataSourceBadge';
import { StockKLineMockChart } from './StockKLineMockChart';
import { StockMetricStrip } from './StockMetricStrip';
import { TerminalTableText } from './TerminalShared';
import type {
  EventRow,
  MarketSnapshot,
  Metric,
  StockQuantSignal,
  StockResearchSnapshot,
} from './types';

const signalSeverityColorMap: Record<StockQuantSignal['severity'], string> = {
  info: 'blue',
  warning: 'gold',
  critical: 'red',
};

const Panel = ({
  title,
  icon,
  extra,
  children,
}: {
  title: string;
  icon?: ReactNode;
  extra?: ReactNode;
  children: ReactNode;
}) => (
  <section className="terminal-panel">
    <div className="terminal-panel-header">
      <h2>
        {icon}
        <TerminalTableText>{title}</TerminalTableText>
      </h2>
      {extra}
    </div>
    {children}
  </section>
);

const QuantSection = ({ title, extra, children }: { title: string; extra: ReactNode; children: ReactNode }) => (
  <section className="terminal-quant-section">
    <div className="terminal-quant-section-header">
      <h2 className="terminal-quant-section-heading"><TerminalTableText>{title}</TerminalTableText></h2>
      <div className="terminal-quant-section-source">{extra}</div>
    </div>
    {children}
  </section>
);

const fundamentalStatusColorMap: Record<string, string> = {
  complete: 'blue',
  partial: 'gold',
  mock: 'default',
};

const factorStatusColorMap: Record<string, string> = {
  complete: 'blue',
  partial: 'gold',
  computed: 'purple',
};

const signalStatusColorMap: Record<string, string> = {
  complete: 'blue',
  computed: 'purple',
};

const getFundamentalStatusText = (
  intl: ReturnType<typeof useIntl>,
  stock: StockResearchSnapshot,
): string => {
  const { completeness, source, missingSections } = stock.fundamentalDataStatus;
  if (source === 'database' && completeness === 'complete') {
    return intl.formatMessage({ id: 'terminal.fundamentalDataStatus.databaseComplete' });
  }
  if (source === 'database' && completeness === 'partial') {
    return intl.formatMessage(
      { id: 'terminal.fundamentalDataStatus.databasePartial' },
      { count: missingSections.length },
    );
  }
  return intl.formatMessage({ id: 'terminal.fundamentalDataStatus.mock' });
};

const buildFundamentalStatusTag = (
  intl: ReturnType<typeof useIntl>,
  stock: StockResearchSnapshot,
) => (
  <Tag color={fundamentalStatusColorMap[stock.fundamentalDataStatus.completeness] ?? 'default'}>
    {getFundamentalStatusText(intl, stock)}
  </Tag>
);

const getFactorStatusText = (
  intl: ReturnType<typeof useIntl>,
  stock: StockResearchSnapshot,
): string => {
  const { completeness, source, missingFactors } = stock.factorDataStatus;
  if (source === 'database' && completeness === 'complete') {
    return intl.formatMessage({ id: 'terminal.factorDataStatus.databaseComplete' });
  }
  if (source === 'database' && completeness === 'partial') {
    return intl.formatMessage(
      { id: 'terminal.factorDataStatus.databasePartial' },
      { count: missingFactors.length },
    );
  }
  return intl.formatMessage({ id: 'terminal.factorDataStatus.computed' });
};

const buildFactorStatusTag = (
  intl: ReturnType<typeof useIntl>,
  stock: StockResearchSnapshot,
) => (
  <Tag color={factorStatusColorMap[stock.factorDataStatus.completeness] ?? 'default'}>
    {getFactorStatusText(intl, stock)}
  </Tag>
);

const getSignalStatusText = (
  intl: ReturnType<typeof useIntl>,
  stock: StockResearchSnapshot,
): string => {
  const { source, signalCount } = stock.signalDataStatus;
  if (source === 'database') {
    return intl.formatMessage({ id: 'terminal.signalDataStatus.database' }, { count: signalCount });
  }
  return intl.formatMessage({ id: 'terminal.signalDataStatus.computed' }, { count: signalCount });
};

const buildSignalStatusTag = (
  intl: ReturnType<typeof useIntl>,
  stock: StockResearchSnapshot,
) => (
  <Tag color={signalStatusColorMap[stock.signalDataStatus.completeness] ?? 'default'}>
    {getSignalStatusText(intl, stock)}
  </Tag>
);

const buildStockQuoteMetrics = (stock: StockResearchSnapshot): Metric[] => {
  // 报价状态独立于 K 线；明确标注的回退样例仍保留展示，不冒充真实报价。
  const dataSource: Metric['dataSource'] = stock.quoteDataSource.fallbackActive ? undefined : {
    source: stock.quoteDataSource.source,
    status: stock.quoteDataSource.dataStatus,
    timestamp: stock.quote.timestamp,
  };
  return [
    {
      labelId: 'terminal.table.lastPrice',
      value: stock.quote.price,
      valueFormat: 'currency',
      change: stock.quote.changePercent,
      changeFormat: 'percent',
      tone: stock.direction,
      dataSource,
    },
    {
      labelId: 'terminal.table.volume',
      value: stock.quote.volume,
      tone: 'neutral',
      dataSource,
    },
    {
      labelId: 'terminal.metric.turnover',
      value: stock.quote.turnover,
      valueFormat: 'currency',
      tone: 'neutral',
      dataSource,
    },
  ];
};

export const StockResearchContent = ({
  snapshot,
  stockResearch,
  requestedSymbol,
  eventColumns,
}: {
  snapshot: MarketSnapshot;
  stockResearch: StockResearchSnapshot;
  requestedSymbol?: string;
  eventColumns: ColumnsType<EventRow>;
}) => {
  const intl = useIntl();
  // 身份不匹配时不渲染分析正文；保留外层搜索入口，等待匹配的数据恢复展示。
  if (stockResearch.market !== snapshot.code
    || (requestedSymbol !== undefined && stockResearch.symbol !== requestedSymbol)) {
    return (
      <section className="terminal-panel" role="status">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={intl.formatMessage({ id: 'terminal.stockResearch.targetMismatchWithheld' }, {
            requestedMarket: snapshot.code,
            requestedSymbol: requestedSymbol ?? intl.formatMessage({ id: 'terminal.stockSelector.defaultTarget' }),
            actualMarket: stockResearch.market,
            actualSymbol: stockResearch.symbol,
          })}
        />
      </section>
    );
  }
  const dataStatusLabel = intl.formatMessage({ id: `terminal.dataStatus.${stockResearch.dataStatus}` });
  const metricGroupMap = Object.fromEntries(stockResearch.metricGroups.map((group) => [group.key, group]));
  // 整组缺失与单个指标不可用分开显示，不用零值或上一标的指标填补。
  const renderMetricGroup = (key: string): ReactNode => {
    const metrics = metricGroupMap[key]?.metrics ?? [];
    return metrics.length > 0
      ? <StockMetricStrip metrics={metrics} market={stockResearch.market} />
      : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={intl.formatMessage({ id: 'terminal.stockResearch.emptyMetrics' })} />;
  };
  const quantSignalColumns: ColumnsType<StockQuantSignal> = [
    {
      title: intl.formatMessage({ id: 'terminal.table.event' }),
      dataIndex: 'title',
      key: 'title',
      width: 260,
      render: (value: string) => <TerminalTableText>{value}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.severity' }),
      dataIndex: 'severity',
      key: 'severity',
      width: 88,
      render: (value: StockQuantSignal['severity']) => (
        <Tag color={signalSeverityColorMap[value]}>
          {intl.formatMessage({ id: `terminal.monitor.severity.${value}` })}
        </Tag>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.score' }),
      dataIndex: 'score',
      key: 'score',
      width: 88,
      align: 'right',
      render: (value: number) => <TerminalTableText>{value.toFixed(2)}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.evidence' }),
      dataIndex: 'evidence',
      key: 'evidence',
      width: 360,
      render: (items: string[]) => <TerminalTableText>{items.join(' / ')}</TerminalTableText>,
    },
  ];

  return (
    <div className="terminal-stock-workspace">
      <Tabs
        size="small"
        items={[
        {
          key: 'overview',
          label: intl.formatMessage({ id: 'terminal.tab.overview' }),
          children: (
            <div className="terminal-stock-overview">
              <div className="terminal-stock-primary-row">
                <Panel
                  title={`${stockResearch.symbol} / ${stockResearch.name}`}
                  icon={<LineChartOutlined />}
                  extra={
                    <>
                      <DataSourceBadge labelId="terminal.dataSource.marketData" source={stockResearch.quoteDataSource} />
                      <DataSourceBadge labelId="terminal.dataSource.kline" source={stockResearch.klineDataSource} />
                      <Tag color={stockResearch.dataStatus === 'realtime' ? 'blue' : 'gold'}>
                        {dataStatusLabel}
                      </Tag>
                    </>
                  }
                >
                  <StockMetricStrip metrics={buildStockQuoteMetrics(stockResearch)} market={stockResearch.market}>
                    <div className="terminal-metric">
                      <span>{intl.formatMessage({ id: 'terminal.metric.dataStatus' })}</span>
                      <strong title={dataStatusLabel}>{dataStatusLabel}</strong>
                    </div>
                  </StockMetricStrip>
                  {/* 切换研究对象时清空图表交互状态，同一对象刷新行情时保留视图。 */}
                  <StockKLineMockChart key={`${stockResearch.market}:${stockResearch.symbol}:${stockResearch.kline.interval}`} bars={stockResearch.kline.bars} dataSource={stockResearch.klineDataSource} timezone={stockResearch.timezone} />
                </Panel>
                <Panel
                  title={intl.formatMessage({ id: 'terminal.panel.aiQuant' })}
                  icon={<RadarChartOutlined />}
                  extra={<CompactDataSourceBadge source={stockResearch.summaryDataSource} />}
                >
                  <div className="terminal-ai-brief terminal-stock-analysis">
                    <div className="terminal-stock-summary">
                      <TerminalTableText>
                        {stockResearch.exchange} / {stockResearch.sector}
                      </TerminalTableText>
                      {stockResearch.summaryPoints.map((point) => (
                        <p key={point} title={point}>{point}</p>
                      ))}
                    </div>
              {stockResearch.riskFlags.length > 0 ? (
                      <section className="terminal-stock-risks" aria-label={intl.formatMessage({ id: 'terminal.stockResearch.riskTitle' })}>
                        <h3 className="terminal-quant-section-title">
                          {intl.formatMessage({ id: 'terminal.stockResearch.riskTitle' })}
                        </h3>
                        <p>{intl.formatMessage({ id: 'terminal.stockResearch.riskNote' })}</p>
                        <ul className="terminal-risk-list" style={{ listStyle: 'none', margin: 0, padding: 0 }}>
                          {stockResearch.riskFlags.map((flag) => (
                            <li className="terminal-risk-item" key={flag}>
                              <TerminalTableText>{flag}</TerminalTableText>
                            </li>
                          ))}
                        </ul>
                      </section>
                    ) : null}
                  </div>
                </Panel>
              </div>
            </div>
          ),
        },
        {
          key: 'fundamentals',
          label: intl.formatMessage({ id: 'terminal.tab.fundamentals' }),
          children: (
            <QuantSection
              title={intl.formatMessage({ id: 'terminal.tab.fundamentals' })}
              extra={buildFundamentalStatusTag(intl, stockResearch)}
            >
              {renderMetricGroup('profitability')}
            </QuantSection>
          ),
        },
        {
          key: 'valuation',
          label: intl.formatMessage({ id: 'terminal.tab.valuation' }),
          children: (
            <QuantSection
              title={intl.formatMessage({ id: 'terminal.tab.valuation' })}
              extra={buildFundamentalStatusTag(intl, stockResearch)}
            >
              {renderMetricGroup('valuation')}
            </QuantSection>
          ),
        },
        {
          key: 'events',
          label: intl.formatMessage({ id: 'terminal.tab.newsEvents' }),
          children: (
            <QuantSection
              title={intl.formatMessage({ id: 'terminal.stockResearch.marketEvents' })}
              extra={<Tag>{intl.formatMessage({ id: snapshot.labelId })} / {snapshot.code}</Tag>}
            >
              <p className="terminal-stock-event-scope">
                {intl.formatMessage(
                  { id: 'terminal.stockResearch.marketEventsScope' },
                  { market: intl.formatMessage({ id: snapshot.labelId }), symbol: stockResearch.symbol },
                )}
              </p>
              <Table
                size="small"
                columns={eventColumns}
                dataSource={snapshot.events}
                locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={intl.formatMessage(
                  { id: 'terminal.stockResearch.emptyMarketEvents' },
                  { market: intl.formatMessage({ id: snapshot.labelId }) },
                )} /> }}
                pagination={false}
                scroll={{ x: 836 }}
              />
            </QuantSection>
          ),
        },
        {
          key: 'quant',
          label: intl.formatMessage({ id: 'terminal.tab.quant' }),
          children: (
            <div className="terminal-stock-quant-workspace">
              <div className="terminal-stock-factor-row">
              <QuantSection title={intl.formatMessage({ id: 'terminal.quant.factorSnapshot' })} extra={buildFactorStatusTag(intl, stockResearch)}>
                {renderMetricGroup('factors')}
              </QuantSection>
              <QuantSection title={intl.formatMessage({ id: 'terminal.quant.technicalIndicators' })} extra={<CompactDataSourceBadge source={stockResearch.technicalDataSource} />}>
                {renderMetricGroup('technical')}
              </QuantSection>
              </div>
              <QuantSection title={intl.formatMessage({ id: 'terminal.quant.quantSignals' })} extra={buildSignalStatusTag(intl, stockResearch)}>
                <Table
                  size="small"
                  columns={quantSignalColumns}
                  dataSource={stockResearch.quantSignals}
                  locale={{
                    emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={intl.formatMessage(
                      { id: 'terminal.stockResearch.emptySignals' },
                      { symbol: stockResearch.symbol },
                    )} />,
                  }}
                  pagination={false}
                  scroll={{ x: 796 }}
                />
              </QuantSection>
              <QuantSection title={intl.formatMessage({ id: 'terminal.quant.cashFlowQuality' })} extra={buildFundamentalStatusTag(intl, stockResearch)}>
                {renderMetricGroup('cash-flow')}
              </QuantSection>
            </div>
          ),
        },
        ]}
      />
    </div>
  );
};

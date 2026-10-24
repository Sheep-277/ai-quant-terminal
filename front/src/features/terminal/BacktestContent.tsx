import { BarChartOutlined, HistoryOutlined, LineChartOutlined } from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { Empty, Table, Tabs, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { ReactNode } from 'react';
import type { BacktestTaskCreateResponse } from './apiTypes';
import { toBacktestSnapshot } from './apiAdapters';
import { getDataSourceLabelText } from './DataSourceBadge';
import { formatCurrency, formatDateTime, formatNumber, formatPercent } from './formatters';
import { GlossaryTerm } from './glossary';
import { StockMetricStrip } from './StockMetricStrip';
import { TerminalTableText } from './TerminalShared';
import { terminalTheme } from './theme';
import type { BacktestSnapshot, BacktestTrade } from './types';
import { useBacktestByPollUrl } from './useBacktestResult';
import { BacktestPollError } from '@/services/terminal/backtest';

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
        {title}
      </h2>
      {extra}
    </div>
    {children}
  </section>
);

const buildEquityCurvePoints = (backtest: BacktestSnapshot) => {
  if (backtest.equityCurve.length === 0) return { strategy: '', benchmark: '' };
  const chartWidth = 720;
  const chartTop = 28;
  const chartBottom = 220;
  const values = backtest.equityCurve.flatMap((point) => [point.equity, point.benchmarkEquity]);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const valueRange = maxValue - minValue || 1;
  const xAt = (index: number) => (backtest.equityCurve.length <= 1 ? chartWidth / 2 : (index / (backtest.equityCurve.length - 1)) * chartWidth);
  const yAt = (value: number) => chartBottom - ((value - minValue) / valueRange) * (chartBottom - chartTop);

  return {
    strategy: backtest.equityCurve.map((point, index) => `${xAt(index)},${yAt(point.equity)}`).join(' '),
    benchmark: backtest.equityCurve.map((point, index) => `${xAt(index)},${yAt(point.benchmarkEquity)}`).join(' '),
  };
};

const useTradeColumns = (backtest: BacktestSnapshot): ColumnsType<BacktestTrade> => {
  const intl = useIntl();

  return [
    {
      title: intl.formatMessage({ id: 'terminal.table.time' }),
      dataIndex: 'timestamp',
      width: 170,
      render: (value: string) => (
        <TerminalTableText code>
          {formatDateTime(value, { timezone: backtest.timezone, locale: intl.locale })}
        </TerminalTableText>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.symbol' }),
      dataIndex: 'symbol',
      width: 116,
      render: (value: string) => <TerminalTableText code>{value}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.backtest.side' }),
      dataIndex: 'side',
      width: 76,
      render: (value: string) => (
        <Tag color={value === 'BUY' ? 'red' : 'green'}>
          {intl.formatMessage({ id: `terminal.backtest.side.${value.toLowerCase()}` })}
        </Tag>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.backtest.quantity' }),
      dataIndex: 'quantity',
      width: 96,
      align: 'right',
      render: (value: number) => <TerminalTableText>{formatNumber(value, {}, intl.locale)}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.backtest.price' }),
      dataIndex: 'price',
      width: 110,
      align: 'right',
      render: (value: number) => <TerminalTableText>{formatCurrency(value, backtest.market)}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.backtest.cost' }),
      width: 130,
      align: 'right',
      render: (_, row) => (
        <TerminalTableText>{formatCurrency(row.fee + row.slippage, backtest.market)}</TerminalTableText>
      ),
    },
  ];
};

const getBacktestTaskResultMessageId = (error: unknown) => {
  if (error instanceof BacktestPollError) {
    if (error.code === 'backtest_database_reads_disabled') {
      return 'terminal.backtest.taskResult.databaseReadsDisabled';
    }
    if (error.code === 'backtest_result_not_found') {
      return 'terminal.backtest.taskResult.notFound';
    }
    if (error.code === 'invalid_backtest_poll_url') {
      return 'terminal.backtest.taskResult.invalidPollUrl';
    }
  }

  return 'terminal.backtest.taskResult.requestFailed';
};

const getBacktestMetricValue = (backtest: BacktestSnapshot, labelId: string) =>
  backtest.performanceMetrics.find((metric) => metric.labelId === labelId)?.value;

const isBacktestFallbackAssumption = (assumption: string) =>
  assumption.includes('数据库回测结果读取失败') ||
  assumption.includes('真实历史行情读取失败') ||
  assumption.toLowerCase().includes('database backtest read failed') ||
  assumption.toLowerCase().includes('historical market data read failed');

const getBacktestDataModeColor = (dataMode: BacktestSnapshot['dataMode']) =>
  dataMode === 'historical' ? 'green' : 'gold';

const getBacktestTaskFallbackReason = (receipt: BacktestTaskCreateResponse) =>
  receipt.fallback_active && receipt.fallback_reason ? receipt.fallback_reason : null;

const formatBacktestPercentMetric = (
  backtest: BacktestSnapshot,
  labelId: string,
  locale: string,
) => {
  const value = getBacktestMetricValue(backtest, labelId);
  return typeof value === 'number' ? formatPercent(value, {}, locale) : '-';
};

const formatBacktestNumberMetric = (
  backtest: BacktestSnapshot,
  labelId: string,
  locale: string,
) => {
  const value = getBacktestMetricValue(backtest, labelId);
  return typeof value === 'number' ? formatNumber(value, { maximumFractionDigits: 2 }, locale) : '-';
};

const BacktestTaskReceiptPanel = ({
  receipt,
}: {
  receipt: BacktestTaskCreateResponse;
}) => {
  const intl = useIntl();
  const fallbackReason = getBacktestTaskFallbackReason(receipt);
  const requestedDataModeLabel = getDataSourceLabelText(receipt.data_mode, intl);
  const resultDataModeLabel = receipt.result_data_mode
    ? getDataSourceLabelText(receipt.result_data_mode, intl)
    : intl.formatMessage({ id: 'terminal.dataSource.unknown' });
  const pollResultQuery = useBacktestByPollUrl({
    pollUrl: receipt.poll_url,
    enabled: !fallbackReason && receipt.poll_url.startsWith('/api/v1/backtests/'),
  });
  const polledBacktest = pollResultQuery.data ? toBacktestSnapshot(pollResultQuery.data) : undefined;
  const resultStatusColor = fallbackReason ? 'gold' : polledBacktest ? 'green' : pollResultQuery.isFetching ? 'blue' : pollResultQuery.isError ? 'gold' : 'orange';
  const resultStatusText = polledBacktest
    ? intl.formatMessage({ id: 'terminal.backtest.taskResult.loaded' })
    : fallbackReason
      ? fallbackReason
      : pollResultQuery.isFetching
      ? intl.formatMessage({ id: 'terminal.backtest.taskResult.loading' })
      : pollResultQuery.isError
        ? intl.formatMessage({ id: getBacktestTaskResultMessageId(pollResultQuery.error) })
        : intl.formatMessage({ id: 'terminal.backtest.taskResult.unavailable' });

  return (
    <Panel
      title={intl.formatMessage({ id: 'terminal.backtest.taskReceipt' })}
      icon={<HistoryOutlined />}
      extra={
        <>
          {fallbackReason ? <Tag color="gold">{intl.formatMessage({ id: 'terminal.providerStatus.fallback' })}</Tag> : null}
          <Tag color="blue">{intl.formatMessage({ id: `terminal.backtest.status.${receipt.status}` })}</Tag>
        </>
      }
    >
      <div className="terminal-ai-brief">
        <strong>{receipt.backtest_id}</strong>
        <p>
          {intl.formatMessage(
            { id: 'terminal.backtest.taskReceiptMeta' },
            {
              pollUrl: receipt.poll_url,
              acceptedAt: formatDateTime(receipt.accepted_at, { timezone: receipt.timezone, locale: intl.locale }),
            },
          )}
        </p>
        <p className="terminal-muted">{intl.formatMessage({ id: 'terminal.backtest.taskReceiptFootnote' })}</p>
        <p className="terminal-muted">
          {intl.formatMessage(
            { id: 'terminal.backtest.taskReceiptDataMode' },
            {
              requestedMode: requestedDataModeLabel,
              resultMode: resultDataModeLabel,
            },
          )}
        </p>
        <p>
          <Tag color={resultStatusColor}>
            {intl.formatMessage({ id: 'terminal.backtest.taskResult.title' })}
          </Tag>
          {resultStatusText}
        </p>
        {polledBacktest ? (
          <p className="terminal-muted">
            {intl.formatMessage(
              { id: 'terminal.backtest.taskResult.meta' },
              {
                backtestId: polledBacktest.backtestId,
                status: intl.formatMessage({ id: `terminal.backtest.status.${polledBacktest.status}` }),
                tradeCount: formatNumber(polledBacktest.trades.length, {}, intl.locale),
                totalReturn: formatBacktestPercentMetric(polledBacktest, 'terminal.metric.totalReturn', intl.locale),
                maxDrawdown: formatBacktestPercentMetric(polledBacktest, 'terminal.metric.maxDrawdown', intl.locale),
                sharpeRatio: formatBacktestNumberMetric(polledBacktest, 'terminal.metric.sharpeRatio', intl.locale),
              },
            )}
          </p>
        ) : null}
      </div>
    </Panel>
  );
};

export const BacktestContent = ({
  backtest,
  taskReceipt,
}: {
  backtest: BacktestSnapshot;
  taskReceipt?: BacktestTaskCreateResponse;
}) => {
  const intl = useIntl();
  const linePoints = buildEquityCurvePoints(backtest);
  const tradeColumns = useTradeColumns(backtest);
  const backtestDataModeLabel = getDataSourceLabelText(backtest.dataMode, intl);

  return (
    <div className="terminal-backtest-workspace">
      <div className="terminal-backtest-primary-row">
        <div className="terminal-backtest-performance">
          <Panel
            title={intl.formatMessage({ id: 'terminal.panel.backtestPerformance' })}
            icon={<BarChartOutlined />}
            extra={<Tag color="blue">{intl.formatMessage({ id: `terminal.backtest.status.${backtest.status}` })}</Tag>}
          >
            <div className="terminal-portfolio-meta">
              <span>
                {intl.formatMessage({ id: 'terminal.backtest.dataMode' })}
                <strong>
                  <Tag color={getBacktestDataModeColor(backtest.dataMode)}>{backtestDataModeLabel}</Tag>
                </strong>
              </span>
              <span>
                {intl.formatMessage({ id: 'terminal.backtest.strategyId' })}
                <strong>{backtest.strategyId}</strong>
              </span>
              <span>
                {intl.formatMessage({ id: 'terminal.backtest.market' })}
                <strong>{backtest.market}</strong>
              </span>
              <span>
                {intl.formatMessage({ id: 'terminal.backtest.period' })}
                <strong>
                  {backtest.startDate} / {backtest.endDate}
                </strong>
              </span>
            </div>
            <StockMetricStrip metrics={backtest.performanceMetrics} market={backtest.market} />
            <div className="terminal-glossary-row">
              <GlossaryTerm term="SHARPE" />
              <GlossaryTerm term="MAX_DRAWDOWN" />
              <GlossaryTerm term="SLIPPAGE" />
            </div>
            <p className="terminal-data-footnote">
              {intl.formatMessage(
                { id: 'terminal.backtest.updatedAt' },
                {
                  benchmark: backtest.benchmark,
                  dataMode: backtestDataModeLabel,
                  timestamp: formatDateTime(backtest.timestamp, { timezone: backtest.timezone, locale: intl.locale }),
                },
              )}
            </p>
          </Panel>
        </div>
        <div className="terminal-backtest-results">
          <Panel
            title={intl.formatMessage({ id: 'terminal.panel.equityCurve' })}
            icon={<LineChartOutlined />}
            extra={<Tag>{intl.formatMessage({ id: 'terminal.panel.backtestTrades' })}: {backtest.trades.length}</Tag>}
          >
            <Tabs
              size="small"
              items={[
                {
                  key: 'equity',
                  label: intl.formatMessage({ id: 'terminal.panel.equityCurve' }),
                  children: (
                    <div className="terminal-chart">
                      {backtest.equityCurve.length > 0 ? <div className="terminal-backtest-equity-plot" role="img" aria-label={intl.formatMessage({ id: 'terminal.backtest.equityCurveAria' })}>
                      <div className="terminal-chart-grid" />
                      <svg viewBox="0 0 720 260" role="img">
                        <title>{intl.formatMessage({ id: 'terminal.panel.equityCurve' })}</title>
                        <polyline points={linePoints.strategy} fill="none" stroke={terminalTheme.positiveColor} strokeWidth="2" />
                        <polyline points={linePoints.benchmark} fill="none" stroke={terminalTheme.accentColor} strokeWidth="1.6" strokeDasharray="6 4" />
                      </svg>
                      <div className="terminal-chart-footer">
                        <span>{intl.formatMessage({ id: 'terminal.backtest.strategyEquity' })}</span>
                        <span>{intl.formatMessage({ id: 'terminal.backtest.benchmarkEquity' })}</span>
                      </div>
                      </div> : <div className="terminal-chart-empty" role="status"><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={intl.formatMessage({ id: 'terminal.backtest.emptyEquity' })} /></div>}
                    </div>
                  ),
                },
                {
                  key: 'trades',
                  label: intl.formatMessage({ id: 'terminal.panel.backtestTrades' }),
                  children: (
                    <Table size="small" columns={tradeColumns} dataSource={backtest.trades} pagination={false} rowKey="key" scroll={{ x: 698 }} />
                  ),
                },
              ]}
            />
          </Panel>
        </div>
      </div>
      <Panel title={intl.formatMessage({ id: 'terminal.panel.backtestAssumptions' })} icon={<HistoryOutlined />}>
        <div className="terminal-assumption-list">
          {backtest.assumptions.map((item) => (
            <div
              className={`terminal-assumption-item ${isBacktestFallbackAssumption(item) ? 'terminal-assumption-item-warning' : ''}`}
              key={item}
            >
              {isBacktestFallbackAssumption(item) ? (
                <Tag color="gold">{intl.formatMessage({ id: 'terminal.providerStatus.fallback' })}</Tag>
              ) : null}
              <span>{item}</span>
            </div>
          ))}
        </div>
      </Panel>
      {taskReceipt ? <BacktestTaskReceiptPanel receipt={taskReceipt} /> : null}
    </div>
  );
};

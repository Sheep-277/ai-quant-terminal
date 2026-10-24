import { CalculatorOutlined, StopOutlined } from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { Button, Empty, Input, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useId, useState, type FormEvent } from 'react';
import type { StockQuantSignalDto } from './apiTypes';
import { getDataSourceLabelText } from './DataSourceBadge';
import { formatDateTime, formatNumber, formatPercent } from './formatters';
import { getToneClass } from './mockData';
import { Panel, TerminalTableText } from './TerminalShared';
import type { MarketCode } from './types';
import { useMonitorCalculatedSignals } from './useMonitorCalculatedSignals';

const signalCodes = new Set([
  'momentum_strength',
  'momentum_weakness',
  'trend_above_ema',
  'trend_below_ema',
  'volatility_elevated',
  'composite_score_high',
  'composite_score_low',
]);

const MonitorCalculationForm = ({ market }: { market: MarketCode }) => {
  const intl = useIntl();
  const inputId = useId();
  const [symbol, setSymbol] = useState('');
  const [cancelled, setCancelled] = useState(false);
  const normalizedSymbol = symbol.trim().toUpperCase();
  const validSymbol = /^[A-Z0-9.-]{1,32}$/.test(normalizedSymbol);
  const query = useMonitorCalculatedSignals({
    market,
    symbol: normalizedSymbol,
  });
  // 即使上游错误地返回其他标的，也不把结果展示给当前选择。
  const mismatched =
    query.data &&
    (query.data.market !== market || query.data.symbol !== normalizedSymbol);
  const data = mismatched ? undefined : query.data;
  const timeout =
    query.error && 'code' in query.error && query.error.code === 'ECONNABORTED';
  const columns: ColumnsType<StockQuantSignalDto> = [
    {
      title: intl.formatMessage({ id: 'terminal.table.signal' }),
      width: 200,
      key: 'signal',
      render: (_, row) => (
        <TerminalTableText className={getToneClass(row.direction)}>
          {signalCodes.has(row.code)
            ? intl.formatMessage({
                id: `terminal.monitor.calculation.signal.${row.code}`,
              })
            : intl.formatMessage(
                { id: 'terminal.monitor.calculation.signal.other' },
                { code: row.code },
              )}
        </TerminalTableText>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.severity' }),
      dataIndex: 'severity',
      width: 90,
      render: (value: StockQuantSignalDto['severity']) => (
        <Tag
          color={
            value === 'critical' ? 'red' : value === 'warning' ? 'gold' : 'blue'
          }
        >
          {intl.formatMessage({ id: `terminal.monitor.severity.${value}` })}
        </Tag>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.monitor.calculation.score' }),
      dataIndex: 'score',
      width: 140,
      align: 'right',
      render: (value: number) =>
        formatPercent(value, { signDisplay: 'never' }, intl.locale),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.evidence' }),
      dataIndex: 'evidence',
      width: 320,
      render: (value: string[]) => (
        <TerminalTableText code>{value.join(' / ')}</TerminalTableText>
      ),
    },
  ];
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!validSymbol || query.isFetching) return;
    setCancelled(false);
    void query.refetch();
  };

  return (
    <Panel
      title={intl.formatMessage({ id: 'terminal.monitor.calculation.title' })}
      icon={<CalculatorOutlined />}
      extra={<Tag>{market}</Tag>}
      className="terminal-monitor-calculation"
    >
      <form onSubmit={submit} className="terminal-monitor-calculation-form">
        <label htmlFor={inputId}>
          {intl.formatMessage({ id: 'terminal.monitor.calculation.symbol' })}
        </label>
        <Input
          id={inputId}
          value={symbol}
          maxLength={32}
          autoComplete="off"
          placeholder={intl.formatMessage({
            id: `terminal.monitor.calculation.placeholder.${market}`,
          })}
          status={symbol && !validSymbol ? 'error' : undefined}
          onChange={(event) => {
            setSymbol(event.target.value);
            setCancelled(false);
          }}
        />
        <Button
          type="primary"
          htmlType="submit"
          icon={<CalculatorOutlined />}
          loading={query.isFetching}
          disabled={!validSymbol}
        >
          {intl.formatMessage({ id: 'terminal.monitor.calculation.run' })}
        </Button>
        <Button
          icon={<StopOutlined />}
          disabled={!query.isFetching}
          onClick={() => {
            void query.cancel();
            setCancelled(true);
          }}
        >
          {intl.formatMessage({ id: 'terminal.monitor.calculation.cancel' })}
        </Button>
      </form>
      {symbol && !validSymbol ? (
        <p role="alert" className="terminal-warning">
          {intl.formatMessage({
            id: 'terminal.monitor.calculation.invalidSymbol',
          })}
        </p>
      ) : null}
      <div
        role="status"
        aria-live="polite"
        className="terminal-monitor-calculation-status"
      >
        {intl.formatMessage({
          id: query.isFetching
            ? 'terminal.monitor.calculation.loading'
            : cancelled
              ? 'terminal.monitor.calculation.cancelled'
              : !query.isFetched
                ? 'terminal.monitor.calculation.idle'
                : 'terminal.monitor.calculation.complete',
        })}
      </div>
      {query.isError || mismatched ? (
        <p role="alert" className="terminal-warning">
          {intl.formatMessage({
            id: mismatched
              ? 'terminal.monitor.calculation.mismatch'
              : timeout
                ? 'terminal.monitor.calculation.timeout'
                : 'terminal.monitor.calculation.failed',
          })}
          {data
            ? ` ${intl.formatMessage({ id: 'terminal.monitor.calculation.stale' })}`
            : ''}
        </p>
      ) : null}
      {data ? (
        <>
          <dl className="terminal-monitor-calculation-meta">
            <div>
              <dt>
                {intl.formatMessage({
                  id: 'terminal.monitor.calculation.target',
                })}
              </dt>
              <dd>
                {data.market} / {data.symbol}
              </dd>
            </div>
            <div>
              <dt>{intl.formatMessage({ id: 'terminal.table.source' })}</dt>
              <dd>{getDataSourceLabelText(data.source, intl)}</dd>
            </div>
            <div>
              <dt>
                {intl.formatMessage({
                  id: 'terminal.monitor.calculation.dataStatus',
                })}
              </dt>
              <dd>
                {intl.formatMessage({
                  id: `terminal.dataStatus.${data.data_status}`,
                })}
              </dd>
            </div>
            <div>
              <dt>
                {intl.formatMessage({
                  id: 'terminal.monitor.calculation.asOf',
                })}
              </dt>
              <dd>
                {formatDateTime(data.timestamp, {
                  timezone: data.timezone,
                  locale: intl.locale,
                })}
              </dd>
            </div>
            <div>
              <dt>
                {intl.formatMessage({
                  id: 'terminal.monitor.calculation.bars',
                })}
              </dt>
              <dd>{formatNumber(data.bar_count, {}, intl.locale)}</dd>
            </div>
          </dl>
          <Table
            size="small"
            columns={columns}
            dataSource={data.signals}
            rowKey="code"
            pagination={false}
            scroll={{ x: 750 }}
            locale={{
              emptyText: (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description={intl.formatMessage({
                    id: 'terminal.monitor.calculation.empty',
                  })}
                />
              ),
            }}
          />
        </>
      ) : null}
      <p className="terminal-data-footnote">
        {intl.formatMessage({ id: 'terminal.monitor.calculation.boundary' })}
      </p>
    </Panel>
  );
};

// 市场改变时重置输入并卸载旧查询，防止沿用另一市场的代码。
export const MonitorCalculatedSignalsPanel = ({
  market,
}: {
  market: MarketCode;
}) => <MonitorCalculationForm key={market} market={market} />;

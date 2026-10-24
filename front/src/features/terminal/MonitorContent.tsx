import { ApiOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { Button, Empty, Segmented, Table, Tabs, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useMemo, useState, type ReactNode } from 'react';
import { formatDateTime, formatNumber, formatPercent } from './formatters';
import { getToneClass } from './mockData';
import { StockMetricStrip } from './StockMetricStrip';
import { MonitorCalculatedSignalsPanel } from './MonitorCalculatedSignalsPanel';
import { TerminalTableText } from './TerminalShared';
import type { MonitorEvent, MonitorSignal, MonitorSnapshot } from './types';

const sourceLabelMap: Record<MonitorEvent['source'], string> = {
  FAST_PATH: 'terminal.source.fastPath',
  AI_PATH: 'terminal.source.aiPath',
  RISK_ENGINE: 'terminal.source.riskEngine',
  PROVIDER: 'terminal.source.provider',
};

const severityColorMap: Record<MonitorSignal['severity'], string> = {
  info: 'blue',
  warning: 'gold',
  critical: 'red',
};

const eventSourceColorMap: Record<MonitorEvent['source'], string> = {
  FAST_PATH: 'blue',
  AI_PATH: 'purple',
  RISK_ENGINE: 'volcano',
  PROVIDER: 'gold',
};

const streamStatusColorMap: Record<
  MonitorSnapshot['stream']['status'],
  string
> = {
  connected: 'green',
  reconnecting: 'gold',
  disconnected: 'red',
};

const streamHealthToneMap: Record<MonitorSnapshot['stream']['status'], string> =
  {
    connected: 'positive',
    reconnecting: 'warning',
    disconnected: 'negative',
  };

const severityRank: Record<MonitorSignal['severity'], number> = {
  info: 1,
  warning: 2,
  critical: 3,
};

type SignalSeverityFilter = MonitorSignal['severity'] | 'all';
type EventSourceFilter = MonitorEvent['source'] | 'all';

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

const useSignalColumns = (
  monitor: MonitorSnapshot,
): ColumnsType<MonitorSignal> => {
  const intl = useIntl();

  return [
    {
      title: intl.formatMessage({ id: 'terminal.table.time' }),
      dataIndex: 'triggeredAt',
      width: 150,
      ellipsis: true,
      render: (value: string) => (
        <TerminalTableText>
          {formatDateTime(value, {
            timezone: monitor.timezone,
            locale: intl.locale,
          })}
        </TerminalTableText>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.symbol' }),
      dataIndex: 'symbol',
      width: 104,
      ellipsis: true,
      render: (value: string) => (
        <TerminalTableText code>{value}</TerminalTableText>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.signal' }),
      dataIndex: 'title',
      width: 220,
      ellipsis: true,
      render: (value: string, row) => (
        <TerminalTableText className={getToneClass(row.direction)}>
          {value}
        </TerminalTableText>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.severity' }),
      dataIndex: 'severity',
      width: 78,
      ellipsis: true,
      render: (value: MonitorSignal['severity']) => (
        <Tag color={severityColorMap[value]}>
          {intl.formatMessage({ id: `terminal.monitor.severity.${value}` })}
        </Tag>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.score' }),
      dataIndex: 'score',
      align: 'right',
      width: 78,
      ellipsis: true,
      render: (value: number) =>
        formatPercent(
          value,
          { signDisplay: 'never', maximumFractionDigits: 0 },
          intl.locale,
        ),
    },
    {
      dataIndex: 'source',
      key: 'signal-source',
      title: intl.formatMessage({ id: 'terminal.monitor.signalSource' }),
      width: 180,
      ellipsis: true,
      render: (_value: string | null | undefined, row) => (
        <TerminalTableText>
          {intl.formatMessage({ id: 'terminal.monitor.signalOriginSummary' }, {
            origin: intl.formatMessage({ id: `terminal.monitor.signalOrigin.${row.dataOrigin ?? 'unknown'}` }),
            source: row.source ?? intl.formatMessage({ id: 'terminal.monitor.signalSourceMissing' }),
          })}
        </TerminalTableText>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.evidence' }),
      dataIndex: 'evidence',
      width: 320,
      ellipsis: true,
      render: (value: string[]) => (
        <TerminalTableText code>{value.join(' / ')}</TerminalTableText>
      ),
    },
  ];
};

const useEventColumns = (
  monitor: MonitorSnapshot,
): ColumnsType<MonitorEvent> => {
  const intl = useIntl();

  return [
    {
      title: intl.formatMessage({ id: 'terminal.table.time' }),
      dataIndex: 'createdAt',
      width: 150,
      ellipsis: true,
      render: (value: string) => (
        <TerminalTableText>
          {formatDateTime(value, {
            timezone: monitor.timezone,
            locale: intl.locale,
          })}
        </TerminalTableText>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.source' }),
      dataIndex: 'source',
      width: 122,
      ellipsis: true,
      render: (value: MonitorEvent['source']) => (
        <Tag color={eventSourceColorMap[value]}>
          {intl.formatMessage({ id: sourceLabelMap[value] })}
        </Tag>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.event' }),
      dataIndex: 'title',
      width: 220,
      ellipsis: true,
      render: (value: string, row) => (
        <TerminalTableText className={getToneClass(row.impact)}>
          {value}
        </TerminalTableText>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.summary' }),
      dataIndex: 'summary',
      width: 360,
      ellipsis: true,
      render: (value: string, row) => (
        <TerminalTableText className={getToneClass(row.impact)}>
          {value}
        </TerminalTableText>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.confidence' }),
      dataIndex: 'confidence',
      align: 'right',
      width: 88,
      ellipsis: true,
      render: (value: number) =>
        formatPercent(
          value,
          { signDisplay: 'never', maximumFractionDigits: 0 },
          intl.locale,
        ),
    },
  ];
};

export const MonitorContent = ({ monitor }: { monitor: MonitorSnapshot }) => {
  const intl = useIntl();
  const [signalSeverityFilter, setSignalSeverityFilter] =
    useState<SignalSeverityFilter>('all');
  const [eventSourceFilter, setEventSourceFilter] =
    useState<EventSourceFilter>('all');
  const signalColumns = useSignalColumns(monitor);
  const eventColumns = useEventColumns(monitor);
  const hasActiveSignalFilter = signalSeverityFilter !== 'all';
  const hasActiveEventFilter = eventSourceFilter !== 'all';
  const streamHealthMessageId =
    monitor.stream.status === 'connected' &&
    monitor.stream.reconnectAttempts === 0
      ? 'terminal.monitor.health.normal'
      : `terminal.monitor.health.${monitor.stream.status}`;
  const filteredSignals = useMemo(
    () =>
      signalSeverityFilter === 'all'
        ? monitor.signals
        : monitor.signals.filter(
            (signal) => signal.severity === signalSeverityFilter,
          ),
    [monitor.signals, signalSeverityFilter],
  );
  const filteredEvents = useMemo(
    () =>
      eventSourceFilter === 'all'
        ? monitor.events
        : monitor.events.filter((event) => event.source === eventSourceFilter),
    [monitor.events, eventSourceFilter],
  );
  const signalEmptyText =
    monitor.signals.length === 0
      ? intl.formatMessage({ id: 'terminal.monitor.emptySignals' })
      : intl.formatMessage({ id: 'terminal.monitor.emptyFilteredSignals' });
  const eventEmptyText =
    monitor.events.length === 0
      ? intl.formatMessage({ id: 'terminal.monitor.emptyEvents' })
      : intl.formatMessage({ id: 'terminal.monitor.emptyFilteredEvents' });
  const severityFilterOptions = [
    {
      label: intl.formatMessage({ id: 'terminal.monitor.severity.all' }),
      value: 'all',
    },
    {
      label: intl.formatMessage({ id: 'terminal.monitor.severity.critical' }),
      value: 'critical',
    },
    {
      label: intl.formatMessage({ id: 'terminal.monitor.severity.warning' }),
      value: 'warning',
    },
    {
      label: intl.formatMessage({ id: 'terminal.monitor.severity.info' }),
      value: 'info',
    },
  ];
  const eventSourceFilterOptions = [
    {
      label: intl.formatMessage({ id: 'terminal.monitor.source.all' }),
      value: 'all',
    },
    {
      label: intl.formatMessage({ id: sourceLabelMap.FAST_PATH }),
      value: 'FAST_PATH',
    },
    {
      label: intl.formatMessage({ id: sourceLabelMap.AI_PATH }),
      value: 'AI_PATH',
    },
    {
      label: intl.formatMessage({ id: sourceLabelMap.RISK_ENGINE }),
      value: 'RISK_ENGINE',
    },
    {
      label: intl.formatMessage({ id: sourceLabelMap.PROVIDER }),
      value: 'PROVIDER',
    },
  ];
  const highestSeverity = monitor.signals.reduce<MonitorSignal['severity']>(
    (current, signal) =>
      severityRank[signal.severity] > severityRank[current]
        ? signal.severity
        : current,
    'info',
  );
  const riskSignalCount = monitor.signals.filter(
    (signal) => signal.severity !== 'info',
  ).length;
  const providerWarningCount = monitor.events.filter(
    (event) => event.source === 'PROVIDER' && event.impact === 'warning',
  ).length;
  const eventSourceSummary = eventSourceFilterOptions
    .filter((option) => option.value !== 'all')
    .map((option) => {
      const count = monitor.events.filter(
        (event) => event.source === option.value,
      ).length;
      return `${option.label} ${formatNumber(count, {}, intl.locale)}`;
    })
    .join(' / ');

  return (
    <div className="terminal-monitor-workspace">
      <MonitorCalculatedSignalsPanel market={monitor.market} />
      <Panel
        title={intl.formatMessage({ id: 'terminal.monitor.snapshotTitle' })}
        icon={<ApiOutlined />}
        extra={
          <Tag color={streamStatusColorMap[monitor.stream.status]}>
            {intl.formatMessage({
              id: `terminal.monitor.streamStatus.${monitor.stream.status}`,
            })}
          </Tag>
        }
      >
        <p className="terminal-data-footnote">
          {intl.formatMessage(
            { id: 'terminal.monitor.provenanceSummary' },
            {
              stream: intl.formatMessage({ id: `terminal.monitor.origin.${monitor.provenance?.streamSource ?? 'unknown'}` }),
              signals: intl.formatMessage({ id: `terminal.monitor.origin.${monitor.provenance?.signalSource ?? 'unknown'}` }),
              events: intl.formatMessage({ id: `terminal.monitor.origin.${monitor.provenance?.eventSource ?? 'unknown'}` }),
              heartbeat: intl.formatMessage({ id: `terminal.monitor.heartbeat.${monitor.provenance?.heartbeatBasis ?? 'unknown'}` }),
              transport: intl.formatMessage({ id: monitor.provenance?.transport === 'rest_polling' ? 'terminal.monitor.transport.restPolling' : 'terminal.monitor.origin.unknown' }),
            },
          )}
        </p>
        <div className="terminal-monitor-overview">
          <div className="terminal-monitor-connection">
            <StockMetricStrip
              metrics={monitor.streamMetrics}
              market={monitor.market}
            />
            <div
              className={`terminal-monitor-health terminal-monitor-health-${streamHealthToneMap[monitor.stream.status]}`}
            >
              <span>
                {intl.formatMessage({ id: 'terminal.monitor.healthTitle' })}
              </span>
              <strong>
                {intl.formatMessage(
                  { id: streamHealthMessageId },
                  {
                    reconnectAttempts: monitor.stream.reconnectAttempts,
                    latency: formatNumber(
                      monitor.stream.latencyMs,
                      {},
                      intl.locale,
                    ),
                    dataStatus: intl.formatMessage({
                      id: `terminal.dataStatus.${monitor.stream.dataStatus}`,
                    }),
                  },
                )}
              </strong>
            </div>
            <div className="terminal-monitor-status-strip">
              <Tag
                color={
                  monitor.stream.dataStatus === 'realtime' ? 'blue' : 'gold'
                }
              >
                {intl.formatMessage(
                  { id: 'terminal.monitor.dataStatusLabel' },
                  {
                    status: intl.formatMessage({
                      id: `terminal.dataStatus.${monitor.stream.dataStatus}`,
                    }),
                  },
                )}
              </Tag>
              <Tag color="geekblue">
                {intl.formatMessage({
                  id: 'terminal.monitor.transport.restPolling',
                })}
              </Tag>
              <Tag color="default">
                {intl.formatMessage({
                  id: 'terminal.monitor.transport.noWebSocket',
                })}
              </Tag>
            </div>
          </div>
          <div className="terminal-monitor-risk-summary">
            <div className="terminal-monitor-summary-strip">
              <div>
                <span>
                  {intl.formatMessage({
                    id: 'terminal.monitor.highestSeverity',
                  })}
                </span>
                <strong
                  className={
                    highestSeverity === 'critical'
                      ? 'terminal-negative'
                      : highestSeverity === 'warning'
                        ? 'terminal-warning'
                        : ''
                  }
                >
                  {intl.formatMessage({
                    id: `terminal.monitor.severity.${highestSeverity}`,
                  })}
                </strong>
              </div>
              <div>
                <span>
                  {intl.formatMessage({
                    id: 'terminal.monitor.riskSignalCount',
                  })}
                </span>
                <strong>
                  {formatNumber(riskSignalCount, {}, intl.locale)}
                </strong>
              </div>
              <div>
                <span>
                  {intl.formatMessage({
                    id: 'terminal.monitor.providerWarningCount',
                  })}
                </span>
                <strong
                  className={providerWarningCount > 0 ? 'terminal-warning' : ''}
                >
                  {formatNumber(providerWarningCount, {}, intl.locale)}
                </strong>
              </div>
            </div>
          </div>
        </div>
        <p className="terminal-data-footnote">
          {intl.formatMessage(
            { id: 'terminal.monitor.updatedAt' },
            {
              timestamp: formatDateTime(monitor.timestamp, {
                timezone: monitor.timezone,
                locale: intl.locale,
              }),
              heartbeat: formatDateTime(monitor.stream.lastHeartbeatAt, {
                timezone: monitor.timezone,
                locale: intl.locale,
              }),
            },
          )}
        </p>
        <p className="terminal-data-footnote">
          {intl.formatMessage(
            { id: 'terminal.monitor.eventSourceSummary' },
            { summary: eventSourceSummary },
          )}
        </p>
      </Panel>
      <div className="terminal-monitor-tables">
        <p className="terminal-data-footnote">
          {intl.formatMessage({ id: 'terminal.monitor.snapshotBoundary' })}
        </p>
        <Panel
          title={intl.formatMessage({ id: 'terminal.builder.signalSet' })}
          icon={<ThunderboltOutlined />}
          extra={
            <Tag>
              {monitor.signals.length} / {monitor.events.length}
            </Tag>
          }
        >
          <Tabs
            size="small"
            items={[
              {
                key: 'signals',
                label: intl.formatMessage({ id: 'terminal.builder.signalSet' }),
                children: (
                  <div className="terminal-stack terminal-stack-tight">
                    <div className="terminal-monitor-filter-group">
                      <Segmented
                        className="terminal-monitor-filter"
                        options={severityFilterOptions}
                        size="small"
                        value={signalSeverityFilter}
                        onChange={(value) =>
                          setSignalSeverityFilter(value as SignalSeverityFilter)
                        }
                      />
                      {hasActiveSignalFilter ? (
                        <Button
                          size="small"
                          type="link"
                          onClick={() => setSignalSeverityFilter('all')}
                        >
                          {intl.formatMessage({
                            id: 'terminal.monitor.clearFilter',
                          })}
                        </Button>
                      ) : null}
                    </div>
                    <div className="terminal-monitor-result-count">
                      {intl.formatMessage(
                        { id: 'terminal.monitor.signalResultCount' },
                        {
                          visible: filteredSignals.length,
                          total: monitor.signals.length,
                        },
                      )}
                    </div>
                    <Table
                      size="small"
                      columns={signalColumns}
                      dataSource={filteredSignals}
                      locale={{
                        emptyText: (
                          <Empty
                            image={Empty.PRESENTED_IMAGE_SIMPLE}
                            description={signalEmptyText}
                          />
                        ),
                      }}
                      pagination={false}
                      rowKey="key"
                      scroll={{ x: 1130 }}
                    />
                  </div>
                ),
              },
              {
                key: 'events',
                label: intl.formatMessage({
                  id: 'terminal.panel.liveEventStream',
                }),
                children: (
                  <div className="terminal-stack terminal-stack-tight">
                    <div className="terminal-monitor-filter-group">
                      <Segmented
                        className="terminal-monitor-filter"
                        options={eventSourceFilterOptions}
                        size="small"
                        value={eventSourceFilter}
                        onChange={(value) =>
                          setEventSourceFilter(value as EventSourceFilter)
                        }
                      />
                      {hasActiveEventFilter ? (
                        <Button
                          size="small"
                          type="link"
                          onClick={() => setEventSourceFilter('all')}
                        >
                          {intl.formatMessage({
                            id: 'terminal.monitor.clearFilter',
                          })}
                        </Button>
                      ) : null}
                    </div>
                    <div className="terminal-monitor-result-count">
                      {intl.formatMessage(
                        { id: 'terminal.monitor.eventResultCount' },
                        {
                          visible: filteredEvents.length,
                          total: monitor.events.length,
                        },
                      )}
                    </div>
                    <Table
                      size="small"
                      columns={eventColumns}
                      dataSource={filteredEvents}
                      locale={{
                        emptyText: (
                          <Empty
                            image={Empty.PRESENTED_IMAGE_SIMPLE}
                            description={eventEmptyText}
                          />
                        ),
                      }}
                      pagination={false}
                      rowClassName={(row) =>
                        row.source === 'PROVIDER' && row.impact === 'warning'
                          ? 'terminal-monitor-provider-warning-row'
                          : ''
                      }
                      rowKey="key"
                      scroll={{ x: 940 }}
                    />
                  </div>
                ),
              },
            ]}
          />
        </Panel>
      </div>
    </div>
  );
};

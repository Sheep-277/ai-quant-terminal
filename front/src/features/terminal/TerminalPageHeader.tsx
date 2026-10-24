import { HistoryOutlined, InfoCircleOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { Button, Empty, Modal, Table, Tag, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useMemo, useState } from 'react';
import type { ProviderStatusLogItem, ProviderStatusResponse } from './apiTypes';
import { getDataSourceLabelText, getProviderBadgeColor } from './DataSourceBadge';
import { formatDateTime, formatNumber } from './formatters';
import type { pageDefinitions } from './mockData';
import { TerminalTableText } from './TerminalShared';
import type { MarketSnapshot, TerminalPageKey } from './types';
import { useProviderStatusLogs } from './useProviderStatus';

type ApiStatus = {
  isError: boolean;
  isFetching: boolean;
};

type ApiStatusMap = Record<TerminalPageKey, ApiStatus>;

const ApiStatusTag = ({
  isError,
  isFetching,
}: ApiStatus) => {
  const intl = useIntl();
  const label = intl.formatMessage({
    // 查询失败不等于 Provider 已回退；重试期间优先展示当前请求状态。
    id: isFetching
      ? 'terminal.apiSyncing'
      : isError
        ? 'terminal.apiFailed'
        : 'terminal.apiSynced',
  });

  return (
    <Tag color={!isFetching && isError ? 'gold' : 'blue'} title={label}>
      <span className="terminal-page-header-tag-text">{label}</span>
    </Tag>
  );
};

const ProviderStatusTag = ({
  providerStatus,
  isError,
  isFetching,
}: {
  providerStatus?: ProviderStatusResponse;
  isError: boolean;
  isFetching: boolean;
}) => {
  const intl = useIntl();

  if (isError) {
    return (
      <Tag color="gold">
        <span className="terminal-page-header-tag-text">{intl.formatMessage({ id: 'terminal.providerStatus.error' })}</span>
      </Tag>
    );
  }

  if (!providerStatus) {
    return (
      <Tag color="default">
        <span className="terminal-page-header-tag-text">
          {intl.formatMessage({
            id: isFetching ? 'terminal.providerStatus.loading' : 'terminal.providerStatus.unknown',
          })}
        </span>
      </Tag>
    );
  }

  const labelId = providerStatus.source_type === 'demo_provider'
    ? 'terminal.providerStatus.demo'
    : providerStatus.fallback_active
    ? 'terminal.providerStatus.fallback'
    : providerStatus.mode === 'real'
      ? 'terminal.providerStatus.real'
      : 'terminal.providerStatus.mock';
  const color = getProviderBadgeColor(providerStatus);
  const missingConfiguration = providerStatus.missing_configuration?.join(', ') || '-';
  const lastLoggedAt = providerStatus.last_logged_at
    ? formatDateTime(providerStatus.last_logged_at, { locale: intl.locale })
    : '-';
  const recentLogCount = formatNumber(providerStatus.recent_log_count ?? 0, {}, intl.locale);
  const activeSource = getDataSourceLabelText(
    providerStatus.active_source ?? providerStatus.source_type ?? providerStatus.mode,
    intl,
  );
  const providerTitle = [
    intl.formatMessage(
      { id: 'terminal.providerStatus.tooltip.provider' },
      { provider: providerStatus.provider_name },
    ),
    intl.formatMessage(
      { id: 'terminal.providerStatus.tooltip.activeSource' },
      { source: activeSource },
    ),
    intl.formatMessage(
      { id: 'terminal.providerStatus.tooltip.dataStatus' },
      { status: intl.formatMessage({ id: `terminal.dataStatus.${providerStatus.data_status}` }) },
    ),
    intl.formatMessage(
      { id: 'terminal.providerStatus.tooltip.missingConfiguration' },
      { items: missingConfiguration },
    ),
    intl.formatMessage(
      { id: 'terminal.providerStatus.tooltip.lastLoggedAt' },
      { timestamp: lastLoggedAt },
    ),
    intl.formatMessage(
      { id: 'terminal.providerStatus.tooltip.recentLogCount' },
      { count: recentLogCount },
    ),
    providerStatus.fallback_reason
      ? intl.formatMessage(
          { id: 'terminal.providerStatus.tooltip.fallbackReason' },
          { reason: providerStatus.fallback_reason },
        )
      : null,
    providerStatus.next_action
      ? intl.formatMessage(
          { id: 'terminal.providerStatus.tooltip.nextAction' },
          { action: providerStatus.next_action },
        )
      : null,
  ]
    .filter(Boolean)
    .join('\n');

  return (
    <Tooltip title={<span className="terminal-page-header-provider-details">{providerTitle}</span>}>
      <Tag color={color}>
        <span className="terminal-page-header-tag-text">{intl.formatMessage({ id: labelId })}</span>
      </Tag>
    </Tooltip>
  );
};

const ProviderStatusLogModal = ({
  open,
  providerName,
  onClose,
}: {
  open: boolean;
  providerName?: string;
  onClose: () => void;
}) => {
  const intl = useIntl();
  const logsQuery = useProviderStatusLogs({
    enabled: open,
    limit: 20,
    providerName,
  });
  const columns = useMemo<ColumnsType<ProviderStatusLogItem>>(
    () => [
      {
        title: intl.formatMessage({ id: 'terminal.providerStatus.logs.checkedAt' }),
        dataIndex: 'checked_at',
        width: 180,
        ellipsis: true,
        render: (value: string) => (
          <TerminalTableText>
            {formatDateTime(value, { locale: intl.locale })}
          </TerminalTableText>
        ),
      },
      {
        title: intl.formatMessage({ id: 'terminal.providerStatus.logs.provider' }),
        dataIndex: 'provider_name',
        width: 170,
        ellipsis: true,
        render: (value: string) => <TerminalTableText code>{value}</TerminalTableText>,
      },
      {
        title: intl.formatMessage({ id: 'terminal.providerStatus.logs.mode' }),
        dataIndex: 'mode',
        width: 80,
        ellipsis: true,
        render: (value: string) => <Tag color={value === 'real' ? 'blue' : 'default'}>{value}</Tag>,
      },
      {
        title: intl.formatMessage({ id: 'terminal.providerStatus.logs.dataStatus' }),
        dataIndex: 'data_status',
        width: 104,
        ellipsis: true,
        render: (value: ProviderStatusLogItem['data_status']) => (
          <Tag color={value === 'realtime' ? 'green' : value === 'delayed' ? 'gold' : 'red'}>
            {intl.formatMessage({ id: `terminal.dataStatus.${value}` })}
          </Tag>
        ),
      },
      {
        title: intl.formatMessage({ id: 'terminal.providerStatus.logs.ready' }),
        dataIndex: 'ready',
        width: 76,
        ellipsis: true,
        render: (value: boolean) => (
          <Tag color={value ? 'green' : 'red'}>
            {intl.formatMessage({ id: value ? 'terminal.boolean.yes' : 'terminal.boolean.no' })}
          </Tag>
        ),
      },
      {
        title: intl.formatMessage({ id: 'terminal.providerStatus.logs.fallback' }),
        dataIndex: 'fallback_active',
        width: 86,
        ellipsis: true,
        render: (value: boolean) => (
          <Tag color={value ? 'gold' : 'default'}>
            {intl.formatMessage({ id: value ? 'terminal.boolean.yes' : 'terminal.boolean.no' })}
          </Tag>
        ),
      },
      {
        title: intl.formatMessage({ id: 'terminal.providerStatus.logs.reason' }),
        dataIndex: 'fallback_reason',
        width: 260,
        ellipsis: true,
        render: (value: string | null) => <TerminalTableText>{value ?? '-'}</TerminalTableText>,
      },
    ],
    [intl],
  );
  const logs = logsQuery.data?.items ?? [];
  const fallbackReason = logsQuery.data?.fallback_reason;

  return (
    <Modal
      destroyOnHidden
      footer={null}
      open={open}
      title={intl.formatMessage({ id: 'terminal.providerStatus.logs.title' })}
      width={920}
      onCancel={onClose}
    >
      {fallbackReason ? (
        <p className="terminal-data-footnote">{fallbackReason}</p>
      ) : (
        <p className="terminal-data-footnote">
          {intl.formatMessage(
            { id: 'terminal.providerStatus.logs.summary' },
            {
              count: formatNumber(logsQuery.data?.total ?? logs.length, {}, intl.locale),
              provider: providerName ?? intl.formatMessage({ id: 'terminal.monitor.source.all' }),
            },
          )}
        </p>
      )}
      <Table
        columns={columns}
        dataSource={logs}
        loading={logsQuery.isFetching}
        locale={{
          emptyText: (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={intl.formatMessage({ id: 'terminal.providerStatus.logs.empty' })}
            />
          ),
        }}
        pagination={false}
        rowKey="id"
        scroll={{ x: 980 }}
        size="small"
      />
    </Modal>
  );
};

export const TerminalPageHeader = ({
  pageKey,
  page,
  snapshot,
  providerStatus,
  providerStatusLoading,
  providerStatusError,
  apiStatusMap,
  primaryActionLoading,
  onMockDataClick,
  onPrimaryActionClick,
}: {
  pageKey: TerminalPageKey;
  page: (typeof pageDefinitions)[TerminalPageKey];
  snapshot: MarketSnapshot;
  providerStatus?: ProviderStatusResponse;
  providerStatusLoading: boolean;
  providerStatusError: boolean;
  apiStatusMap: ApiStatusMap;
  primaryActionLoading: boolean;
  onMockDataClick: () => void;
  onPrimaryActionClick: () => void;
}) => {
  const intl = useIntl();
  const [providerLogOpen, setProviderLogOpen] = useState(false);
  const marketMeta = `${intl.formatMessage({ id: snapshot.labelId })} / ${snapshot.currency} / ${snapshot.timezone}`;
  const pageTitle = intl.formatMessage({ id: page.title });
  const pageSubtitle = intl.formatMessage({ id: page.subtitle });
  const prototypeGuideLabel = intl.formatMessage({ id: 'terminal.prototypeGuide' });
  const prototypeGuideTooltip = intl.formatMessage({ id: 'terminal.prototypeGuide.tooltip' });
  const primaryActionLabel = intl.formatMessage({ id: page.primaryAction });

  return (
    <header className="terminal-page-header">
      <div className="terminal-page-header-copy">
        <TerminalTableText className="terminal-kicker">{marketMeta}</TerminalTableText>
        <h1 title={pageTitle}>{pageTitle}</h1>
        <p title={pageSubtitle}>{pageSubtitle}</p>
      </div>
      <div className="terminal-page-header-command-strip">
        <Tooltip title={prototypeGuideTooltip}>
          <Button
            className="terminal-page-header-secondary-button"
            size="small"
            icon={<InfoCircleOutlined />}
            onClick={onMockDataClick}
          >
            <TerminalTableText>{prototypeGuideLabel}</TerminalTableText>
          </Button>
        </Tooltip>
        <Tooltip title={primaryActionLabel}>
          <Button
            className="terminal-page-header-primary-button"
            size="small"
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={primaryActionLoading}
            onClick={onPrimaryActionClick}
          >
            <TerminalTableText>{primaryActionLabel}</TerminalTableText>
          </Button>
        </Tooltip>
      </div>
      {/* 状态占据独立整行，主操作不会压缩回退原因和基准名称。 */}
      <div className="terminal-page-header-status-strip">
        <ProviderStatusTag
          providerStatus={providerStatus}
          isError={providerStatusError}
          isFetching={providerStatusLoading}
        />
        <Tooltip title={intl.formatMessage({ id: 'terminal.providerStatus.logs.open' })}>
          <Button
            className="terminal-page-header-icon-button"
            size="small"
            icon={<HistoryOutlined />}
            aria-label={intl.formatMessage({ id: 'terminal.providerStatus.logs.open' })}
            onClick={() => setProviderLogOpen(true)}
          />
        </Tooltip>
        <ApiStatusTag
          isError={apiStatusMap[pageKey].isError}
          isFetching={apiStatusMap[pageKey].isFetching}
        />
        <Tag>
          <span className="terminal-page-header-tag-text">{snapshot.benchmark}</span>
        </Tag>
      </div>
      <ProviderStatusLogModal
        open={providerLogOpen}
        providerName={providerStatus?.provider_name}
        onClose={() => setProviderLogOpen(false)}
      />
    </header>
  );
};

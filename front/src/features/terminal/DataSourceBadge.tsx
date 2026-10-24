import { useIntl } from '@umijs/max';
import { Tag, Tooltip } from 'antd';
import type { ProviderStatusResponse } from './apiTypes';
import type { DataSourceStatus, StockMarketDataSourceStatus } from './types';

const sourceLabelIdMap: Record<string, string> = {
  database: 'terminal.dataSource.database',
  provider: 'terminal.dataSource.provider',
  demo_provider: 'terminal.dataSource.demoProvider',
  yahoo_finance: 'terminal.dataSource.yahooFinance',
  real_http_configured: 'terminal.dataSource.realHttpConfigured',
  real_placeholder: 'terminal.dataSource.realPlaceholder',
  mock_provider: 'terminal.dataSource.mockProvider',
  computed: 'terminal.dataSource.quantPipeline',
  quant_pipeline: 'terminal.dataSource.quantPipeline',
  mock: 'terminal.dataSource.mockProvider',
  mock_fallback: 'terminal.dataSource.mockFallback',
  paper: 'terminal.dataSource.paper',
  historical: 'terminal.dataSource.historical',
};

const sourceColorMap: Record<string, string> = {
  database: 'blue',
  provider: 'cyan',
  demo_provider: 'geekblue',
  yahoo_finance: 'cyan',
  real_http_configured: 'cyan',
  real_placeholder: 'gold',
  mock_provider: 'default',
  mock_fallback: 'gold',
  computed: 'purple',
  quant_pipeline: 'purple',
  paper: 'geekblue',
  historical: 'volcano',
};

export const getDataSourceLabelText = (
  source: string | undefined,
  intl: ReturnType<typeof useIntl>,
) => {
  if (!source) {
    return intl.formatMessage({ id: 'terminal.dataSource.unknown' });
  }

  const labelId = sourceLabelIdMap[source];
  return labelId ? intl.formatMessage({ id: labelId }) : source;
};

export const getMarketDataSourceLabelText = (
  source: StockMarketDataSourceStatus | undefined,
  intl: ReturnType<typeof useIntl>,
) => {
  if (!source) {
    return intl.formatMessage({ id: 'terminal.dataSource.unknown' });
  }

  if (source.fallbackActive) {
    return intl.formatMessage({ id: 'terminal.dataSource.mockFallback' });
  }

  const label = getDataSourceLabelText(source.source, intl);
  // 数据来源不等于数据可用；未启用回退时也要直接展示不可用状态。
  return source.dataStatus === 'unavailable'
    ? `${label} · ${intl.formatMessage({ id: 'terminal.dataStatus.unavailable' })}`
    : label;
};

export const getDataSourceColor = (source: string | undefined, fallbackActive = false): string => {
  if (fallbackActive) {
    return sourceColorMap.mock_fallback;
  }

  return source ? sourceColorMap[source] ?? 'default' : 'default';
};

export const getMarketDataSourceTooltipText = (
  source: StockMarketDataSourceStatus,
  intl: ReturnType<typeof useIntl>,
) => {
  const sourceLabel = getDataSourceLabelText(source.source, intl);
  const statusLabel = intl.formatMessage({ id: `terminal.dataStatus.${source.dataStatus}` });
  const fallbackLabel = intl.formatMessage({
    id: source.fallbackActive
      ? 'terminal.dataSource.tooltip.fallbackActive'
      : 'terminal.dataSource.tooltip.fallbackInactive',
  });

  return [
    intl.formatMessage({ id: 'terminal.dataSource.tooltip.source' }, { source: sourceLabel }),
    intl.formatMessage({ id: 'terminal.dataSource.tooltip.status' }, { status: statusLabel }),
    intl.formatMessage({ id: 'terminal.dataSource.tooltip.fallback' }, { fallback: fallbackLabel }),
    source.detail
      ? intl.formatMessage({ id: 'terminal.dataSource.tooltip.detail' }, { detail: source.detail })
      : undefined,
  ]
    .filter(Boolean)
    .join('\n');
};

// Provider 颜色语义：蓝色=Mock 正常，金色=缺配置/回退，青色=真实源配置完整但待验证，极客蓝=本地 Demo，绿色=真实源已就绪。
export const getProviderBadgeColor = (providerStatus: ProviderStatusResponse | undefined): string => {
  if (!providerStatus) {
    return 'default';
  }
  if (providerStatus.source_type === 'demo_provider') {
    return 'geekblue';
  }
  if (providerStatus.fallback_active || !providerStatus.ready) {
    return providerStatus.source_type === 'real_http_configured' ? 'cyan' : 'gold';
  }
  return providerStatus.mode === 'real' ? 'green' : 'blue';
};

export const DataSourceBadge = ({
  className,
  labelId,
  source,
}: {
  className?: string;
  labelId: string;
  source: StockMarketDataSourceStatus;
}) => {
  const intl = useIntl();
  const label = getMarketDataSourceLabelText(source, intl);
  const color = source.dataStatus === 'unavailable' ? 'gold' : getDataSourceColor(source.source, source.fallbackActive);
  const tooltip = getMarketDataSourceTooltipText(source, intl);

  return (
    <Tooltip title={<span style={{ whiteSpace: 'pre-line' }}>{tooltip}</span>} trigger={['hover', 'focus']}>
      <Tag className={className} color={color} tabIndex={0} aria-label={`${intl.formatMessage({ id: labelId })}: ${tooltip}`}>
        {intl.formatMessage({ id: labelId })}: {label}
      </Tag>
    </Tooltip>
  );
};

export const CompactDataSourceBadge = ({ source }: { source: DataSourceStatus }) => {
  const intl = useIntl();
  const label = getMarketDataSourceLabelText(source, intl);
  const tooltip = getMarketDataSourceTooltipText(source, intl);

  return (
    <Tooltip title={<span style={{ whiteSpace: 'pre-line' }}>{tooltip}</span>} trigger={['hover', 'focus']}>
      <Tag color={source.dataStatus === 'unavailable' ? 'gold' : getDataSourceColor(source.source, source.fallbackActive)} tabIndex={0} aria-label={tooltip}>{label}</Tag>
    </Tooltip>
  );
};

export const SimpleDataSourceBadge = ({
  className,
  labelId,
  tooltip,
  value,
  color = 'default',
}: {
  className?: string;
  labelId: string;
  tooltip?: string;
  value: number | string;
  color?: string;
}) => {
  const intl = useIntl();
  const tag = (
    <Tag className={className} color={color}>
      {intl.formatMessage({ id: labelId })}: {value}
    </Tag>
  );

  return tooltip ? <Tooltip title={tooltip}>{tag}</Tooltip> : tag;
};

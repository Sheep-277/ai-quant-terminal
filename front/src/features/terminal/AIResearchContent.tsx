import {
  ApiOutlined,
  FileSearchOutlined,
  PartitionOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { App, Button, Input, Progress, Space, Table, Tabs, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { ReactNode } from 'react';
import { useMemo, useState } from 'react';
import { AIResearchPollError } from '@/services/terminal/aiResearch';
import { toAIResearchSnapshot } from './apiAdapters';
import type { AIResearchTaskCreateResponse } from './apiTypes';
import { formatDateTime, formatPercent } from './formatters';
import { getToneClass } from './mockData';
import { TerminalTableText } from './TerminalShared';
import { terminalTheme } from './theme';
import type {
  AIResearchEvidence,
  AIResearchSnapshot,
  AIResearchToolCall,
  AIResearchTraceStep,
} from './types';
import {
  useAIResearchLLMStatus,
  useAIResearchSearchStatus,
  useAIResearchTaskByPollUrl,
  useCheckAIResearchLLMConnection,
  useCheckAIResearchSearchConnection,
  useCreateAIResearchTask,
} from './useAIResearchTask';

const taskStatusColorMap: Record<AIResearchSnapshot['status'], string> = {
  queued: 'default',
  running: 'processing',
  completed: 'green',
  failed: 'red',
};

const toolStatusColorMap: Record<AIResearchToolCall['status'], string> = {
  pending: 'default',
  running: 'processing',
  completed: 'green',
  failed: 'red',
};

const evidenceStatusColorMap: Record<AIResearchEvidence['dataStatus'], string> = {
  realtime: 'green',
  delayed: 'gold',
  unavailable: 'red',
};

const evidenceTypeColorMap: Record<AIResearchEvidence['evidenceType'], string> = {
  market_data: 'blue',
  fundamental: 'cyan',
  valuation: 'purple',
  event: 'geekblue',
  risk: 'red',
  tool_output: 'default',
};

const evidenceSourceColorMap: Record<string, string> = {
  Tavily: 'geekblue',
  SerpAPI: 'blue',
  MockSearch: 'default',
};

const getEvidenceSourceLabelId = (source: string): string | null => {
  const normalizedSource = source.toLowerCase();
  if (normalizedSource === 'tavily') {
    return 'terminal.aiResearch.searchSource.tavily';
  }
  if (normalizedSource === 'serpapi') {
    return 'terminal.aiResearch.searchSource.serpapi';
  }
  if (normalizedSource === 'mocksearch') {
    return 'terminal.aiResearch.searchSource.mockSearch';
  }
  return null;
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
        {title}
      </h2>
      {extra}
    </div>
    {children}
  </section>
);

const useTraceColumns = (
  research: AIResearchSnapshot,
): ColumnsType<AIResearchTraceStep> => {
  const intl = useIntl();

  return [
    {
      title: intl.formatMessage({ id: 'terminal.aiResearch.agent' }),
      dataIndex: 'agent',
      width: 130,
      render: (value: AIResearchTraceStep['agent']) => (
        <TerminalTableText>{intl.formatMessage({ id: `terminal.aiResearch.agent.${value}` })}</TerminalTableText>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.status' }),
      dataIndex: 'status',
      width: 98,
      render: (value: AIResearchTraceStep['status']) => (
        <Tag color={toolStatusColorMap[value]}>
          {intl.formatMessage({ id: `terminal.aiResearch.toolStatus.${value}` })}
        </Tag>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.event' }),
      dataIndex: 'title',
      width: 220,
      render: (value: string) => <TerminalTableText>{value}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.summary' }),
      dataIndex: 'summary',
      width: 320,
      render: (value: string, row) => (
        <TerminalTableText className={row.status === 'failed' ? 'terminal-tone-warning' : undefined}>
          {value}
        </TerminalTableText>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.startedAt' }),
      dataIndex: 'startedAt',
      width: 158,
      render: (value: string) =>
        formatDateTime(value, { timezone: research.timezone, locale: intl.locale }),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.completedAt' }),
      dataIndex: 'completedAt',
      width: 158,
      render: (value: string | null) =>
        value
          ? formatDateTime(value, { timezone: research.timezone, locale: intl.locale })
          : '-',
    },
  ];
};

const useToolColumns = (
  research: AIResearchSnapshot,
): ColumnsType<AIResearchToolCall> => {
  const intl = useIntl();

  return [
    {
      title: intl.formatMessage({ id: 'terminal.aiResearch.agent' }),
      dataIndex: 'agent',
      width: 130,
      render: (value: AIResearchToolCall['agent']) => (
        <TerminalTableText>{intl.formatMessage({ id: `terminal.aiResearch.agent.${value}` })}</TerminalTableText>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.aiResearch.tool' }),
      dataIndex: 'toolName',
      width: 170,
      render: (value: string) => <TerminalTableText code>{value}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.status' }),
      dataIndex: 'status',
      width: 98,
      render: (value: AIResearchToolCall['status']) => (
        <Tag color={toolStatusColorMap[value]}>
          {intl.formatMessage({ id: `terminal.aiResearch.toolStatus.${value}` })}
        </Tag>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.summary' }),
      dataIndex: 'summary',
      width: 320,
      render: (value: string, row) => (
        <TerminalTableText className={row.status === 'failed' ? 'terminal-tone-warning' : undefined}>
          {value}
        </TerminalTableText>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.startedAt' }),
      dataIndex: 'startedAt',
      width: 158,
      render: (value: string | null) =>
        value
          ? formatDateTime(value, { timezone: research.timezone, locale: intl.locale })
          : '-',
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.completedAt' }),
      dataIndex: 'completedAt',
      width: 158,
      render: (value: string | null) =>
        value
          ? formatDateTime(value, { timezone: research.timezone, locale: intl.locale })
          : '-',
    },
  ];
};

const useEvidenceColumns = (
  research: AIResearchSnapshot,
): ColumnsType<AIResearchEvidence> => {
  const intl = useIntl();

  return [
    {
      title: intl.formatMessage({ id: 'terminal.aiResearch.evidenceType' }),
      dataIndex: 'evidenceType',
      width: 126,
      render: (value: AIResearchEvidence['evidenceType']) => (
        <Tag color={evidenceTypeColorMap[value]}>
          {intl.formatMessage({ id: `terminal.aiResearch.evidenceType.${value}` })}
        </Tag>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.symbol' }),
      dataIndex: 'symbol',
      width: 98,
      render: (value: string) => <TerminalTableText code>{value}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.event' }),
      dataIndex: 'title',
      width: 260,
      render: (value: string) => <TerminalTableText>{value}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.strategy.value' }),
      dataIndex: 'value',
      width: 190,
      render: (value: string) => <TerminalTableText>{value}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.source' }),
      dataIndex: 'source',
      width: 150,
      render: (value: string) => {
        const labelId = getEvidenceSourceLabelId(value);
        return (
          <Tag color={evidenceSourceColorMap[value] ?? 'default'}>
            <TerminalTableText code>
              {labelId ? intl.formatMessage({ id: labelId }) : value}
            </TerminalTableText>
          </Tag>
        );
      },
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.status' }),
      dataIndex: 'dataStatus',
      width: 98,
      render: (value: AIResearchEvidence['dataStatus']) => (
        <Tag color={evidenceStatusColorMap[value]}>
          {intl.formatMessage({ id: `terminal.dataStatus.${value}` })}
        </Tag>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.time' }),
      dataIndex: 'timestamp',
      width: 158,
      render: (value: string) =>
        formatDateTime(value, { timezone: research.timezone, locale: intl.locale }),
    },
  ];
};

const getAIResearchTaskResultMessageId = (error: unknown) => {
  if (error instanceof AIResearchPollError) {
    if (error.code === 'ai_research_database_reads_disabled') {
      return 'terminal.aiResearch.taskResult.databaseReadsDisabled';
    }
    if (error.code === 'ai_research_task_not_found') {
      return 'terminal.aiResearch.taskResult.notFound';
    }
    if (error.code === 'invalid_ai_research_poll_url') {
      return 'terminal.aiResearch.taskResult.invalidPollUrl';
    }
  }

  return 'terminal.aiResearch.taskResult.requestFailed';
};

const getAIResearchTaskFallbackReason = (receipt: AIResearchTaskCreateResponse) =>
  receipt.fallback_active && receipt.fallback_reason ? receipt.fallback_reason : null;

const AIResearchTaskInputPanel = ({
  research,
  onCreated,
}: {
  research: AIResearchSnapshot;
  onCreated: (receipt: AIResearchTaskCreateResponse) => void;
}) => {
  const intl = useIntl();
  const { message } = App.useApp();
  const defaultSymbol = useMemo(
    () => research.evidence.find((item) => item.symbol)?.symbol ?? '',
    [research.evidence],
  );
  const [query, setQuery] = useState(research.query);
  const [symbol, setSymbol] = useState(defaultSymbol);
  const createTaskMutation = useCreateAIResearchTask();
  const normalizedSymbol = symbol.trim().toUpperCase();
  const normalizedQuery = query.trim();
  const disabled = !normalizedQuery || createTaskMutation.isPending;

  const handleSubmit = async () => {
    if (!normalizedQuery) {
      void message.warning(intl.formatMessage({ id: 'terminal.aiResearch.taskInput.queryRequired' }));
      return;
    }

    try {
      const receipt = await createTaskMutation.mutateAsync({
        market: research.market,
        query: normalizedQuery,
        symbols: normalizedSymbol ? [normalizedSymbol] : [],
        include_strategy_idea: true,
      });
      onCreated(receipt);
      void message.success(
        intl.formatMessage(
          { id: 'terminal.aiResearch.taskInput.createSuccess' },
          { taskId: receipt.task_id },
        ),
      );
    } catch {
      void message.error(intl.formatMessage({ id: 'terminal.aiResearch.createFailed' }));
    }
  };

  return (
    <Panel title={intl.formatMessage({ id: 'terminal.aiResearch.taskInput' })} icon={<RobotOutlined />}>
      <div className="terminal-stack terminal-stack-tight">
        <div className="terminal-builder-field terminal-builder-field-wide">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.taskInput.query' })}</TerminalTableText>
          <Input.TextArea
            autoSize={{ minRows: 2, maxRows: 4 }}
            maxLength={2000}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <div className="terminal-builder-field terminal-builder-field-wide">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.taskInput.symbol' })}</TerminalTableText>
          <Input
            value={symbol}
            placeholder={intl.formatMessage({ id: 'terminal.aiResearch.taskInput.symbolPlaceholder' })}
            onChange={(event) => setSymbol(event.target.value)}
          />
        </div>
        <Space size={6} wrap>
          <Button
            size="small"
            type="primary"
            loading={createTaskMutation.isPending}
            disabled={disabled}
            onClick={handleSubmit}
          >
            {intl.formatMessage({ id: 'terminal.aiResearch.taskInput.submit' })}
          </Button>
          <Tag color="blue">
            {intl.formatMessage({
              id: `terminal.marketSwitcher.${research.market.toLowerCase()}`,
            })}
          </Tag>
          {normalizedSymbol ? <Tag>{normalizedSymbol}</Tag> : null}
        </Space>
      </div>
    </Panel>
  );
};

const AIResearchTaskReceiptPanel = ({
  receipt,
}: {
  receipt: AIResearchTaskCreateResponse;
}) => {
  const intl = useIntl();
  const fallbackReason = getAIResearchTaskFallbackReason(receipt);
  const pollResultQuery = useAIResearchTaskByPollUrl({
    pollUrl: receipt.poll_url,
    enabled:
      !fallbackReason &&
      (receipt.poll_url.startsWith('/api/v1/research/tasks/') ||
        receipt.poll_url.startsWith('/api/v1/ai-research/tasks/')),
  });
  const polledResearch = pollResultQuery.data ? toAIResearchSnapshot(pollResultQuery.data) : undefined;
  const resultStatusColor = polledResearch
    ? 'green'
    : fallbackReason
      ? 'gold'
      : pollResultQuery.isFetching
      ? 'blue'
      : pollResultQuery.isError
        ? 'gold'
        : 'orange';
  const resultStatusText = polledResearch
    ? intl.formatMessage({ id: 'terminal.aiResearch.taskResult.loaded' })
    : fallbackReason
      ? fallbackReason
      : pollResultQuery.isFetching
      ? intl.formatMessage({ id: 'terminal.aiResearch.taskResult.loading' })
      : pollResultQuery.isError
        ? intl.formatMessage({ id: getAIResearchTaskResultMessageId(pollResultQuery.error) })
        : intl.formatMessage({ id: 'terminal.aiResearch.taskResult.unavailable' });

  return (
    <Panel
      title={intl.formatMessage({ id: 'terminal.aiResearch.taskReceipt' })}
      icon={<ApiOutlined />}
      extra={
        <Space size={4} wrap>
          {fallbackReason ? <Tag color="gold">{intl.formatMessage({ id: 'terminal.providerStatus.fallback' })}</Tag> : null}
          <Tag color={taskStatusColorMap[receipt.status]}>
            {intl.formatMessage({ id: `terminal.aiResearch.taskStatus.${receipt.status}` })}
          </Tag>
        </Space>
      }
    >
      <div className="terminal-ai-task-grid">
        <div className="terminal-builder-field">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.taskId' })}</TerminalTableText>
          <TerminalTableText code>{receipt.task_id}</TerminalTableText>
        </div>
        <div className="terminal-builder-field">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.builder.market' })}</TerminalTableText>
          <TerminalTableText>
            {intl.formatMessage({
              id: `terminal.marketSwitcher.${receipt.market.toLowerCase()}`,
            })}
          </TerminalTableText>
        </div>
        <div className="terminal-builder-field">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.acceptedAt' })}</TerminalTableText>
          <TerminalTableText code>
            {formatDateTime(receipt.accepted_at, {
              timezone: receipt.timezone,
              locale: intl.locale,
            })}
          </TerminalTableText>
        </div>
        <div className="terminal-builder-field">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.dataStatus' })}</TerminalTableText>
          <TerminalTableText>
            {intl.formatMessage({ id: `terminal.dataStatus.${receipt.data_status}` })}
          </TerminalTableText>
        </div>
      </div>
      <p className="terminal-data-footnote">
        {intl.formatMessage(
          { id: 'terminal.aiResearch.taskReceiptFootnote' },
          { pollUrl: receipt.poll_url },
        )}
      </p>
      <p className="terminal-data-footnote">
        <Tag color={resultStatusColor}>
          {intl.formatMessage({ id: 'terminal.aiResearch.taskResult.title' })}
        </Tag>
        {resultStatusText}
      </p>
      {polledResearch ? (
        <p className="terminal-data-footnote">
          {intl.formatMessage(
            { id: 'terminal.aiResearch.taskResult.meta' },
            {
              taskId: polledResearch.taskId,
              status: intl.formatMessage({ id: `terminal.aiResearch.taskStatus.${polledResearch.status}` }),
              evidenceCount: polledResearch.evidence.length,
              headline: polledResearch.result.headline,
              confidence: formatPercent(
                polledResearch.result.confidence,
                { signDisplay: 'never', maximumFractionDigits: 0 },
                intl.locale,
              ),
            },
          )}
        </p>
      ) : null}
    </Panel>
  );
};

const AIResearchLLMStatusPanel = () => {
  const intl = useIntl();
  const { message } = App.useApp();
  const llmStatusQuery = useAIResearchLLMStatus();
  const llmCheckMutation = useCheckAIResearchLLMConnection();
  const llmStatus = llmStatusQuery.data;
  const llmCheckResult = llmCheckMutation.data;
  const configured = llmStatus?.configured ?? false;
  const enabled = llmStatus?.enabled ?? false;
  const checkResultColor = llmCheckResult?.ok ? 'green' : 'red';
  const statusColor = llmStatusQuery.isError
    ? 'red'
    : configured
      ? 'green'
      : enabled
        ? 'gold'
        : 'default';
  const missingConfiguration = llmStatus?.missing_configuration.length
    ? llmStatus.missing_configuration.join(', ')
    : '-';

  const handleCheckConnection = async () => {
    try {
      const result = await llmCheckMutation.mutateAsync();
      if (result.ok) {
        void message.success(intl.formatMessage({ id: 'terminal.aiResearch.llmCheck.success' }));
      } else {
        void message.warning(
          intl.formatMessage(
            { id: 'terminal.aiResearch.llmCheck.failed' },
            { reason: result.error ?? result.next_action },
          ),
        );
      }
    } catch {
      void message.error(intl.formatMessage({ id: 'terminal.aiResearch.llmCheck.requestFailed' }));
    }
  };

  return (
    <Panel
      title={intl.formatMessage({ id: 'terminal.aiResearch.llmStatus' })}
      icon={<ApiOutlined />}
      extra={
        <Space size={4} wrap>
          <Button
            size="small"
            type="text"
            loading={llmCheckMutation.isPending}
            disabled={!configured}
            onClick={handleCheckConnection}
          >
            {intl.formatMessage({ id: 'terminal.aiResearch.llmCheck.action' })}
          </Button>
          <Tag color={statusColor}>
            {llmStatusQuery.isFetching
              ? intl.formatMessage({ id: 'terminal.apiSyncing' })
              : intl.formatMessage({
                  id: configured
                    ? 'terminal.aiResearch.llmStatus.configured'
                    : enabled
                      ? 'terminal.aiResearch.llmStatus.missingConfig'
                      : 'terminal.aiResearch.llmStatus.disabled',
                })}
          </Tag>
        </Space>
      }
    >
      <div className="terminal-ai-task-grid">
        <div className="terminal-builder-field">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.llmEnabled' })}</TerminalTableText>
          <TerminalTableText>
            {intl.formatMessage({ id: enabled ? 'terminal.boolean.yes' : 'terminal.boolean.no' })}
          </TerminalTableText>
        </div>
        <div className="terminal-builder-field">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.llmConfigured' })}</TerminalTableText>
          <TerminalTableText>
            {intl.formatMessage({ id: configured ? 'terminal.boolean.yes' : 'terminal.boolean.no' })}
          </TerminalTableText>
        </div>
        <div className="terminal-builder-field">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.llmProvider' })}</TerminalTableText>
          <TerminalTableText code>{llmStatus?.provider_name ?? '-'}</TerminalTableText>
        </div>
        <div className="terminal-builder-field">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.llmModel' })}</TerminalTableText>
          <TerminalTableText code>{llmStatus?.model ?? '-'}</TerminalTableText>
        </div>
        <div className="terminal-builder-field terminal-builder-field-wide">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.llmEndpoint' })}</TerminalTableText>
          <TerminalTableText code>{llmStatus?.endpoint ?? '-'}</TerminalTableText>
        </div>
        <div className="terminal-builder-field terminal-builder-field-wide">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.llmMissingConfig' })}</TerminalTableText>
          <TerminalTableText code>{missingConfiguration}</TerminalTableText>
        </div>
      </div>
      <p className="terminal-data-footnote">
        {llmStatusQuery.isError
          ? intl.formatMessage({ id: 'terminal.aiResearch.llmStatus.requestFailed' })
          : llmStatus?.next_action ?? intl.formatMessage({ id: 'terminal.aiResearch.llmStatus.loading' })}
      </p>
      {llmCheckResult ? (
        <p className="terminal-data-footnote">
          <Tag color={checkResultColor}>
            {intl.formatMessage({
              id: llmCheckResult.ok
                ? 'terminal.aiResearch.llmCheck.ok'
                : 'terminal.aiResearch.llmCheck.notOk',
            })}
          </Tag>
          {llmCheckResult.ok
            ? intl.formatMessage(
                { id: 'terminal.aiResearch.llmCheck.resultOk' },
                { preview: llmCheckResult.response_preview ?? '-' },
              )
            : intl.formatMessage(
                { id: 'terminal.aiResearch.llmCheck.resultError' },
                { reason: llmCheckResult.error ?? llmCheckResult.next_action },
              )}
        </p>
      ) : null}
    </Panel>
  );
};

const AIResearchSearchStatusPanel = () => {
  const intl = useIntl();
  const { message } = App.useApp();
  const searchStatusQuery = useAIResearchSearchStatus();
  const searchCheckMutation = useCheckAIResearchSearchConnection();
  const searchStatus = searchStatusQuery.data;
  const searchCheckResult = searchCheckMutation.data;
  const configured = searchStatus?.configured ?? false;
  const apiKeyConfigured = searchStatus?.api_key_configured ?? false;
  const providerName = searchStatus?.provider_name ?? '-';
  const isMockProvider = providerName === 'mock';
  const statusColor = searchStatusQuery.isError
    ? 'red'
    : configured
      ? isMockProvider
        ? 'default'
        : 'green'
      : 'gold';
  const statusText = searchStatusQuery.isFetching
    ? intl.formatMessage({ id: 'terminal.apiSyncing' })
    : searchStatusQuery.isError
      ? intl.formatMessage({ id: 'terminal.aiResearch.searchStatus.requestFailed' })
      : configured
        ? intl.formatMessage({
            id: isMockProvider
              ? 'terminal.aiResearch.searchStatus.mock'
              : 'terminal.aiResearch.searchStatus.configured',
          })
        : intl.formatMessage({ id: 'terminal.aiResearch.searchStatus.missingConfig' });
  const providerLabelId = getEvidenceSourceLabelId(providerName);
  const providerLabel = providerLabelId ? intl.formatMessage({ id: providerLabelId }) : providerName;
  const missingConfiguration = searchStatus?.missing_configuration.length
    ? searchStatus.missing_configuration.join(', ')
    : '-';
  const checkResultColor = searchCheckResult?.ok ? 'green' : 'red';

  const handleCheckConnection = async () => {
    try {
      const result = await searchCheckMutation.mutateAsync();
      if (result.ok) {
        void message.success(
          intl.formatMessage(
            { id: 'terminal.aiResearch.searchCheck.success' },
            { count: result.result_count },
          ),
        );
      } else {
        void message.warning(
          intl.formatMessage(
            { id: 'terminal.aiResearch.searchCheck.failed' },
            { reason: result.error ?? result.next_action },
          ),
        );
      }
    } catch {
      void message.error(intl.formatMessage({ id: 'terminal.aiResearch.searchCheck.requestFailed' }));
    }
  };

  return (
    <Panel
      title={intl.formatMessage({ id: 'terminal.aiResearch.searchStatus' })}
      icon={<FileSearchOutlined />}
      extra={
        <Space size={4} wrap>
          <Button
            size="small"
            type="text"
            loading={searchCheckMutation.isPending}
            disabled={!configured}
            onClick={handleCheckConnection}
          >
            {intl.formatMessage({ id: 'terminal.aiResearch.searchCheck.action' })}
          </Button>
          <Tag color={statusColor}>{statusText}</Tag>
        </Space>
      }
    >
      <div className="terminal-ai-task-grid">
        <div className="terminal-builder-field">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.searchProvider' })}</TerminalTableText>
          <TerminalTableText code>{providerLabel}</TerminalTableText>
        </div>
        <div className="terminal-builder-field">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.searchConfigured' })}</TerminalTableText>
          <TerminalTableText>
            {intl.formatMessage({ id: configured ? 'terminal.boolean.yes' : 'terminal.boolean.no' })}
          </TerminalTableText>
        </div>
        <div className="terminal-builder-field">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.searchApiKey' })}</TerminalTableText>
          <TerminalTableText>
            {intl.formatMessage({ id: apiKeyConfigured ? 'terminal.boolean.yes' : 'terminal.boolean.no' })}
          </TerminalTableText>
        </div>
        <div className="terminal-builder-field">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.searchResultLimit' })}</TerminalTableText>
          <TerminalTableText code>{searchStatus?.result_limit ?? '-'}</TerminalTableText>
        </div>
        <div className="terminal-builder-field">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.searchTimeout' })}</TerminalTableText>
          <TerminalTableText code>{searchStatus?.timeout_seconds ?? '-'}</TerminalTableText>
        </div>
        <div className="terminal-builder-field">
          <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.llmMissingConfig' })}</TerminalTableText>
          <TerminalTableText code>{missingConfiguration}</TerminalTableText>
        </div>
      </div>
      <p className="terminal-data-footnote">
        {searchStatusQuery.isError
          ? intl.formatMessage({ id: 'terminal.aiResearch.searchStatus.requestFailed' })
          : searchStatus?.next_action ?? intl.formatMessage({ id: 'terminal.aiResearch.searchStatus.loading' })}
      </p>
      {searchCheckResult ? (
        <p className="terminal-data-footnote">
          <Tag color={checkResultColor}>
            {intl.formatMessage({
              id: searchCheckResult.ok
                ? 'terminal.aiResearch.searchCheck.ok'
                : 'terminal.aiResearch.searchCheck.notOk',
            })}
          </Tag>
          {searchCheckResult.ok
            ? intl.formatMessage(
                { id: 'terminal.aiResearch.searchCheck.resultOk' },
                {
                  count: searchCheckResult.result_count,
                  preview: searchCheckResult.response_preview ?? '-',
                },
              )
            : intl.formatMessage(
                { id: 'terminal.aiResearch.searchCheck.resultError' },
                { reason: searchCheckResult.error ?? searchCheckResult.next_action },
              )}
        </p>
      ) : null}
    </Panel>
  );
};

export const AIResearchContent = ({
  research,
  taskReceipt,
}: {
  research: AIResearchSnapshot;
  taskReceipt?: AIResearchTaskCreateResponse;
}) => {
  const intl = useIntl();
  const [manualTaskReceipt, setManualTaskReceipt] = useState<AIResearchTaskCreateResponse | undefined>();
  const traceColumns = useTraceColumns(research);
  const toolColumns = useToolColumns(research);
  const evidenceColumns = useEvidenceColumns(research);
  const completedTraceCount = research.trace.filter((step) => step.status === 'completed').length;
  const completedToolCallCount = research.toolCalls.filter(
    (toolCall) => toolCall.status === 'completed',
  ).length;
  const evidenceById = new Map(
    research.evidence.map((evidence) => [evidence.evidenceId, evidence]),
  );
  const latestFailedToolCall = [...research.toolCalls]
    .reverse()
    .find((toolCall) => toolCall.status === 'failed');
  const eventEvidence = research.evidence.filter((evidence) => evidence.evidenceType === 'event');
  const searchEvidence = eventEvidence.filter((evidence) =>
    ['tavily', 'serpapi', 'mocksearch'].includes(evidence.source.toLowerCase()),
  );
  const searchSourceLabels = Array.from(
    new Set(
      searchEvidence.map((evidence) => {
        const labelId = getEvidenceSourceLabelId(evidence.source);
        return labelId ? intl.formatMessage({ id: labelId }) : evidence.source;
      }),
    ),
  );
  const citedEvidence = research.result.evidenceIds
    .map((evidenceId) => evidenceById.get(evidenceId))
    .filter((evidence): evidence is AIResearchEvidence => Boolean(evidence));
  const visibleTaskReceipt = manualTaskReceipt ?? taskReceipt;

  return (
    <div className="terminal-ai-workspace">
      <div className="terminal-ai-primary-row">
        <div className="terminal-ai-task-summary">
          <Panel
            title={intl.formatMessage({ id: 'terminal.panel.agentResearchTask' })}
            icon={<RobotOutlined />}
            extra={
              <Tag color={taskStatusColorMap[research.status]}>
                {intl.formatMessage({ id: `terminal.aiResearch.taskStatus.${research.status}` })}
              </Tag>
            }
          >
            <div className="terminal-ai-brief">
              <TerminalTableText className={getToneClass(research.result.direction)}>
                {research.result.headline}
              </TerminalTableText>
              <p title={research.query}>{research.query}</p>
              <Progress
                percent={Math.round(research.result.confidence * 100)}
                size="small"
                strokeColor="var(--aqt-accent)"
                railColor={terminalTheme.chartTrailColor}
              />
            </div>
            <div className="terminal-ai-task-grid">
              <div className="terminal-builder-field">
                <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.taskId' })}</TerminalTableText>
                <TerminalTableText code>{research.taskId}</TerminalTableText>
              </div>
              <div className="terminal-builder-field">
                <TerminalTableText>{intl.formatMessage({ id: 'terminal.builder.market' })}</TerminalTableText>
                <TerminalTableText>{intl.formatMessage({ id: `terminal.marketSwitcher.${research.market.toLowerCase()}` })}</TerminalTableText>
              </div>
              <div className="terminal-builder-field">
                <TerminalTableText>{intl.formatMessage({ id: 'terminal.table.confidence' })}</TerminalTableText>
                <TerminalTableText>
                  {formatPercent(
                    research.result.confidence,
                    { signDisplay: 'never', maximumFractionDigits: 0 },
                    intl.locale,
                  )}
                </TerminalTableText>
              </div>
              <div className="terminal-builder-field">
                <TerminalTableText>{intl.formatMessage({ id: 'terminal.builder.eventHorizon' })}</TerminalTableText>
                <TerminalTableText>
                  {intl.formatMessage({
                    id: `terminal.aiResearch.horizon.${research.result.horizon}`,
                    defaultMessage: research.result.horizon,
                  })}
                </TerminalTableText>
              </div>
              <div className="terminal-builder-field">
                <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.traceProgress' })}</TerminalTableText>
                <TerminalTableText>
                  {completedTraceCount}/{research.trace.length}
                </TerminalTableText>
              </div>
              <div className="terminal-builder-field">
                <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.toolProgress' })}</TerminalTableText>
                <TerminalTableText>
                  {completedToolCallCount}/{research.toolCalls.length}
                </TerminalTableText>
              </div>
              <div className="terminal-builder-field">
                <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.evidenceCount' })}</TerminalTableText>
                <TerminalTableText>{research.evidence.length}</TerminalTableText>
              </div>
              <div className="terminal-builder-field">
                <TerminalTableText>{intl.formatMessage({ id: 'terminal.aiResearch.dataStatus' })}</TerminalTableText>
                <TerminalTableText>{intl.formatMessage({ id: `terminal.dataStatus.${research.dataStatus}` })}</TerminalTableText>
              </div>
            </div>
            <p className="terminal-data-footnote">
              {intl.formatMessage(
                { id: 'terminal.aiResearch.updatedAt' },
                {
                  timestamp: formatDateTime(research.timestamp, {
                    timezone: research.timezone,
                    locale: intl.locale,
                  }),
                },
              )}
            </p>
          </Panel>

        </div>
        <div id="terminal-ai-research-task-input" className="terminal-ai-task-input">
          <AIResearchTaskInputPanel research={research} onCreated={setManualTaskReceipt} />
        </div>
      </div>
      {visibleTaskReceipt ? <AIResearchTaskReceiptPanel receipt={visibleTaskReceipt} /> : null}
      <div className="terminal-ai-conclusion">
        <Panel
          title={intl.formatMessage({ id: 'terminal.aiResearch.keyPoints' })}
          icon={<FileSearchOutlined />}
          extra={<Tag color="blue">{intl.formatMessage({ id: 'terminal.noPrivateChain' })}</Tag>}
        >
          <div className="terminal-ai-conclusion-grid" data-has-risks={research.result.riskFlags.length > 0}>
            <div className="terminal-stack terminal-stack-tight">
              <h3 className="terminal-quant-section-title">{intl.formatMessage({ id: 'terminal.aiResearch.keyFindings' })}</h3>
              {research.result.keyPoints.map((point) => (
                <div className="terminal-trace-row" key={point}>
                  <span>KP</span>
                  <TerminalTableText className="terminal-trace-title">{point}</TerminalTableText>
                  <em>{intl.formatMessage({ id: 'terminal.status.completed' })}</em>
                </div>
              ))}
            </div>
            {research.result.riskFlags.length > 0 ? (
              <div className="terminal-stack terminal-stack-tight">
                <h3 className="terminal-quant-section-title">{intl.formatMessage({ id: 'terminal.table.risk' })}</h3>
                {research.result.riskFlags.map((flag) => (
                  <div className="terminal-trace-row" key={flag}>
                    <span>RK</span>
                    <TerminalTableText className="terminal-tone-warning terminal-trace-title">
                      {flag}
                    </TerminalTableText>
                    <em>{intl.formatMessage({ id: 'terminal.table.risk' })}</em>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
          <div className="terminal-evidence-reference">
            <div className="terminal-evidence-reference-title">
              {intl.formatMessage({ id: 'terminal.aiResearch.evidenceRefs' })}
            </div>
            <Space wrap size={[4, 4]}>
              {citedEvidence.map((evidence) => (
                <Tag className="terminal-status-tag" color={evidenceStatusColorMap[evidence.dataStatus]} key={evidence.evidenceId}>
                  <TerminalTableText code>
                    {evidence.evidenceId} · {evidence.title}
                  </TerminalTableText>
                </Tag>
              ))}
            </Space>
          </div>
        </Panel>
      </div>
      <div className="terminal-ai-audit">
          <Panel
            title={intl.formatMessage({ id: 'terminal.panel.researchTrace' })}
            icon={<PartitionOutlined />}
            extra={
              <Space size={4} wrap>
                {latestFailedToolCall ? (
                  <Tag color="red">{intl.formatMessage({ id: 'terminal.aiResearch.latestFailure' })}</Tag>
                ) : null}
                <Tag color={searchEvidence.length ? 'geekblue' : 'default'}>
                  {intl.formatMessage(
                    { id: 'terminal.aiResearch.publicSearchEvidence' },
                    { count: searchEvidence.length },
                  )}
                </Tag>
                {searchSourceLabels.map((source) => (
                  <Tag color="blue" key={source}>
                    {source}
                  </Tag>
                ))}
              </Space>
            }
          >
            <Tabs
              size="small"
              items={[
                {
                  key: 'trace',
                  label: intl.formatMessage({ id: 'terminal.panel.researchTrace' }),
                  children: (
                    <Table
                      size="small"
                      columns={traceColumns}
                      dataSource={research.trace}
                      pagination={false}
                      rowClassName={(row) => (row.status === 'failed' ? 'terminal-ai-research-failed-row' : '')}
                      rowKey="key"
                      scroll={{ x: 984 }}
                    />
                  ),
                },
                {
                  key: 'tool-calls',
                  label: intl.formatMessage({ id: 'terminal.aiResearch.toolCalls' }),
                  children: (
                    <>
                      <Table
                        size="small"
                        columns={toolColumns}
                        dataSource={research.toolCalls}
                        pagination={false}
                        rowClassName={(row) => (row.status === 'failed' ? 'terminal-ai-research-failed-row' : '')}
                        rowKey="key"
                        scroll={{ x: 1034 }}
                      />
                      {latestFailedToolCall ? (
                        <div className="terminal-ai-failure-detail">
                          <Space size={4} wrap>
                            <Tag color="red">{intl.formatMessage({ id: 'terminal.aiResearch.latestFailure' })}</Tag>
                            <TerminalTableText>
                              {intl.formatMessage({
                                id: `terminal.aiResearch.agent.${latestFailedToolCall.agent}`,
                              })}
                            </TerminalTableText>
                            <TerminalTableText code>{latestFailedToolCall.toolName}</TerminalTableText>
                          </Space>
                          <p>{latestFailedToolCall.summary}</p>
                        </div>
                      ) : null}
                    </>
                  ),
                },
                {
                  key: 'evidence',
                  label: intl.formatMessage({ id: 'terminal.action.evidence' }),
                  children: (
                    <Table
                      size="small"
                      columns={evidenceColumns}
                      dataSource={research.evidence}
                      pagination={false}
                      rowKey="key"
                      scroll={{ x: 1080 }}
                    />
                  ),
                },
              ]}
            />
          </Panel>
      </div>
      {/* 折叠仅改变可见性，配置查询与连接检查组件不会因展开而重新挂载。 */}
      <details className="terminal-ai-connections">
        <summary>{intl.formatMessage({ id: 'terminal.aiResearch.connectionDetails' })}</summary>
        <div className="terminal-ai-connections-grid">
          <AIResearchLLMStatusPanel />
          <AIResearchSearchStatusPanel />
        </div>
      </details>
    </div>
  );
};

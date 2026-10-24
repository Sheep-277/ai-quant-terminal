import { ExperimentOutlined } from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import {
  Alert,
  Button,
  Input,
  InputNumber,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import type {
  RiskConstraintDto,
  StrategyConditionDto,
  StrategyConditionField,
  StrategyConditionOperator,
  StrategyDraftCreateRequest,
  StrategyDraftDto,
} from './apiTypes';
import { formatDateTime, formatNumber } from './formatters';
import { StockMetricStrip } from './StockMetricStrip';
import { TerminalTableText } from './TerminalShared';
import { StrategyGuardrails } from './TerminalRightRail';
import type {
  StrategyCondition,
  StrategyDraft,
  StrategyLabSnapshot,
} from './types';
import { useParseStrategyNaturalLanguage } from './useStrategyLab';

type StrategyEvaluationRow = {
  key: string;
  field: string;
  operator: string;
  expectedValue: number;
  upperValue: number | null;
  actualValue: number | null;
  matched: boolean;
  reason: string;
};

type StrategyEvaluationSnapshot = {
  entryMatched: boolean;
  exitMatched: boolean;
  entryEvaluations: StrategyEvaluationRow[];
  exitEvaluations: StrategyEvaluationRow[];
};

type EditableStrategyCondition = StrategyCondition & {
  rowKey: string;
};

const formatStrategyField = (field: string, intl: ReturnType<typeof useIntl>) =>
  intl.formatMessage({
    id: `terminal.strategy.field.${field}`,
    defaultMessage: field,
  });

const formatStrategyOperator = (
  operator: string,
  intl: ReturnType<typeof useIntl>,
) =>
  intl.formatMessage({
    id: `terminal.strategy.operator.${operator}`,
    defaultMessage: operator,
  });

const formatStrategyReason = (
  reason: string,
  intl: ReturnType<typeof useIntl>,
) =>
  intl.formatMessage({
    id: `terminal.strategy.reason.${reason}`,
    defaultMessage: reason,
  });

const strategyConditionFields: StrategyConditionField[] = [
  'momentum_20d',
  'roe',
  'volume_ratio',
  'rsi_14',
  'pe_ttm',
];
const strategyConditionOperators: StrategyConditionOperator[] = [
  'gt',
  'gte',
  'lt',
  'lte',
  'between',
];

const getStrategyFallbackReason = (parameters: Record<string, unknown>) =>
  parameters.fallback_active === true &&
  typeof parameters.fallback_reason === 'string'
    ? parameters.fallback_reason
    : null;

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

const useConditionColumns = ({
  editable = false,
  onChange,
}: {
  editable?: boolean;
  onChange?: (index: number, patch: Partial<StrategyCondition>) => void;
} = {}): ColumnsType<EditableStrategyCondition> => {
  const intl = useIntl();

  return [
    {
      title: intl.formatMessage({ id: 'terminal.strategy.field' }),
      dataIndex: 'field',
      width: 180,
      render: (value: string, _row, index) =>
        editable ? (
          <Select
            size="small"
            value={value}
            options={strategyConditionFields.map((field) => ({
              value: field,
              label: formatStrategyField(field, intl),
            }))}
            onChange={(field) => onChange?.(index, { field })}
          />
        ) : (
          <TerminalTableText>
            {formatStrategyField(value, intl)}
          </TerminalTableText>
        ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.strategy.operator' }),
      dataIndex: 'operator',
      width: 110,
      render: (value: string, _row, index) =>
        editable ? (
          <Select
            size="small"
            value={value}
            options={strategyConditionOperators.map((operator) => ({
              value: operator,
              label: formatStrategyOperator(operator, intl),
            }))}
            onChange={(operator) =>
              onChange?.(index, {
                operator,
                upperValue: operator === 'between' ? _row.upperValue : null,
              })
            }
          />
        ) : (
          <TerminalTableText>
            {formatStrategyOperator(value, intl)}
          </TerminalTableText>
        ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.strategy.value' }),
      dataIndex: 'value',
      width: 92,
      align: 'right',
      render: (value: number, _row, index) =>
        editable ? (
          <InputNumber
            size="small"
            value={value}
            step={0.01}
            onChange={(nextValue) =>
              onChange?.(index, { value: Number(nextValue ?? 0) })
            }
          />
        ) : (
          <TerminalTableText>
            {formatNumber(value, {}, intl.locale)}
          </TerminalTableText>
        ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.strategy.upperValue' }),
      dataIndex: 'upperValue',
      width: 92,
      align: 'right',
      render: (value: number | null, row, index) =>
        editable ? (
          <InputNumber
            disabled={row.operator !== 'between'}
            size="small"
            value={value}
            step={0.01}
            onChange={(nextValue) =>
              onChange?.(index, {
                upperValue: nextValue === null ? null : Number(nextValue),
              })
            }
          />
        ) : (
          <TerminalTableText>
            {value === null ? '-' : formatNumber(value, {}, intl.locale)}
          </TerminalTableText>
        ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.strategy.description' }),
      dataIndex: 'description',
      width: 260,
      render: (value: string, _row, index) =>
        editable ? (
          <Input
            size="small"
            value={value}
            onChange={(event) =>
              onChange?.(index, { description: event.target.value })
            }
          />
        ) : (
          <TerminalTableText>{value}</TerminalTableText>
        ),
    },
  ];
};

// 行键只服务于前端表格渲染，提交 DTO 时不会传给后端。
const toEditableConditions = (
  conditions: StrategyCondition[],
  group: 'entry' | 'exit',
): EditableStrategyCondition[] =>
  conditions.map((condition, index) => ({
    ...condition,
    rowKey: `${group}-${index}`,
  }));

const toConditionDto = (
  condition: StrategyCondition,
): StrategyConditionDto => ({
  field: condition.field as StrategyConditionField,
  operator: condition.operator as StrategyConditionOperator,
  value: condition.value,
  upper_value: condition.operator === 'between' ? condition.upperValue : null,
  description: condition.description,
});

const toEditableConditionFromDto = (
  condition: StrategyConditionDto,
  rowKey: string,
): EditableStrategyCondition => ({
  field: condition.field,
  operator: condition.operator,
  value: condition.value,
  upperValue: condition.upper_value,
  description: condition.description,
  rowKey,
});

const readStrategyEvaluation = (
  parameters: Record<string, unknown>,
): StrategyEvaluationSnapshot | null => {
  const raw = parameters.strategy_evaluation;
  if (!raw || typeof raw !== 'object') {
    return null;
  }

  const evaluation = raw as {
    entry_matched?: unknown;
    exit_matched?: unknown;
    entry_evaluations?: unknown;
    exit_evaluations?: unknown;
  };
  const toRows = (rows: unknown, group: string): StrategyEvaluationRow[] =>
    Array.isArray(rows)
      ? rows.map((row, index) => {
          const item = row as Record<string, unknown>;
          return {
            key: `${group}-${index}`,
            field: String(item.field ?? '-'),
            operator: String(item.operator ?? '-'),
            expectedValue: Number(item.expected_value ?? 0),
            upperValue:
              typeof item.upper_value === 'number' ? item.upper_value : null,
            actualValue:
              typeof item.actual_value === 'number' ? item.actual_value : null,
            matched: item.matched === true,
            reason: String(item.reason ?? '-'),
          };
        })
      : [];

  return {
    entryMatched: evaluation.entry_matched === true,
    exitMatched: evaluation.exit_matched === true,
    entryEvaluations: toRows(evaluation.entry_evaluations, 'entry'),
    exitEvaluations: toRows(evaluation.exit_evaluations, 'exit'),
  };
};

const StrategyEvaluationList = ({
  rows,
}: {
  rows: StrategyEvaluationRow[];
}) => {
  const intl = useIntl();

  return (
    <div className="terminal-strategy-evaluation-list">
      {rows.map((row) => (
        <div className="terminal-strategy-evaluation-item" key={row.key}>
          <div className="terminal-strategy-evaluation-main">
            <strong>{formatStrategyField(row.field, intl)}</strong>
            <Tag color={row.matched ? 'red' : 'default'}>
              {intl.formatMessage({
                id: row.matched
                  ? 'terminal.strategy.matched.yes'
                  : 'terminal.strategy.matched.no',
              })}
            </Tag>
          </div>
          <div className="terminal-strategy-evaluation-meta">
            <span>{formatStrategyOperator(row.operator, intl)}</span>
            <span>
              {intl.formatMessage({ id: 'terminal.strategy.expectedValue' })}:{' '}
              {row.upperValue === null
                ? formatNumber(row.expectedValue, {}, intl.locale)
                : `${formatNumber(row.expectedValue, {}, intl.locale)} - ${formatNumber(row.upperValue, {}, intl.locale)}`}
            </span>
            <span>
              {intl.formatMessage({ id: 'terminal.strategy.actualValue' })}:{' '}
              {row.actualValue === null
                ? '-'
                : formatNumber(row.actualValue, {}, intl.locale)}
            </span>
          </div>
          <p>{formatStrategyReason(row.reason, intl)}</p>
        </div>
      ))}
    </div>
  );
};

const StrategyDraftReceiptPanel = ({
  receipt,
}: {
  receipt: StrategyDraftDto;
}) => {
  const intl = useIntl();
  const fallbackReason = getStrategyFallbackReason(receipt.parameters);
  const storageSource =
    typeof receipt.parameters.storage_source === 'string'
      ? receipt.parameters.storage_source
      : receipt.parameters.fallback_active === true
        ? 'mock_fallback'
        : 'mock';

  return (
    <Panel
      title={intl.formatMessage({ id: 'terminal.strategy.createReceipt' })}
      icon={<ExperimentOutlined />}
      extra={
        <Space size={4} wrap>
          {fallbackReason ? (
            <Tag color="gold">
              {intl.formatMessage({ id: 'terminal.providerStatus.fallback' })}
            </Tag>
          ) : null}
          <Tag color="blue">
            {intl.formatMessage({
              id: `terminal.strategy.status.${receipt.status}`,
            })}
          </Tag>
        </Space>
      }
    >
      <div className="terminal-ai-brief">
        <strong>{receipt.strategy_id}</strong>
        <StrategySummaryRows
          rows={[
            [
              intl.formatMessage({ id: 'terminal.strategy.summary.market' }),
              receipt.universe.market,
            ],
            [
              intl.formatMessage({ id: 'terminal.strategy.summary.universe' }),
              receipt.universe.name,
            ],
            [
              intl.formatMessage({
                id: 'terminal.strategy.summary.symbolCount',
              }),
              String(receipt.universe.symbols.length),
            ],
            [
              intl.formatMessage({
                id: 'terminal.strategy.summary.entryCount',
              }),
              String(receipt.entry_conditions.length),
            ],
            [
              intl.formatMessage({ id: 'terminal.strategy.summary.exitCount' }),
              String(receipt.exit_conditions.length),
            ],
            [
              intl.formatMessage({ id: 'terminal.strategy.summary.riskCount' }),
              String(receipt.risk_constraints.length),
            ],
            [
              intl.formatMessage({ id: 'terminal.strategy.summary.rebalance' }),
              intl.formatMessage({
                id: `terminal.strategy.rebalance.${receipt.rebalance_frequency}`,
              }),
            ],
            [
              intl.formatMessage({
                id: 'terminal.strategy.summary.storageSource',
              }),
              intl.formatMessage({
                id: `terminal.strategy.storageSource.${storageSource}`,
                defaultMessage: storageSource,
              }),
            ],
          ]}
        />
        <StrategyConditionPreview
          title={intl.formatMessage({
            id: 'terminal.strategy.summary.entryPreview',
          })}
          conditions={receipt.entry_conditions}
        />
        <StrategyConditionPreview
          title={intl.formatMessage({
            id: 'terminal.strategy.summary.exitPreview',
          })}
          conditions={receipt.exit_conditions}
        />
        <p>
          {intl.formatMessage(
            { id: 'terminal.strategy.createReceiptMeta' },
            {
              createdBy: intl.formatMessage({
                id: `terminal.strategy.createdBy.${receipt.created_by}`,
              }),
              createdAt: formatDateTime(receipt.created_at, {
                timezone: 'Asia/Shanghai',
                locale: intl.locale,
              }),
            },
          )}
        </p>
        {fallbackReason ? (
          <p className="terminal-strategy-fallback-note">{fallbackReason}</p>
        ) : null}
        <p className="terminal-muted">
          {intl.formatMessage({
            id: 'terminal.strategy.createReceiptFootnote',
          })}
        </p>
      </div>
    </Panel>
  );
};

const StrategyConditionPreview = ({
  title,
  conditions,
}: {
  title: string;
  conditions: StrategyConditionDto[];
}) => {
  const intl = useIntl();
  const visibleConditions = conditions.slice(0, 2);
  const hiddenCount = Math.max(conditions.length - visibleConditions.length, 0);

  return (
    <div className="terminal-strategy-evaluation-list">
      <div className="terminal-panel-toolbar">
        <span className="terminal-muted">{title}</span>
        {hiddenCount > 0 ? (
          <Tag>
            {intl.formatMessage(
              { id: 'terminal.strategy.summary.moreRules' },
              { count: hiddenCount },
            )}
          </Tag>
        ) : null}
      </div>
      {visibleConditions.map((condition) => (
        <div
          className="terminal-strategy-evaluation-item"
          key={`${condition.field}-${condition.operator}-${condition.value}-${condition.upper_value}-${condition.description}`}
        >
          <div className="terminal-strategy-evaluation-main">
            <strong>{formatStrategyField(condition.field, intl)}</strong>
            <Tag>{formatStrategyOperator(condition.operator, intl)}</Tag>
          </div>
          <div className="terminal-strategy-evaluation-meta">
            <span>
              {condition.upper_value === null
                ? formatNumber(condition.value, {}, intl.locale)
                : `${formatNumber(condition.value, {}, intl.locale)} - ${formatNumber(condition.upper_value, {}, intl.locale)}`}
            </span>
          </div>
          <p>{condition.description}</p>
        </div>
      ))}
    </div>
  );
};

const StrategySummaryRows = ({ rows, compact = false }: { rows: Array<[string, string]>; compact?: boolean }) => (
  <div className={compact ? 'terminal-strategy-summary-grid' : 'terminal-strategy-evaluation-list'}>
    {rows.map(([label, value]) => (
      <div className="terminal-strategy-evaluation-item" key={label}>
        <div className="terminal-strategy-evaluation-main">
          <span className="terminal-muted">{label}</span>
          <strong>{value}</strong>
        </div>
      </div>
    ))}
  </div>
);

const StrategyDraftSummary = ({ draft }: { draft: StrategyDraft }) => {
  const intl = useIntl();

  return (
    <StrategySummaryRows
      compact
      rows={[
        [
          intl.formatMessage({ id: 'terminal.strategy.summary.version' }),
          `v${draft.version}`,
        ],
        [
          intl.formatMessage({ id: 'terminal.strategy.summary.entryCount' }),
          String(draft.entryConditions.length),
        ],
        [
          intl.formatMessage({ id: 'terminal.strategy.summary.exitCount' }),
          String(draft.exitConditions.length),
        ],
        [
          intl.formatMessage({ id: 'terminal.strategy.summary.riskCount' }),
          String(draft.riskMetrics.length),
        ],
        [
          intl.formatMessage({ id: 'terminal.strategy.summary.rebalance' }),
          intl.formatMessage({
            id: `terminal.strategy.rebalance.${draft.rebalanceFrequency}`,
          }),
        ],
        [
          intl.formatMessage({ id: 'terminal.strategy.summary.symbolCount' }),
          String(draft.universe.symbols.length),
        ],
      ]}
    />
  );
};

const ParsedRiskConstraintList = ({
  riskConstraints,
}: {
  riskConstraints: RiskConstraintDto[];
}) => {
  const intl = useIntl();
  const rows = riskConstraints.flatMap((constraint, index) => [
    ...(constraint.max_drawdown === null
      ? []
      : [
          {
            key: `max-drawdown-${index}`,
            label: intl.formatMessage({ id: 'terminal.metric.maxDrawdown' }),
            value: formatNumber(
              constraint.max_drawdown,
              { style: 'percent' },
              intl.locale,
            ),
          },
        ]),
    ...(constraint.stop_loss === null
      ? []
      : [
          {
            key: `stop-loss-${index}`,
            label: intl.formatMessage({ id: 'terminal.metric.stopLoss' }),
            value: formatNumber(
              constraint.stop_loss,
              { style: 'percent' },
              intl.locale,
            ),
          },
        ]),
    ...(constraint.min_liquidity === null
      ? []
      : [
          {
            key: `min-liquidity-${index}`,
            label: intl.formatMessage({ id: 'terminal.metric.minLiquidity' }),
            value: formatNumber(constraint.min_liquidity, {}, intl.locale),
          },
        ]),
  ]);

  return (
    <div className="terminal-strategy-evaluation-list">
      <div className="terminal-panel-toolbar">
        <span className="terminal-muted">
          {intl.formatMessage({ id: 'terminal.strategy.nl.riskTitle' })}
        </span>
        <Tag color={rows.length > 0 ? 'gold' : 'default'}>
          {rows.length > 0
            ? intl.formatMessage(
                { id: 'terminal.strategy.nl.riskParsed' },
                { count: rows.length },
              )
            : intl.formatMessage({ id: 'terminal.strategy.nl.riskEmpty' })}
        </Tag>
      </div>
      {rows.map((row) => (
        <div className="terminal-strategy-evaluation-item" key={row.key}>
          <div className="terminal-strategy-evaluation-main">
            <strong>{row.label}</strong>
            <Tag color="gold">{row.value}</Tag>
          </div>
        </div>
      ))}
    </div>
  );
};

export const StrategyLabContent = ({
  strategyLab,
  strategyDraftReceipt,
  strategyDraftSource,
  onDraftPayloadChange,
}: {
  strategyLab: StrategyLabSnapshot;
  strategyDraftReceipt?: StrategyDraftDto;
  strategyDraftSource?: StrategyDraftDto;
  onDraftPayloadChange?: (
    payload: StrategyDraftCreateRequest | undefined,
  ) => void;
}) => {
  const intl = useIntl();
  const draft = strategyLab.drafts[0];
  const [editableEntryConditions, setEditableEntryConditions] = useState<
    EditableStrategyCondition[]
  >([]);
  const [editableExitConditions, setEditableExitConditions] = useState<
    EditableStrategyCondition[]
  >([]);
  const [parsedRiskConstraints, setParsedRiskConstraints] = useState<
    StrategyDraftCreateRequest['risk_constraints'] | undefined
  >();
  const [naturalLanguageText, setNaturalLanguageText] = useState('');
  const [parseWarnings, setParseWarnings] = useState<string[]>([]);
  const [parseError, setParseError] = useState<string | null>(null);
  const [draftApplied, setDraftApplied] = useState(false);
  const parseStrategyMutation = useParseStrategyNaturalLanguage();

  useEffect(() => {
    if (!draft) {
      setEditableEntryConditions([]);
      setEditableExitConditions([]);
      setParsedRiskConstraints(undefined);
      setParseWarnings([]);
      setParseError(null);
      setDraftApplied(false);
      onDraftPayloadChange?.(undefined);
      return;
    }
    setEditableEntryConditions(
      toEditableConditions(draft.entryConditions, 'entry'),
    );
    setEditableExitConditions(
      toEditableConditions(draft.exitConditions, 'exit'),
    );
    setParsedRiskConstraints(undefined);
    setParseWarnings([]);
    setParseError(null);
    setDraftApplied(false);
    onDraftPayloadChange?.(undefined);
  }, [draft?.strategyId]);

  const updateEntryCondition = (
    index: number,
    patch: Partial<StrategyCondition>,
  ) => {
    setDraftApplied(false);
    setEditableEntryConditions((conditions) =>
      conditions.map((condition, currentIndex) =>
        currentIndex === index ? { ...condition, ...patch } : condition,
      ),
    );
  };
  const updateExitCondition = (
    index: number,
    patch: Partial<StrategyCondition>,
  ) => {
    setDraftApplied(false);
    setEditableExitConditions((conditions) =>
      conditions.map((condition, currentIndex) =>
        currentIndex === index ? { ...condition, ...patch } : condition,
      ),
    );
  };
  const editableEntryConditionColumns = useConditionColumns({
    editable: true,
    onChange: updateEntryCondition,
  });
  const editableExitConditionColumns = useConditionColumns({
    editable: true,
    onChange: updateExitCondition,
  });

  if (!draft) {
    return (
      <Panel
        title={intl.formatMessage({ id: 'terminal.panel.strategyBuilder' })}
        icon={<ExperimentOutlined />}
      >
        <p className="terminal-muted">
          {intl.formatMessage({ id: 'terminal.strategy.empty' })}
        </p>
      </Panel>
    );
  }

  const strategyEvaluation = readStrategyEvaluation(draft.parameters);
  const fallbackReason = getStrategyFallbackReason(draft.parameters);
  const hasParsedPreview = Boolean(parseStrategyMutation.data && !parseError);
  const fillNaturalLanguageExample = () => {
    setNaturalLanguageText(
      intl.formatMessage({ id: 'terminal.strategy.nl.exampleText' }),
    );
    setParseWarnings([]);
    setParseError(null);
    setDraftApplied(false);
    onDraftPayloadChange?.(undefined);
  };
  const parseNaturalLanguageConditions = async () => {
    const text = naturalLanguageText.trim();
    if (!text) {
      setParseError(intl.formatMessage({ id: 'terminal.strategy.nl.empty' }));
      return;
    }

    setParseError(null);
    try {
      const response = await parseStrategyMutation.mutateAsync({
        market: strategyLab.market,
        text,
        universe: strategyDraftSource?.universe ?? null,
        require_user_confirmation: true,
      });
      setEditableEntryConditions(
        response.result.entry_conditions.map((condition, index) =>
          toEditableConditionFromDto(condition, `parsed-entry-${index}`),
        ),
      );
      setEditableExitConditions(
        response.result.exit_conditions.map((condition, index) =>
          toEditableConditionFromDto(condition, `parsed-exit-${index}`),
        ),
      );
      setParsedRiskConstraints(response.result.risk_constraints);
      setParseWarnings(response.result.warnings);
      setDraftApplied(false);
      onDraftPayloadChange?.(undefined);
    } catch {
      setParseError(intl.formatMessage({ id: 'terminal.strategy.nl.failed' }));
    }
  };
  const applyEditedDraft = () => {
    if (!strategyDraftSource) {
      return;
    }

    onDraftPayloadChange?.({
      market: strategyDraftSource.universe.market,
      name: strategyDraftSource.name,
      description: strategyDraftSource.description,
      universe: strategyDraftSource.universe,
      entry_conditions: editableEntryConditions.map(toConditionDto),
      exit_conditions: editableExitConditions.map(toConditionDto),
      position_rule: strategyDraftSource.position_rule,
      rebalance_frequency: strategyDraftSource.rebalance_frequency,
      risk_constraints:
        parsedRiskConstraints ?? strategyDraftSource.risk_constraints,
      created_by: 'user',
    });
    setDraftApplied(true);
  };
  const resetEditedDraft = () => {
    setEditableEntryConditions(
      toEditableConditions(draft.entryConditions, 'entry'),
    );
    setEditableExitConditions(
      toEditableConditions(draft.exitConditions, 'exit'),
    );
    setParsedRiskConstraints(undefined);
    setParseWarnings([]);
    setParseError(null);
    setDraftApplied(false);
    onDraftPayloadChange?.(undefined);
  };

  return (
    <div className="terminal-strategy-workspace">
      <div className="terminal-strategy-main-row">
        <div className="terminal-strategy-summary">
          <Panel
            title={draft.name}
            icon={<ExperimentOutlined />}
            extra={
              <Space size={4} wrap>
                {fallbackReason ? (
                  <Tag color="gold">
                    {intl.formatMessage({
                      id: 'terminal.providerStatus.fallback',
                    })}
                  </Tag>
                ) : null}
                <Tag color="gold">
                  {intl.formatMessage({
                    id: `terminal.strategy.status.${draft.status}`,
                  })}
                </Tag>
              </Space>
            }
          >
            <div className="terminal-ai-brief">
              <strong>
                {strategyLab.defaultUniverse.name} /{' '}
                {strategyLab.defaultUniverse.market}
              </strong>
              <p>{draft.description}</p>
              {fallbackReason ? (
                <p className="terminal-strategy-fallback-note">
                  {fallbackReason}
                </p>
              ) : null}
              <StrategyDraftSummary draft={draft} />
              <Space wrap size={4}>
                {draft.universe.symbols.map((symbol) => (
                  <Tag key={symbol}>{symbol}</Tag>
                ))}
              </Space>
            </div>
            <StockMetricStrip
              metrics={draft.positionMetrics}
              market={strategyLab.market}
            />
          </Panel>
        </div>
        <div className="terminal-strategy-editor">
          <Panel
            title={intl.formatMessage({ id: 'terminal.panel.strategyBuilder' })}
            icon={<ExperimentOutlined />}
            extra={
              <Space size={4} wrap>
                {draftApplied ? (
                  <Tag color="green">
                    {intl.formatMessage({
                      id: 'terminal.strategy.editor.applied',
                    })}
                  </Tag>
                ) : null}
                <Tag>
                  {intl.formatMessage({
                    id: `terminal.strategy.rebalance.${draft.rebalanceFrequency}`,
                  })}
                </Tag>
              </Space>
            }
          >
            <Tabs
              size="small"
              items={[
                {
                  key: 'natural-language',
                  label: intl.formatMessage({
                    id: 'terminal.strategy.nl.title',
                  }),
                  children: (
                    <div className="terminal-stack terminal-stack-tight">
                      <div className="terminal-panel-toolbar">
                        <span className="terminal-muted">
                          {intl.formatMessage({
                            id: 'terminal.strategy.nl.description',
                          })}
                        </span>
                        <Space size={4}>
                          <Button
                            size="small"
                            onClick={fillNaturalLanguageExample}
                          >
                            {intl.formatMessage({
                              id: 'terminal.strategy.nl.fillExample',
                            })}
                          </Button>
                          <Button
                            size="small"
                            type="primary"
                            loading={parseStrategyMutation.isPending}
                            onClick={parseNaturalLanguageConditions}
                          >
                            {intl.formatMessage({
                              id: 'terminal.strategy.nl.parse',
                            })}
                          </Button>
                        </Space>
                      </div>
                      <Input.TextArea
                        value={naturalLanguageText}
                        onChange={(event) =>
                          setNaturalLanguageText(event.target.value)
                        }
                        placeholder={intl.formatMessage({
                          id: 'terminal.strategy.nl.placeholder',
                        })}
                        autoSize={{ minRows: 2, maxRows: 4 }}
                      />
                      <p className="terminal-muted">
                        {intl.formatMessage({
                          id: 'terminal.strategy.nl.example',
                        })}
                      </p>
                      {parseStrategyMutation.data && !parseError ? (
                        <Alert
                          type="success"
                          showIcon
                          title={intl.formatMessage(
                            { id: 'terminal.strategy.nl.success' },
                            {
                              entryCount:
                                parseStrategyMutation.data.result
                                  .entry_conditions.length,
                              exitCount:
                                parseStrategyMutation.data.result
                                  .exit_conditions.length,
                              riskCount:
                                parseStrategyMutation.data.result
                                  .risk_constraints.length,
                              confidence: formatNumber(
                                parseStrategyMutation.data.confidence,
                                {},
                                intl.locale,
                              ),
                            },
                          )}
                        />
                      ) : null}
                      {parseWarnings.length > 0 ? (
                        <Alert
                          type="warning"
                          showIcon
                          title={parseWarnings.join(' / ')}
                        />
                      ) : null}
                      {parseError ? (
                        <Alert type="error" showIcon title={parseError} />
                      ) : null}
                    </div>
                  ),
                },
                {
                  key: 'entry',
                  label: intl.formatMessage({
                    id: 'terminal.strategy.entryConditions',
                  }),
                  children: (
                    <div className="terminal-stack terminal-stack-tight">
                      <div className="terminal-panel-toolbar">
                        <span className="terminal-muted">
                          {intl.formatMessage({
                            id: 'terminal.strategy.editor.description',
                          })}
                        </span>
                        <Space size={4}>
                          {hasParsedPreview ? (
                            <Tag color={draftApplied ? 'green' : 'gold'}>
                              {intl.formatMessage({
                                id: draftApplied
                                  ? 'terminal.strategy.editor.parsedApplied'
                                  : 'terminal.strategy.editor.parsedPending',
                              })}
                            </Tag>
                          ) : null}
                          <Button size="small" onClick={resetEditedDraft}>
                            {intl.formatMessage({
                              id: 'terminal.strategy.editor.reset',
                            })}
                          </Button>
                          <Button
                            size="small"
                            type="primary"
                            onClick={applyEditedDraft}
                            disabled={!strategyDraftSource}
                          >
                            {intl.formatMessage({
                              id: 'terminal.strategy.editor.apply',
                            })}
                          </Button>
                        </Space>
                      </div>
                      <Table
                        size="small"
                        columns={editableEntryConditionColumns}
                        dataSource={editableEntryConditions}
                        pagination={false}
                        rowKey="rowKey"
                        scroll={{ x: 734 }}
                      />
                    </div>
                  ),
                },
                {
                  key: 'exit-risk',
                  label: intl.formatMessage({
                    id: 'terminal.strategy.exitConditions',
                  }),
                  children: (
                    <div className="terminal-stack terminal-stack-tight">
                      <Table
                        size="small"
                        columns={editableExitConditionColumns}
                        dataSource={editableExitConditions}
                        pagination={false}
                        rowKey="rowKey"
                        scroll={{ x: 734 }}
                      />
                      <ParsedRiskConstraintList
                        riskConstraints={
                          parsedRiskConstraints ??
                          strategyDraftSource?.risk_constraints ??
                          []
                        }
                      />
                      <StockMetricStrip
                        metrics={draft.riskMetrics}
                        market={strategyLab.market}
                      />
                    </div>
                  ),
                },
              ]}
            />
            <StrategyGuardrails />
          </Panel>
        </div>
      </div>
      <p className="terminal-data-footnote">
        {intl.formatMessage(
          { id: 'terminal.strategy.updatedAt' },
          { timestamp: formatDateTime(strategyLab.timestamp, { timezone: 'Asia/Shanghai', locale: intl.locale }) },
        )}
      </p>
      {strategyDraftReceipt ? <StrategyDraftReceiptPanel receipt={strategyDraftReceipt} /> : null}
      {strategyEvaluation ? (
        <Panel
          title={intl.formatMessage({
            id: 'terminal.strategy.engineEvaluation',
          })}
          icon={<ExperimentOutlined />}
          extra={
            <Space size={4}>
              <Tag color={strategyEvaluation.entryMatched ? 'red' : 'default'}>
                {intl.formatMessage({
                  id: strategyEvaluation.entryMatched
                    ? 'terminal.strategy.entryMatched'
                    : 'terminal.strategy.entryNotMatched',
                })}
              </Tag>
              <Tag color={strategyEvaluation.exitMatched ? 'gold' : 'default'}>
                {intl.formatMessage({
                  id: strategyEvaluation.exitMatched
                    ? 'terminal.strategy.exitMatched'
                    : 'terminal.strategy.exitNotMatched',
                })}
              </Tag>
            </Space>
          }
        >
          <div className="terminal-strategy-evaluation-grid">
            <StrategyEvaluationList rows={strategyEvaluation.entryEvaluations} />
            <StrategyEvaluationList rows={strategyEvaluation.exitEvaluations} />
          </div>
        </Panel>
      ) : null}
    </div>
  );
};

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { App } from 'antd';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import zhCN from '../../locales/zh-CN/terminal';
import type {
  StrategyDraftCreateRequest,
  StrategyDraftDto,
  StrategyNaturalLanguageParseResponse,
} from './apiTypes';
import { StrategyLabContent } from './StrategyLabContent';
import type { StrategyLabSnapshot } from './types';

const dependencyMocks = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  parseData: undefined as unknown,
  stockMetricStrip: vi.fn(),
}));

vi.mock('@ant-design/icons', () => ({
  ExperimentOutlined: () => null,
}));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: 'zh-CN',
    formatMessage: (
      { id, defaultMessage }: { id?: string; defaultMessage?: string },
      values?: Record<string, string | number>,
    ) => {
      let message =
        (id && zhCN[id as keyof typeof zhCN]) || defaultMessage || id || '';
      for (const [key, value] of Object.entries(values ?? {})) {
        message = message.replace(`{${key}}`, String(value));
      }
      return message;
    },
  }),
}));

vi.mock('./useStrategyLab', () => ({
  useParseStrategyNaturalLanguage: () => ({
    data: dependencyMocks.parseData,
    isPending: false,
    mutateAsync: dependencyMocks.mutateAsync,
  }),
}));

vi.mock('./TerminalRightRail', () => ({
  StrategyGuardrails: () => <div data-testid="strategy-guardrails" />,
}));

vi.mock('./StockMetricStrip', () => ({
  StockMetricStrip: (props: {
    market: string;
    metrics: StrategyLabSnapshot['drafts'][number]['positionMetrics'];
  }) => {
    dependencyMocks.stockMetricStrip(props);
    return (
      <div data-testid="strategy-metrics">
        {props.market}:{props.metrics.length}
      </div>
    );
  },
}));

const strategyLab: StrategyLabSnapshot = {
  market: 'HK',
  timestamp: '2026-10-16T02:00:00Z',
  defaultUniverse: {
    market: 'HK',
    universeType: 'index',
    name: 'Hang Seng TECH',
    symbols: ['00700.HK', '09988.HK'],
  },
  drafts: [
    {
      strategyId: 'strategy-hk-quality-001',
      name: 'HK Cash Flow Value Draft',
      version: 3,
      description: '筛选现金流稳健且估值合理的港股互联网标的。',
      status: 'draft',
      createdBy: 'agent',
      createdAt: '2026-10-15T02:00:00Z',
      updatedAt: '2026-10-16T02:00:00Z',
      universe: {
        market: 'HK',
        universeType: 'index',
        name: 'Hang Seng TECH',
        symbols: ['00700.HK', '09988.HK'],
      },
      entryConditions: [
        {
          field: 'roe',
          operator: 'gt',
          value: 0.18,
          upperValue: null,
          description: 'ROE 大于 18%',
        },
      ],
      exitConditions: [
        {
          field: 'rsi_14',
          operator: 'gt',
          value: 78,
          upperValue: null,
          description: 'RSI 高于 78 时退出',
        },
      ],
      positionMetrics: [
        {
          labelId: 'terminal.metric.maxHoldings',
          value: 8,
        },
      ],
      riskMetrics: [
        {
          labelId: 'terminal.metric.maxDrawdown',
          value: 0.16,
          valueFormat: 'percent',
        },
      ],
      rebalanceFrequency: 'monthly',
      parameters: {
        strategy_evaluation: {
          entry_matched: true,
          exit_matched: false,
          entry_evaluations: [
            {
              field: 'roe',
              operator: 'gt',
              expected_value: 0.18,
              upper_value: null,
              actual_value: 0.21,
              matched: true,
              reason: 'matched',
            },
          ],
          exit_evaluations: [
            {
              field: 'rsi_14',
              operator: 'gt',
              expected_value: 78,
              upper_value: null,
              actual_value: 62,
              matched: false,
              reason: 'not_matched',
            },
          ],
        },
      },
    },
  ],
};

const strategyDraftSource: StrategyDraftDto = {
  strategy_id: 'strategy-hk-quality-001',
  name: 'HK Cash Flow Value Draft',
  version: 3,
  description: '筛选现金流稳健且估值合理的港股互联网标的。',
  status: 'draft',
  created_by: 'agent',
  created_at: '2026-10-15T02:00:00Z',
  updated_at: '2026-10-16T02:00:00Z',
  universe: {
    market: 'HK',
    universe_type: 'index',
    name: 'Hang Seng TECH',
    symbols: ['00700.HK', '09988.HK'],
  },
  entry_conditions: [
    {
      field: 'roe',
      operator: 'gt',
      value: 0.18,
      upper_value: null,
      description: 'ROE 大于 18%',
    },
  ],
  exit_conditions: [
    {
      field: 'rsi_14',
      operator: 'gt',
      value: 78,
      upper_value: null,
      description: 'RSI 高于 78 时退出',
    },
  ],
  position_rule: {
    max_holdings: 8,
    max_position_weight: 0.15,
    equal_weight: true,
  },
  rebalance_frequency: 'monthly',
  risk_constraints: [
    {
      max_drawdown: 0.16,
      stop_loss: 0.07,
      min_liquidity: 30_000_000,
    },
  ],
  parameters: {
    storage_source: 'database',
  },
};

const parsedResponse: StrategyNaturalLanguageParseResponse = {
  market: 'HK',
  source: 'hybrid',
  confidence: 0.92,
  requires_user_confirmation: true,
  parsed_at: '2026-10-16T02:05:00Z',
  raw_text: 'ROE 大于 20%，RSI 高于 75 时退出，止损 6%',
  result: {
    entry_conditions: [
      {
        field: 'roe',
        operator: 'gt',
        value: 0.2,
        upper_value: null,
        description: 'ROE 大于 20%',
      },
    ],
    exit_conditions: [
      {
        field: 'rsi_14',
        operator: 'gt',
        value: 75,
        upper_value: null,
        description: 'RSI 高于 75 时退出',
      },
    ],
    risk_constraints: [
      {
        max_drawdown: null,
        stop_loss: 0.06,
        min_liquidity: null,
      },
    ],
    warnings: ['请确认 ROE 使用最近一期财报口径。'],
  },
};

const renderContent = ({
  value = strategyLab,
  receipt,
  onDraftPayloadChange = vi.fn(),
}: {
  value?: StrategyLabSnapshot;
  receipt?: StrategyDraftDto;
  onDraftPayloadChange?: (
    payload: StrategyDraftCreateRequest | undefined,
  ) => void;
} = {}) => ({
  onDraftPayloadChange,
  ...render(
    <App>
      <StrategyLabContent
        strategyLab={value}
        strategyDraftReceipt={receipt}
        strategyDraftSource={strategyDraftSource}
        onDraftPayloadChange={onDraftPayloadChange}
      />
    </App>,
  ),
});

beforeEach(() => {
  vi.clearAllMocks();
  dependencyMocks.parseData = undefined;
  dependencyMocks.mutateAsync.mockImplementation(async () => {
    dependencyMocks.parseData = parsedResponse;
    return parsedResponse;
  });
});

it('aligns summary and editor in one row and places the footnote and receipt below it', () => {
  const { container } = renderContent({ receipt: strategyDraftSource });
  const workspace = container.querySelector('.terminal-strategy-workspace') as HTMLElement;
  const row = workspace.querySelector('.terminal-strategy-main-row') as HTMLElement;
  expect(row.children).toHaveLength(2);
  expect(row.children[0]).toHaveClass('terminal-strategy-summary');
  expect(row.children[1]).toHaveClass('terminal-strategy-editor');
  expect(row.querySelector('.terminal-strategy-summary-grid')?.children).toHaveLength(6);
  expect(row.querySelector('[data-testid="strategy-guardrails"]')).not.toBeNull();
  expect(workspace.querySelector(':scope > .terminal-data-footnote')).not.toBeNull();
  expect(row.querySelector('.terminal-data-footnote')).toBeNull();
});

afterEach(() => {
  cleanup();
});

describe('StrategyLabContent', () => {
  it('没有策略草案时显示空状态', () => {
    renderContent({ value: { ...strategyLab, drafts: [] } });

    expect(screen.getByText('暂无策略草案。')).toBeInTheDocument();
    expect(
      screen.queryByText('HK Cash Flow Value Draft'),
    ).not.toBeInTheDocument();
  });

  it('展示草案摘要、股票池和策略引擎评估', () => {
    renderContent();

    expect(screen.getByText('HK Cash Flow Value Draft')).toBeInTheDocument();
    expect(screen.getByText('Hang Seng TECH / HK')).toBeInTheDocument();
    expect(screen.getByText('v3')).toBeInTheDocument();
    expect(screen.getByText('00700.HK')).toBeInTheDocument();
    expect(screen.getByText('09988.HK')).toBeInTheDocument();
    expect(screen.getByTestId('strategy-metrics')).toHaveTextContent('HK:1');
    expect(screen.getByText('入场命中')).toBeInTheDocument();
    expect(screen.getByText('出场未触发')).toBeInTheDocument();
    expect(screen.getByText('规则已命中')).toBeInTheDocument();
    expect(screen.getByText('规则未命中')).toBeInTheDocument();
  });

  it('自然语言解析后允许人工修改条件并应用到待保存草案', async () => {
    const onDraftPayloadChange = vi.fn();
    renderContent({ onDraftPayloadChange });

    const text = 'ROE 大于 20%，RSI 高于 75 时退出，止损 6%';
    fireEvent.change(screen.getByPlaceholderText(/例如：ROE 大于 18%/), {
      target: { value: text },
    });
    fireEvent.click(screen.getByRole('button', { name: '解析条件' }));

    expect(dependencyMocks.mutateAsync).toHaveBeenCalledWith({
      market: 'HK',
      text,
      universe: strategyDraftSource.universe,
      require_user_confirmation: true,
    });
    expect(
      await screen.findByText(
        '已解析：入场 1 条，出场 1 条，风险 1 条，置信度 0.92。',
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText('请确认 ROE 使用最近一期财报口径。'),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole('tab', { name: '入场条件 Entry Conditions' }),
    );
    const [valueInput] = screen.getAllByRole('spinbutton');
    fireEvent.change(valueInput, { target: { value: '0.25' } });
    fireEvent.click(screen.getByRole('button', { name: '应用到保存草案' }));

    await waitFor(() => {
      expect(onDraftPayloadChange).toHaveBeenLastCalledWith(
        expect.objectContaining({
          market: 'HK',
          created_by: 'user',
          entry_conditions: [
            expect.objectContaining({ field: 'roe', value: 0.25 }),
          ],
          risk_constraints: parsedResponse.result.risk_constraints,
        }),
      );
    });
    expect(screen.getByText('已应用')).toBeInTheDocument();
  });

  it('展示草案创建回执的保存来源与规则预览', () => {
    renderContent({ receipt: strategyDraftSource });

    expect(screen.getByText('草案创建回执')).toBeInTheDocument();
    expect(screen.getByText('strategy-hk-quality-001')).toBeInTheDocument();
    expect(screen.getByText('数据库')).toBeInTheDocument();
    expect(screen.getByText('入场规则预览')).toBeInTheDocument();
    expect(screen.getByText('出场规则预览')).toBeInTheDocument();
    expect(screen.getByText('ROE 大于 18%')).toBeInTheDocument();
    expect(screen.getByText('RSI 高于 78 时退出')).toBeInTheDocument();
  });
});

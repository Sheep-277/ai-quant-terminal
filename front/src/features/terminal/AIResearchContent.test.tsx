import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { App } from 'antd';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AIResearchPollError } from '@/services/terminal/aiResearch';
import zhCN from '../../locales/zh-CN/terminal';
import enUS from '../../locales/en-US/terminal';
import { AIResearchContent } from './AIResearchContent';
import type { AIResearchTaskCreateResponse } from './apiTypes';
import type { AIResearchSnapshot } from './types';

const dependencyMocks = vi.hoisted(() => ({
  locale: 'zh-CN',
  createTask: vi.fn(),
  llmCheck: vi.fn(),
  searchCheck: vi.fn(),
  toAIResearchSnapshot: vi.fn(),
  useAIResearchLLMStatus: vi.fn(),
  useAIResearchSearchStatus: vi.fn(),
  useAIResearchTaskByPollUrl: vi.fn(),
  useCheckAIResearchLLMConnection: vi.fn(),
  useCheckAIResearchSearchConnection: vi.fn(),
  useCreateAIResearchTask: vi.fn(),
}));

vi.mock('@ant-design/icons', () => ({
  ApiOutlined: () => null,
  FileSearchOutlined: () => null,
  PartitionOutlined: () => null,
  RobotOutlined: () => null,
}));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: dependencyMocks.locale,
    formatMessage: (
      { id, defaultMessage }: { id?: string; defaultMessage?: string },
      values?: Record<string, string | number>,
    ) => {
      const dictionary = dependencyMocks.locale === 'en-US' ? enUS : zhCN;
      let message =
        (id && dictionary[id as keyof typeof dictionary]) || defaultMessage || id || '';
      for (const [key, value] of Object.entries(values ?? {})) {
        message = message.replace(`{${key}}`, String(value));
      }
      return message;
    },
  }),
}));

vi.mock('./apiAdapters', () => ({
  toAIResearchSnapshot: dependencyMocks.toAIResearchSnapshot,
}));

vi.mock('./useAIResearchTask', () => ({
  useAIResearchLLMStatus: dependencyMocks.useAIResearchLLMStatus,
  useAIResearchSearchStatus: dependencyMocks.useAIResearchSearchStatus,
  useAIResearchTaskByPollUrl: dependencyMocks.useAIResearchTaskByPollUrl,
  useCheckAIResearchLLMConnection:
    dependencyMocks.useCheckAIResearchLLMConnection,
  useCheckAIResearchSearchConnection:
    dependencyMocks.useCheckAIResearchSearchConnection,
  useCreateAIResearchTask: dependencyMocks.useCreateAIResearchTask,
}));

const research: AIResearchSnapshot = {
  taskId: 'research-hk-001',
  market: 'HK',
  query: '分析腾讯的基本面、估值和近期事件风险',
  status: 'completed',
  timestamp: '2026-10-16T02:05:00Z',
  timezone: 'Asia/Hong_Kong',
  dataStatus: 'delayed',
  trace: [
    {
      key: 'trace-001',
      stepId: 'trace-001',
      agent: 'orchestrator',
      status: 'completed',
      title: '接收研究任务',
      summary: '已确认市场和研究标的。',
      startedAt: '2026-10-16T02:00:00Z',
      completedAt: '2026-10-16T02:00:01Z',
    },
    {
      key: 'trace-002',
      stepId: 'trace-002',
      agent: 'risk',
      status: 'running',
      title: '复核风险',
      summary: '正在检查事件风险。',
      startedAt: '2026-10-16T02:00:02Z',
      completedAt: null,
    },
  ],
  toolCalls: [
    {
      key: 'tool-001',
      toolCallId: 'tool-001',
      agent: 'market_analyst',
      toolName: 'run_quant_pipeline',
      status: 'completed',
      startedAt: '2026-10-16T02:00:02Z',
      completedAt: '2026-10-16T02:00:03Z',
      summary: '量化指标计算完成。',
    },
    {
      key: 'tool-002',
      toolCallId: 'tool-002',
      agent: 'orchestrator',
      toolName: 'bailian_chat_completion',
      status: 'failed',
      startedAt: '2026-10-16T02:00:04Z',
      completedAt: '2026-10-16T02:00:05Z',
      summary: '百炼请求超时，保留确定性量化结论。',
    },
  ],
  evidence: [
    {
      key: 'evidence-news-001',
      evidenceId: 'evidence-news-001',
      evidenceType: 'event',
      market: 'HK',
      symbol: '00700.HK',
      title: '腾讯发布季度业绩',
      value: '收入与利润保持增长。',
      source: 'Tavily',
      dataStatus: 'delayed',
      timestamp: '2026-10-16T01:50:00Z',
    },
    {
      key: 'evidence-risk-001',
      evidenceId: 'evidence-risk-001',
      evidenceType: 'risk',
      market: 'HK',
      symbol: '00700.HK',
      title: '事件风险复核',
      value: '关注监管和行业竞争。',
      source: 'QuantEngine',
      dataStatus: 'delayed',
      timestamp: '2026-10-16T01:55:00Z',
    },
  ],
  result: {
    headline: '估值合理，但需要关注事件风险。',
    direction: 'neutral',
    confidence: 0.82,
    horizon: 'risk_review',
    keyPoints: ['盈利保持稳定'],
    riskFlags: ['监管与行业竞争风险'],
    evidenceIds: ['evidence-news-001'],
  },
};

const taskReceipt: AIResearchTaskCreateResponse = {
  task_id: 'research-hk-002',
  market: 'HK',
  query: '分析腾讯近期风险',
  status: 'queued',
  accepted_at: '2026-10-16T02:10:00Z',
  timezone: 'Asia/Hong_Kong',
  data_status: 'delayed',
  poll_url: '/api/v1/research/tasks/research-hk-002',
  fallback_active: false,
  fallback_reason: null,
  storage_source: 'database',
};

type QueryStub = {
  data?: unknown;
  error?: unknown;
  isError: boolean;
  isFetching: boolean;
};

const query = (overrides: Partial<QueryStub> = {}): QueryStub => ({
  data: undefined,
  error: undefined,
  isError: false,
  isFetching: false,
  ...overrides,
});

const mutation = (overrides: Record<string, unknown> = {}) => ({
  data: undefined,
  isPending: false,
  mutateAsync: vi.fn(),
  ...overrides,
});

const renderContent = (receipt?: AIResearchTaskCreateResponse) =>
  render(
    <App>
      <AIResearchContent research={research} taskReceipt={receipt} />
    </App>,
  );

beforeEach(() => {
  vi.clearAllMocks();
  dependencyMocks.useAIResearchLLMStatus.mockReturnValue(
    query({
      data: {
        enabled: true,
        configured: true,
        provider_name: 'bailian',
        model: 'qwen-plus',
        endpoint: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        missing_configuration: [],
        next_action: 'ready',
      },
    }),
  );
  dependencyMocks.useAIResearchSearchStatus.mockReturnValue(
    query({
      data: {
        provider_name: 'tavily',
        configured: true,
        api_key_configured: true,
        result_limit: 5,
        timeout_seconds: 10,
        missing_configuration: [],
        next_action: 'ready',
      },
    }),
  );
  dependencyMocks.useAIResearchTaskByPollUrl.mockReturnValue(query());
  dependencyMocks.useCheckAIResearchLLMConnection.mockReturnValue(
    mutation({ mutateAsync: dependencyMocks.llmCheck }),
  );
  dependencyMocks.useCheckAIResearchSearchConnection.mockReturnValue(
    mutation({ mutateAsync: dependencyMocks.searchCheck }),
  );
  dependencyMocks.useCreateAIResearchTask.mockReturnValue(
    mutation({ mutateAsync: dependencyMocks.createTask }),
  );
  dependencyMocks.llmCheck.mockResolvedValue({
    ok: true,
    provider_name: 'bailian',
    model: 'qwen-plus',
    endpoint: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    response_preview: 'ok',
    error: null,
    next_action: 'ready',
  });
  dependencyMocks.searchCheck.mockResolvedValue({
    ok: true,
    provider_name: 'tavily',
    query: 'Tencent latest news',
    result_count: 3,
    response_preview: 'Tencent released its latest results.',
    error: null,
    next_action: 'ready',
  });
  dependencyMocks.createTask.mockResolvedValue(taskReceipt);
  dependencyMocks.toAIResearchSnapshot.mockReturnValue(research);
});

afterEach(() => {
  cleanup();
  dependencyMocks.locale = 'zh-CN';
});

describe('AIResearchContent', () => {
  it('does not reserve an empty risk column when no risk flags are supplied', () => {
    const { container } = render(<App><AIResearchContent research={{ ...research, result: { ...research.result, riskFlags: [] } }} /></App>);
    const conclusion = container.querySelector('.terminal-ai-conclusion') as HTMLElement;
    expect(conclusion.querySelector('.terminal-ai-conclusion-grid')).toHaveAttribute('data-has-risks', 'false');
    expect(within(conclusion).queryByRole('heading', { name: zhCN['terminal.table.risk'] })).not.toBeInTheDocument();
    expect(within(conclusion).getByText('盈利保持稳定')).toBeInTheDocument();
  });
  it.each(['zh-CN', 'en-US'])('keeps primary panels together and separates results, audit and connection details in %s', locale => {
    dependencyMocks.locale = locale;
    const dictionary = locale === 'en-US' ? enUS : zhCN;
    const { container } = renderContent();
    const row = container.querySelector('.terminal-ai-primary-row') as HTMLElement;
    expect(row.children).toHaveLength(2);
    expect(row.children[0]).toHaveClass('terminal-ai-task-summary');
    expect(row.children[1]).toHaveAttribute('id', 'terminal-ai-research-task-input');
    const workspace = container.querySelector('.terminal-ai-workspace') as HTMLElement;
    expect(workspace.querySelector(':scope > .terminal-ai-conclusion')).not.toBeNull();
    expect(workspace.querySelector(':scope > .terminal-ai-audit')).not.toBeNull();
    const summary = screen.getByText(dictionary['terminal.aiResearch.connectionDetails']);
    const details = summary.closest('details') as HTMLDetailsElement;
    expect(details.open).toBe(false);
    const textboxes = within(row.children[1] as HTMLElement).getAllByRole('textbox');
    fireEvent.change(textboxes[0], { target: { value: 'UNSAVED_RESEARCH_QUERY' } });
    fireEvent.click(summary);
    expect(details.open).toBe(true);
    expect(screen.getAllByRole('button', { name: dictionary['terminal.aiResearch.llmCheck.action'] })).toHaveLength(2);
    fireEvent.click(summary);
    expect(details.open).toBe(false);
    expect(textboxes[0]).toHaveValue('UNSAVED_RESEARCH_QUERY');
    expect(dependencyMocks.createTask).not.toHaveBeenCalled();
    expect(dependencyMocks.llmCheck).not.toHaveBeenCalled();
    expect(dependencyMocks.searchCheck).not.toHaveBeenCalled();
  });
  it('展示研究摘要、公开搜索证据和最近失败工具详情', () => {
    renderContent();

    expect(
      screen.getByText('估值合理，但需要关注事件风险。'),
    ).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute(
      'aria-valuenow',
      '82',
    );
    expect(screen.getByText('风险复核 Risk Review')).toBeInTheDocument();
    expect(screen.getByText('公开搜索证据 1 条')).toBeInTheDocument();
    expect(screen.getAllByText('Tavily 公开搜索').length).toBeGreaterThan(0);
    expect(screen.getByText('盈利保持稳定')).toBeInTheDocument();
    expect(screen.getByText('监管与行业竞争风险')).toBeInTheDocument();
    expect(screen.getByText(/evidence-news-001/)).toHaveTextContent(
      '腾讯发布季度业绩',
    );

    fireEvent.click(screen.getByRole('tab', { name: '工具调用 Tool Calls' }));
    expect(
      screen.getAllByText('bailian_chat_completion').length,
    ).toBeGreaterThanOrEqual(2);
    expect(
      screen.getAllByText('百炼请求超时，保留确定性量化结论。').length,
    ).toBeGreaterThan(0);
  });

  it('展示 LLM 与搜索源配置并仅在点击时检查连接', async () => {
    renderContent();

    fireEvent.click(screen.getByText(zhCN['terminal.aiResearch.connectionDetails']));

    expect(screen.getByText('qwen-plus')).toBeInTheDocument();
    expect(screen.getAllByText('配置完整').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('Tavily 公开搜索').length).toBeGreaterThan(0);
    expect(dependencyMocks.llmCheck).not.toHaveBeenCalled();
    expect(dependencyMocks.searchCheck).not.toHaveBeenCalled();

    const checkButtons = screen.getAllByRole('button', { name: '检查连接' });
    fireEvent.click(checkButtons[0]);
    fireEvent.click(checkButtons[1]);

    await waitFor(() => {
      expect(dependencyMocks.llmCheck).toHaveBeenCalledTimes(1);
      expect(dependencyMocks.searchCheck).toHaveBeenCalledTimes(1);
    });
  });

  it('创建任务时规范化股票代码并显示新的任务回执', async () => {
    renderContent();

    const inputPanel = screen
      .getByRole('heading', { name: '研究任务输入' })
      .closest('.terminal-panel');
    if (!(inputPanel instanceof HTMLElement)) {
      throw new Error('Research task input panel was not rendered.');
    }
    const textboxes = within(inputPanel).getAllByRole('textbox');
    fireEvent.change(textboxes[0], {
      target: { value: '  分析腾讯近期风险  ' },
    });
    fireEvent.change(textboxes[1], { target: { value: '  00700.hk  ' } });
    fireEvent.click(
      within(inputPanel).getByRole('button', { name: '创建研究任务' }),
    );

    await waitFor(() => {
      expect(dependencyMocks.createTask).toHaveBeenCalledWith({
        market: 'HK',
        query: '分析腾讯近期风险',
        symbols: ['00700.HK'],
        include_strategy_idea: true,
      });
    });
    expect(await screen.findByText('research-hk-002')).toBeInTheDocument();
    expect(dependencyMocks.useAIResearchTaskByPollUrl).toHaveBeenCalledWith({
      pollUrl: taskReceipt.poll_url,
      enabled: true,
    });
  });

  it('任务写入回退时显示原因并禁用轮询', () => {
    const fallbackReceipt: AIResearchTaskCreateResponse = {
      ...taskReceipt,
      fallback_active: true,
      fallback_reason: 'database writes disabled',
      storage_source: 'mock_fallback',
    };

    renderContent(fallbackReceipt);

    expect(screen.getByText('database writes disabled')).toBeInTheDocument();
    expect(dependencyMocks.useAIResearchTaskByPollUrl).toHaveBeenCalledWith({
      pollUrl: taskReceipt.poll_url,
      enabled: false,
    });
  });

  it('轮询失败时显示数据库读取开关提示', () => {
    dependencyMocks.useAIResearchTaskByPollUrl.mockReturnValue(
      query({
        isError: true,
        error: new AIResearchPollError({
          code: 'ai_research_database_reads_disabled',
          message: 'database reads disabled',
          taskId: taskReceipt.task_id,
        }),
      }),
    );

    renderContent(taskReceipt);

    expect(
      screen.getByText(
        '后端数据库读取开关未开启，请在 .env 中开启 ENABLE_AI_RESEARCH_DATABASE_READS 后重启后端。',
      ),
    ).toBeInTheDocument();
  });

  it('轮询成功时显示任务结果摘要', () => {
    dependencyMocks.useAIResearchTaskByPollUrl.mockReturnValue(
      query({ data: { task_id: taskReceipt.task_id } }),
    );

    renderContent(taskReceipt);

    expect(
      screen.getByText('已读取到该 AI 研究任务的结果快照。'),
    ).toBeInTheDocument();
    expect(screen.getByText(/结果 ID：research-hk-001/)).toHaveTextContent(
      '证据：2 条',
    );
    expect(dependencyMocks.toAIResearchSnapshot).toHaveBeenCalledWith({
      task_id: taskReceipt.task_id,
    });
  });
});

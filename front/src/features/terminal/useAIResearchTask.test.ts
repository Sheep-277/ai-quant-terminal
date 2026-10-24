import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { createElement, type PropsWithChildren } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  AIResearchRequest,
  AIResearchResponse,
  AIResearchTaskCreateResponse,
} from './apiTypes';
import {
  aiResearchLLMCheckMutationKey,
  aiResearchLLMStatusQueryKey,
  aiResearchSearchCheckMutationKey,
  aiResearchSearchStatusQueryKey,
  aiResearchTaskByIdQueryKey,
  aiResearchTaskByPollUrlQueryKey,
  aiResearchTaskCreateMutationKey,
  aiResearchTaskQueryKey,
  useAIResearchLLMStatus,
  useAIResearchSearchStatus,
  useAIResearchTask,
  useAIResearchTaskById,
  useAIResearchTaskByPollUrl,
  useCheckAIResearchLLMConnection,
  useCheckAIResearchSearchConnection,
  useCreateAIResearchTask,
} from './useAIResearchTask';

const serviceMocks = vi.hoisted(() => ({
  checkAIResearchLLMConnection: vi.fn(),
  checkAIResearchSearchConnection: vi.fn(),
  createAIResearchTask: vi.fn(),
  getAIResearchLLMStatus: vi.fn(),
  getAIResearchSearchStatus: vi.fn(),
  getAIResearchTask: vi.fn(),
  getAIResearchTaskById: vi.fn(),
  getAIResearchTaskByPollUrl: vi.fn(),
}));

vi.mock('@/services/terminal/aiResearch', () => serviceMocks);

const researchResponse: AIResearchResponse = {
  task_id: 'research-hk-001',
  market: 'HK',
  query: '分析腾讯的基本面、估值和近期事件风险',
  status: 'completed',
  timestamp: '2026-10-16T02:05:00Z',
  timezone: 'Asia/Hong_Kong',
  data_status: 'delayed',
  trace: [],
  tool_calls: [],
  evidence: [],
  result: {
    headline: '估值合理，但需要关注事件风险。',
    direction: 'neutral',
    confidence: 0.78,
    horizon: 'risk_review',
    key_points: ['盈利保持稳定'],
    risk_flags: ['监管与行业竞争风险'],
    evidence_ids: [],
  },
};

const taskPayload: AIResearchRequest = {
  market: 'HK',
  query: researchResponse.query,
  symbols: ['00700.HK'],
  include_strategy_idea: true,
};

const taskReceipt: AIResearchTaskCreateResponse = {
  task_id: 'research-hk-001',
  market: 'HK',
  query: researchResponse.query,
  status: 'queued',
  accepted_at: '2026-10-16T02:00:00Z',
  timezone: 'Asia/Hong_Kong',
  data_status: 'delayed',
  poll_url: '/api/v1/research/tasks/research-hk-001',
  fallback_active: false,
  fallback_reason: null,
  storage_source: 'database',
};

const llmStatus = {
  enabled: true,
  configured: true,
  provider_name: 'bailian',
  model: 'qwen-plus',
  endpoint: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  missing_configuration: [],
  next_action: 'ready',
};

const llmCheck = {
  ok: true,
  provider_name: 'bailian',
  model: 'qwen-plus',
  endpoint: llmStatus.endpoint,
  response_preview: 'ok',
  error: null,
  next_action: 'ready',
};

const searchStatus = {
  provider_name: 'tavily',
  configured: true,
  api_key_configured: true,
  result_limit: 5,
  timeout_seconds: 10,
  missing_configuration: [],
  next_action: 'ready',
};

const searchCheck = {
  ok: true,
  provider_name: 'tavily',
  query: 'Tencent latest news',
  result_count: 3,
  response_preview: 'Tencent released its latest results.',
  error: null,
  next_action: 'ready',
};

let queryClient: QueryClient;

const wrapper = ({ children }: PropsWithChildren) =>
  createElement(QueryClientProvider, { client: queryClient }, children);

describe('useAIResearchTask', () => {
  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        mutations: { retry: false },
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    queryClient.clear();
  });

  it('为任务、轮询、LLM 和搜索源生成稳定缓存键', () => {
    expect(aiResearchTaskQueryKey('HK')).toEqual([
      'terminal',
      'ai-research',
      'HK',
    ]);
    expect(aiResearchTaskByIdQueryKey('research-hk-001')).toEqual([
      'terminal',
      'ai-research',
      'task',
      'research-hk-001',
    ]);
    expect(
      aiResearchTaskByPollUrlQueryKey('/api/v1/research/tasks/research-hk-001'),
    ).toEqual([
      'terminal',
      'ai-research',
      'poll',
      '/api/v1/research/tasks/research-hk-001',
    ]);
    expect(aiResearchTaskCreateMutationKey).toEqual([
      'terminal',
      'ai-research',
      'create',
    ]);
    expect(aiResearchLLMStatusQueryKey).toEqual([
      'terminal',
      'ai-research',
      'llm-status',
    ]);
    expect(aiResearchLLMCheckMutationKey).toEqual([
      'terminal',
      'ai-research',
      'llm-check',
    ]);
    expect(aiResearchSearchStatusQueryKey).toEqual([
      'terminal',
      'ai-research',
      'search-status',
    ]);
    expect(aiResearchSearchCheckMutationKey).toEqual([
      'terminal',
      'ai-research',
      'search-check',
    ]);
  });

  it('按市场加载研究任务并允许手动刷新', async () => {
    serviceMocks.getAIResearchTask.mockResolvedValue(researchResponse);
    const { result } = renderHook(() => useAIResearchTask({ market: 'HK' }), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(researchResponse);
    expect(serviceMocks.getAIResearchTask).toHaveBeenCalledWith({
      market: 'HK',
    });
    expect(
      queryClient
        .getQueryCache()
        .find({ queryKey: aiResearchTaskQueryKey('HK') })
        ?.observers[0]?.options.refetchInterval,
    ).toBe(60_000);

    await act(async () => {
      await result.current.refetch();
    });
    expect(serviceMocks.getAIResearchTask).toHaveBeenCalledTimes(2);
  });

  it('页面未启用时不读取市场级研究任务', () => {
    const { result } = renderHook(
      () => useAIResearchTask({ market: 'CN', enabled: false }),
      { wrapper },
    );

    expect(result.current.fetchStatus).toBe('idle');
    expect(serviceMocks.getAIResearchTask).not.toHaveBeenCalled();
  });

  it('任务 ID 有效后才读取指定研究结果', async () => {
    serviceMocks.getAIResearchTaskById.mockResolvedValue(researchResponse);
    const { result, rerender } = renderHook(
      ({ taskId }) => useAIResearchTaskById({ taskId }),
      { initialProps: { taskId: '' }, wrapper },
    );

    expect(result.current.fetchStatus).toBe('idle');
    expect(serviceMocks.getAIResearchTaskById).not.toHaveBeenCalled();

    rerender({ taskId: 'research-hk-001' });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(serviceMocks.getAIResearchTaskById).toHaveBeenCalledWith({
      taskId: 'research-hk-001',
    });
    expect(
      queryClient
        .getQueryCache()
        .find({ queryKey: aiResearchTaskByIdQueryKey('research-hk-001') })
        ?.observers[0]?.options.refetchInterval,
    ).toBe(30_000);
  });

  it('轮询地址有效后才按回执路径读取任务', async () => {
    const pollUrl = '/api/v1/research/tasks/research-hk-001';
    serviceMocks.getAIResearchTaskByPollUrl.mockResolvedValue(researchResponse);
    const { result, rerender } = renderHook(
      ({ currentPollUrl }) =>
        useAIResearchTaskByPollUrl({ pollUrl: currentPollUrl }),
      { initialProps: { currentPollUrl: '' }, wrapper },
    );

    expect(result.current.fetchStatus).toBe('idle');
    expect(serviceMocks.getAIResearchTaskByPollUrl).not.toHaveBeenCalled();

    rerender({ currentPollUrl: pollUrl });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(serviceMocks.getAIResearchTaskByPollUrl).toHaveBeenCalledWith({
      pollUrl,
    });
  });

  it('将创建任务参数原样交给 AI Research service', async () => {
    serviceMocks.createAIResearchTask.mockResolvedValue(taskReceipt);
    const { result } = renderHook(() => useCreateAIResearchTask(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync(taskPayload);
    });

    expect(serviceMocks.createAIResearchTask).toHaveBeenCalledWith(taskPayload);
    await waitFor(() => expect(result.current.data).toEqual(taskReceipt));
  });

  it('按启用状态读取 LLM 配置', async () => {
    serviceMocks.getAIResearchLLMStatus.mockResolvedValue(llmStatus);
    const { result, rerender } = renderHook(
      ({ enabled }) => useAIResearchLLMStatus(enabled),
      { initialProps: { enabled: false }, wrapper },
    );

    expect(result.current.fetchStatus).toBe('idle');
    expect(serviceMocks.getAIResearchLLMStatus).not.toHaveBeenCalled();

    rerender({ enabled: true });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(llmStatus);
    expect(serviceMocks.getAIResearchLLMStatus).toHaveBeenCalledTimes(1);
  });

  it('仅通过 Mutation 手动检查 LLM 连通性', async () => {
    serviceMocks.checkAIResearchLLMConnection.mockResolvedValue(llmCheck);
    const { result } = renderHook(() => useCheckAIResearchLLMConnection(), {
      wrapper,
    });

    expect(serviceMocks.checkAIResearchLLMConnection).not.toHaveBeenCalled();
    await act(async () => {
      await result.current.mutateAsync();
    });

    expect(serviceMocks.checkAIResearchLLMConnection).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(result.current.data).toEqual(llmCheck));
  });

  it('按启用状态读取搜索源配置', async () => {
    serviceMocks.getAIResearchSearchStatus.mockResolvedValue(searchStatus);
    const { result, rerender } = renderHook(
      ({ enabled }) => useAIResearchSearchStatus(enabled),
      { initialProps: { enabled: false }, wrapper },
    );

    expect(result.current.fetchStatus).toBe('idle');
    expect(serviceMocks.getAIResearchSearchStatus).not.toHaveBeenCalled();

    rerender({ enabled: true });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(searchStatus);
    expect(serviceMocks.getAIResearchSearchStatus).toHaveBeenCalledTimes(1);
  });

  it('仅通过 Mutation 手动检查搜索源连通性', async () => {
    serviceMocks.checkAIResearchSearchConnection.mockResolvedValue(searchCheck);
    const { result } = renderHook(() => useCheckAIResearchSearchConnection(), {
      wrapper,
    });

    expect(serviceMocks.checkAIResearchSearchConnection).not.toHaveBeenCalled();
    await act(async () => {
      await result.current.mutateAsync();
    });

    expect(serviceMocks.checkAIResearchSearchConnection).toHaveBeenCalledTimes(
      1,
    );
    await waitFor(() => expect(result.current.data).toEqual(searchCheck));
  });
});

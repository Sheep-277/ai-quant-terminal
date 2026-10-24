import { request } from '@umijs/max';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  AIResearchRequest,
  AIResearchResponse,
  AIResearchTaskCreateResponse,
} from '@/features/terminal/apiTypes';
import {
  AIResearchPollError,
  checkAIResearchLLMConnection,
  checkAIResearchSearchConnection,
  createAIResearchTask,
  getAIResearchLLMStatus,
  getAIResearchSearchStatus,
  getAIResearchTask,
  getAIResearchTaskById,
  getAIResearchTaskByPollUrl,
  type AIResearchLLMCheckResponse,
  type AIResearchLLMStatusResponse,
  type AIResearchSearchCheckResponse,
  type AIResearchSearchStatusResponse,
} from './aiResearch';

vi.mock('@umijs/max', () => ({
  request: vi.fn(),
}));

const taskPayload: AIResearchRequest = {
  market: 'HK',
  query: '分析腾讯的基本面、估值和近期事件风险',
  symbols: ['00700.HK'],
  include_strategy_idea: true,
};

const taskReceipt: AIResearchTaskCreateResponse = {
  task_id: 'research-hk-001',
  market: 'HK',
  query: taskPayload.query,
  status: 'queued',
  accepted_at: '2026-10-16T02:00:00Z',
  timezone: 'Asia/Hong_Kong',
  data_status: 'delayed',
  poll_url: '/api/v1/research/tasks/research-hk-001',
  fallback_active: false,
  fallback_reason: null,
  storage_source: 'database',
};

const researchResponse: AIResearchResponse = {
  task_id: 'research-hk-001',
  market: 'HK',
  query: taskPayload.query,
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

const llmStatus: AIResearchLLMStatusResponse = {
  enabled: true,
  configured: true,
  provider_name: 'bailian',
  model: 'qwen-plus',
  endpoint: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  missing_configuration: [],
  next_action: 'ready',
};

const llmCheck: AIResearchLLMCheckResponse = {
  ok: true,
  provider_name: 'bailian',
  model: 'qwen-plus',
  endpoint: llmStatus.endpoint,
  response_preview: 'ok',
  error: null,
  next_action: 'ready',
};

const searchStatus: AIResearchSearchStatusResponse = {
  provider_name: 'tavily',
  configured: true,
  api_key_configured: true,
  result_limit: 5,
  timeout_seconds: 10,
  missing_configuration: [],
  next_action: 'ready',
};

const searchCheck: AIResearchSearchCheckResponse = {
  ok: true,
  provider_name: 'tavily',
  query: 'Tencent latest news',
  result_count: 3,
  response_preview: 'Tencent released its latest results.',
  error: null,
  next_action: 'ready',
};

describe('AI Research service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('提交包含市场和股票代码的 AI 研究任务', async () => {
    vi.mocked(request).mockResolvedValue(taskReceipt);

    await expect(createAIResearchTask(taskPayload)).resolves.toEqual(taskReceipt);
    expect(request).toHaveBeenCalledWith('/api/v1/research/tasks', {
      method: 'POST',
      data: taskPayload,
    });
  });

  it('按市场读取默认 AI 研究任务', async () => {
    vi.mocked(request).mockResolvedValue(researchResponse);

    await expect(getAIResearchTask({ market: 'HK' })).resolves.toEqual(
      researchResponse,
    );
    expect(request).toHaveBeenCalledWith('/api/v1/research/task', {
      method: 'GET',
      params: { market: 'HK' },
    });
  });

  it('读取 LLM 配置状态但不触发模型调用', async () => {
    vi.mocked(request).mockResolvedValue(llmStatus);

    await expect(getAIResearchLLMStatus()).resolves.toEqual(llmStatus);
    expect(request).toHaveBeenCalledWith('/api/v1/research/llm/status', {
      method: 'GET',
    });
  });

  it('仅在手动检查时向 LLM 连通性路径发送 POST', async () => {
    vi.mocked(request).mockResolvedValue(llmCheck);

    await expect(checkAIResearchLLMConnection()).resolves.toEqual(llmCheck);
    expect(request).toHaveBeenCalledWith('/api/v1/research/llm/check', {
      method: 'POST',
    });
  });

  it('读取搜索源配置状态但不触发真实搜索', async () => {
    vi.mocked(request).mockResolvedValue(searchStatus);

    await expect(getAIResearchSearchStatus()).resolves.toEqual(searchStatus);
    expect(request).toHaveBeenCalledWith('/api/v1/research/search/status', {
      method: 'GET',
    });
  });

  it('仅在手动检查时向搜索源连通性路径发送 POST', async () => {
    vi.mocked(request).mockResolvedValue(searchCheck);

    await expect(checkAIResearchSearchConnection()).resolves.toEqual(searchCheck);
    expect(request).toHaveBeenCalledWith('/api/v1/research/search/check', {
      method: 'POST',
    });
  });

  it('对任务 ID 编码后读取指定研究任务', async () => {
    vi.mocked(request).mockResolvedValue(researchResponse);

    await getAIResearchTaskById({ taskId: 'research/HK?version=1' });

    expect(request).toHaveBeenCalledWith(
      '/api/v1/research/tasks/research%2FHK%3Fversion%3D1',
      {
        method: 'GET',
        skipErrorHandler: true,
      },
    );
  });

  it.each([
    '/api/v1/research/tasks/research-hk-001',
    '/api/v1/ai-research/tasks/research-hk-001',
  ])('允许使用站内 AI 研究轮询路径 %s', async (pollUrl) => {
    vi.mocked(request).mockResolvedValue(researchResponse);

    await expect(getAIResearchTaskByPollUrl({ pollUrl })).resolves.toEqual(
      researchResponse,
    );
    expect(request).toHaveBeenCalledWith(pollUrl, {
      method: 'GET',
      skipErrorHandler: true,
    });
  });

  it.each([
    'https://example.com/api/v1/research/tasks/research-hk-001',
    '/api/v2/research/tasks/research-hk-001',
    '/api/v1/research/task',
  ])('拒绝非项目任务轮询路径 %s', async (pollUrl) => {
    await expect(getAIResearchTaskByPollUrl({ pollUrl })).rejects.toMatchObject({
      name: 'AIResearchPollError',
      code: 'invalid_ai_research_poll_url',
      message: 'Invalid AI Research poll url.',
    });
    expect(request).not.toHaveBeenCalled();
  });

  it('将数据库读取关闭错误转为结构化轮询错误', async () => {
    vi.mocked(request).mockRejectedValue({
      response: {
        data: {
          detail: {
            code: 'ai_research_database_reads_disabled',
            message: 'AI Research database reads are disabled.',
            task_id: 'research-hk-001',
          },
        },
      },
    });

    const result = getAIResearchTaskById({ taskId: 'research-hk-001' });

    await expect(result).rejects.toBeInstanceOf(AIResearchPollError);
    await expect(result).rejects.toMatchObject({
      code: 'ai_research_database_reads_disabled',
      message: 'AI Research database reads are disabled.',
      taskId: 'research-hk-001',
    });
  });

  it('将任务不存在错误转为可识别的错误码', async () => {
    vi.mocked(request).mockRejectedValue({
      info: {
        data: {
          detail: {
            code: 'ai_research_task_not_found',
            message: 'AI Research task was not found.',
            task_id: 'missing-research',
          },
        },
      },
    });

    await expect(
      getAIResearchTaskByPollUrl({
        pollUrl: '/api/v1/research/tasks/missing-research',
      }),
    ).rejects.toMatchObject({
      name: 'AIResearchPollError',
      code: 'ai_research_task_not_found',
      message: 'AI Research task was not found.',
      taskId: 'missing-research',
    });
  });

  it('保留未分类轮询错误的原始消息', async () => {
    vi.mocked(request).mockRejectedValue(new Error('network timeout'));

    await expect(
      getAIResearchTaskByPollUrl({
        pollUrl: '/api/v1/research/tasks/research-hk-001',
      }),
    ).rejects.toMatchObject({
      name: 'AIResearchPollError',
      code: 'ai_research_poll_request_failed',
      message: 'network timeout',
    });
  });
});

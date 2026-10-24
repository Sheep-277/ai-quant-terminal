import { request } from '@umijs/max';
import type {
  AIResearchRequest,
  AIResearchResponse,
  AIResearchTaskCreateResponse,
} from '@/features/terminal/apiTypes';
import type { MarketCode } from '@/features/terminal/types';

export type GetAIResearchTaskParams = {
  market: MarketCode;
};

export type GetAIResearchTaskByIdParams = {
  taskId: string;
};

export type GetAIResearchTaskByPollUrlParams = {
  pollUrl: string;
};

export type CreateAIResearchTaskParams = AIResearchRequest;

export type AIResearchLLMStatusResponse = {
  enabled: boolean;
  configured: boolean;
  provider_name: string;
  model: string;
  endpoint: string | null;
  missing_configuration: string[];
  next_action: string;
};

export type AIResearchLLMCheckResponse = {
  ok: boolean;
  provider_name: string;
  model: string;
  endpoint: string | null;
  response_preview: string | null;
  error: string | null;
  next_action: string;
};

export type AIResearchSearchStatusResponse = {
  provider_name: string;
  configured: boolean;
  api_key_configured: boolean;
  result_limit: number;
  timeout_seconds: number;
  missing_configuration: string[];
  next_action: string;
};

export type AIResearchSearchCheckResponse = {
  ok: boolean;
  provider_name: string;
  query: string;
  result_count: number;
  response_preview: string | null;
  error: string | null;
  next_action: string;
};

export type AIResearchPollErrorCode =
  | 'ai_research_database_reads_disabled'
  | 'ai_research_task_not_found'
  | 'invalid_ai_research_poll_url'
  | 'ai_research_poll_request_failed';

type AIResearchErrorDetail = {
  code?: string;
  message?: string;
  task_id?: string;
};

export class AIResearchPollError extends Error {
  code: AIResearchPollErrorCode;
  taskId?: string;

  constructor({
    code,
    message,
    taskId,
  }: {
    code: AIResearchPollErrorCode;
    message: string;
    taskId?: string;
  }) {
    super(message);
    this.name = 'AIResearchPollError';
    this.code = code;
    this.taskId = taskId;
  }
}

export async function createAIResearchTask(payload: CreateAIResearchTaskParams) {
  // 当前 POST 只创建 Mock 接收回执，不启动真实 LangGraph、Celery 或 LLM。
  return request<AIResearchTaskCreateResponse>('/api/v1/research/tasks', {
    method: 'POST',
    data: payload,
  });
}

export async function getAIResearchTask({ market }: GetAIResearchTaskParams) {
  // AI Research 当前读取 Mock 任务，后续接入真实 Orchestrator 时保持页面调用稳定。
  return request<AIResearchResponse>('/api/v1/research/task', {
    method: 'GET',
    params: { market },
  });
}

export async function getAIResearchLLMStatus() {
  // 只读取 LLM 配置状态，不触发真实百炼调用。
  return request<AIResearchLLMStatusResponse>('/api/v1/research/llm/status', {
    method: 'GET',
  });
}

export async function checkAIResearchLLMConnection() {
  // 显式触发一次百炼最小连通性检查；只有用户点击时才调用。
  return request<AIResearchLLMCheckResponse>('/api/v1/research/llm/check', {
    method: 'POST',
  });
}

export async function getAIResearchSearchStatus() {
  // 只读取公开搜索源配置状态，不触发 Tavily/SerpAPI 真实搜索请求。
  return request<AIResearchSearchStatusResponse>('/api/v1/research/search/status', {
    method: 'GET',
  });
}

export async function checkAIResearchSearchConnection() {
  // 显式触发一次公开搜索源最小连通性检查；只有用户点击时才调用。
  return request<AIResearchSearchCheckResponse>('/api/v1/research/search/check', {
    method: 'POST',
  });
}

export async function getAIResearchTaskById({ taskId }: GetAIResearchTaskByIdParams) {
  // poll_url 对应的精确查询入口，用于读取某一次 AI Research 任务结果。
  return requestAIResearchTaskByPath(`/api/v1/research/tasks/${encodeURIComponent(taskId)}`);
}

export async function getAIResearchTaskByPollUrl({ pollUrl }: GetAIResearchTaskByPollUrlParams) {
  // 后端回执只允许站内任务路径；这里做前端保护，避免误请求外部地址。
  if (!pollUrl.startsWith('/api/v1/research/tasks/') && !pollUrl.startsWith('/api/v1/ai-research/tasks/')) {
    throw new AIResearchPollError({
      code: 'invalid_ai_research_poll_url',
      message: 'Invalid AI Research poll url.',
    });
  }

  return requestAIResearchTaskByPath(pollUrl);
}

async function requestAIResearchTaskByPath(path: string) {
  try {
    return await request<AIResearchResponse>(path, {
      method: 'GET',
      skipErrorHandler: true,
    });
  } catch (error) {
    throw toAIResearchPollError(error);
  }
}

function toAIResearchPollError(error: unknown) {
  const detail = extractAIResearchErrorDetail(error);
  if (detail?.code === 'ai_research_database_reads_disabled') {
    return new AIResearchPollError({
      code: 'ai_research_database_reads_disabled',
      message: detail.message ?? 'AI Research database reads are disabled.',
      taskId: detail.task_id,
    });
  }
  if (detail?.code === 'ai_research_task_not_found') {
    return new AIResearchPollError({
      code: 'ai_research_task_not_found',
      message: detail.message ?? 'AI Research task was not found.',
      taskId: detail.task_id,
    });
  }

  return new AIResearchPollError({
    code: 'ai_research_poll_request_failed',
    message: error instanceof Error ? error.message : 'AI Research poll request failed.',
  });
}

function extractAIResearchErrorDetail(error: unknown): AIResearchErrorDetail | undefined {
  if (!isRecord(error)) {
    return undefined;
  }

  const response = error.response;
  if (isRecord(response) && isRecord(response.data) && isRecord(response.data.detail)) {
    return response.data.detail;
  }

  const data = error.data;
  if (isRecord(data) && isRecord(data.detail)) {
    return data.detail;
  }

  const info = error.info;
  if (isRecord(info) && isRecord(info.data) && isRecord(info.data.detail)) {
    return info.data.detail;
  }

  return undefined;
}

function isRecord(value: unknown): value is Record<string, any> {
  return typeof value === 'object' && value !== null;
}

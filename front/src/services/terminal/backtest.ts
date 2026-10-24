import { request } from '@umijs/max';
import type {
  BacktestRequest,
  BacktestResponse,
  BacktestTaskCreateResponse,
} from '@/features/terminal/apiTypes';
import type { MarketCode } from '@/features/terminal/types';

export type GetBacktestResultParams = {
  market: MarketCode;
};

export type GetBacktestByIdParams = {
  backtestId: string;
};

export type GetBacktestByPollUrlParams = {
  pollUrl: string;
};

export type CreateBacktestTaskParams = BacktestRequest;

export type BacktestPollErrorCode =
  | 'backtest_database_reads_disabled'
  | 'backtest_result_not_found'
  | 'invalid_backtest_poll_url'
  | 'backtest_poll_request_failed';

type BacktestErrorDetail = {
  code?: string;
  message?: string;
  backtest_id?: string;
};

export class BacktestPollError extends Error {
  code: BacktestPollErrorCode;
  backtestId?: string;

  constructor({
    code,
    message,
    backtestId,
  }: {
    code: BacktestPollErrorCode;
    message: string;
    backtestId?: string;
  }) {
    super(message);
    this.name = 'BacktestPollError';
    this.code = code;
    this.backtestId = backtestId;
  }
}

export async function createBacktestTask(payload: CreateBacktestTaskParams) {
  // 当前 POST 只创建 Mock 回测任务回执，不启动真实异步队列或历史行情读取。
  return request<BacktestTaskCreateResponse>('/api/v1/backtests', {
    method: 'POST',
    data: payload,
  });
}

export async function getBacktestResult({ market }: GetBacktestResultParams) {
  // Backtest 页面通过服务层访问后端，避免组件直接维护 API 路径。
  return request<BacktestResponse>('/api/v1/backtest/result', {
    method: 'GET',
    params: { market },
  });
}

export async function getBacktestById({ backtestId }: GetBacktestByIdParams) {
  // poll_url 对应的查询入口，用于读取某一次回测任务保存后的结果快照。
  return requestBacktestResultByPath(`/api/v1/backtests/${encodeURIComponent(backtestId)}`);
}

export async function getBacktestByPollUrl({ pollUrl }: GetBacktestByPollUrlParams) {
  // 后端回执只允许相对路径；这里仍做一次前端保护，避免误请求外部地址。
  if (!pollUrl.startsWith('/api/v1/backtests/')) {
    throw new BacktestPollError({
      code: 'invalid_backtest_poll_url',
      message: 'Invalid backtest poll url.',
    });
  }

  return requestBacktestResultByPath(pollUrl);
}

async function requestBacktestResultByPath(path: string) {
  try {
    return await request<BacktestResponse>(path, {
      method: 'GET',
      skipErrorHandler: true,
    });
  } catch (error) {
    throw toBacktestPollError(error);
  }
}

function toBacktestPollError(error: unknown) {
  const detail = extractBacktestErrorDetail(error);
  if (detail?.code === 'backtest_database_reads_disabled') {
    return new BacktestPollError({
      code: 'backtest_database_reads_disabled',
      message: detail.message ?? 'Backtest database reads are disabled.',
      backtestId: detail.backtest_id,
    });
  }
  if (detail?.code === 'backtest_result_not_found') {
    return new BacktestPollError({
      code: 'backtest_result_not_found',
      message: detail.message ?? 'Backtest result was not found.',
      backtestId: detail.backtest_id,
    });
  }

  return new BacktestPollError({
    code: 'backtest_poll_request_failed',
    message: error instanceof Error ? error.message : 'Backtest poll request failed.',
  });
}

function extractBacktestErrorDetail(error: unknown): BacktestErrorDetail | undefined {
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

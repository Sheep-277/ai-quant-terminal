import { request } from '@umijs/max';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  BacktestRequest,
  BacktestResponse,
  BacktestTaskCreateResponse,
} from '@/features/terminal/apiTypes';
import {
  BacktestPollError,
  createBacktestTask,
  getBacktestById,
  getBacktestByPollUrl,
  getBacktestResult,
} from './backtest';

vi.mock('@umijs/max', () => ({
  request: vi.fn(),
}));

const backtestPayload: BacktestRequest = {
  market: 'HK',
  strategy_id: 'strategy-hk-quality-001',
  strategy_status: 'confirmed',
  data_mode: 'historical',
  start_date: '2025-01-01',
  end_date: '2025-12-31',
  sample_split_at: null,
  initial_capital: 500_000,
  benchmark: 'Hang Seng TECH',
  transaction_fee_rate: 0.0005,
  slippage_rate: 0.0005,
};

const taskResponse: BacktestTaskCreateResponse = {
  backtest_id: 'backtest-hk-001',
  strategy_id: 'strategy-hk-quality-001',
  market: 'HK',
  status: 'pending',
  accepted_at: '2026-10-16T02:00:00Z',
  data_mode: 'historical',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  poll_url: '/api/v1/backtests/backtest-hk-001',
  data_status: 'delayed',
  fallback_active: false,
  fallback_reason: null,
  storage_source: 'database',
  result_data_mode: null,
};

const backtestResponse: BacktestResponse = {
  backtest_id: 'backtest-hk-001',
  strategy_id: 'strategy-hk-quality-001',
  market: 'HK',
  status: 'completed',
  data_mode: 'historical',
  timestamp: '2026-10-16T02:05:00Z',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  benchmark: 'Hang Seng TECH',
  start_date: '2025-01-01',
  end_date: '2025-12-31',
  performance: {
    initial_capital: 500_000,
    final_value: 560_000,
    total_return: 0.12,
    annualized_return: 0.12,
    benchmark_return: 0.08,
    maximum_drawdown: 0.09,
    sharpe_ratio: 1.35,
    win_rate: 0.58,
    trade_count: 24,
  },
  equity_curve: [],
  trades: [],
  assumptions: [],
};

describe('backtest service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('向回测创建路径提交任务参数', async () => {
    vi.mocked(request).mockResolvedValue(taskResponse);

    await expect(createBacktestTask(backtestPayload)).resolves.toEqual(
      taskResponse,
    );
    expect(request).toHaveBeenCalledWith('/api/v1/backtests', {
      method: 'POST',
      data: backtestPayload,
    });
  });

  it('按市场请求默认回测结果', async () => {
    vi.mocked(request).mockResolvedValue(backtestResponse);

    await expect(getBacktestResult({ market: 'HK' })).resolves.toEqual(
      backtestResponse,
    );
    expect(request).toHaveBeenCalledWith('/api/v1/backtest/result', {
      method: 'GET',
      params: { market: 'HK' },
    });
  });

  it('对回测任务 ID 编码后请求详情', async () => {
    vi.mocked(request).mockResolvedValue(backtestResponse);

    await getBacktestById({ backtestId: 'task/HK?version=1' });

    expect(request).toHaveBeenCalledWith(
      '/api/v1/backtests/task%2FHK%3Fversion%3D1',
      {
        method: 'GET',
        skipErrorHandler: true,
      },
    );
  });

  it('使用后端回执中的合法相对路径轮询结果', async () => {
    const pollUrl = '/api/v1/backtests/backtest-hk-001';
    vi.mocked(request).mockResolvedValue(backtestResponse);

    await expect(getBacktestByPollUrl({ pollUrl })).resolves.toEqual(
      backtestResponse,
    );
    expect(request).toHaveBeenCalledWith(pollUrl, {
      method: 'GET',
      skipErrorHandler: true,
    });
  });

  it.each([
    'https://example.com/api/v1/backtests/backtest-hk-001',
    '/api/v2/backtests/backtest-hk-001',
  ])('拒绝非项目回测路径 %s', async (pollUrl) => {
    await expect(getBacktestByPollUrl({ pollUrl })).rejects.toMatchObject({
      name: 'BacktestPollError',
      code: 'invalid_backtest_poll_url',
      message: 'Invalid backtest poll url.',
    });
    expect(request).not.toHaveBeenCalled();
  });

  it('将数据库读取关闭错误转为结构化轮询错误', async () => {
    vi.mocked(request).mockRejectedValue({
      response: {
        data: {
          detail: {
            code: 'backtest_database_reads_disabled',
            message: 'Backtest database reads are disabled by configuration.',
            backtest_id: 'backtest-hk-001',
          },
        },
      },
    });

    const result = getBacktestById({ backtestId: 'backtest-hk-001' });

    await expect(result).rejects.toBeInstanceOf(BacktestPollError);
    await expect(result).rejects.toMatchObject({
      code: 'backtest_database_reads_disabled',
      message: 'Backtest database reads are disabled by configuration.',
      backtestId: 'backtest-hk-001',
    });
  });

  it('将回测结果不存在错误转为可识别的错误码', async () => {
    vi.mocked(request).mockRejectedValue({
      info: {
        data: {
          detail: {
            code: 'backtest_result_not_found',
            message: 'Backtest result was not found.',
            backtest_id: 'missing-backtest',
          },
        },
      },
    });

    await expect(
      getBacktestByPollUrl({
        pollUrl: '/api/v1/backtests/missing-backtest',
      }),
    ).rejects.toMatchObject({
      name: 'BacktestPollError',
      code: 'backtest_result_not_found',
      message: 'Backtest result was not found.',
      backtestId: 'missing-backtest',
    });
  });

  it('保留未分类请求错误的原始消息', async () => {
    vi.mocked(request).mockRejectedValue(new Error('network timeout'));

    await expect(
      getBacktestByPollUrl({
        pollUrl: '/api/v1/backtests/backtest-hk-001',
      }),
    ).rejects.toMatchObject({
      name: 'BacktestPollError',
      code: 'backtest_poll_request_failed',
      message: 'network timeout',
    });
  });
});

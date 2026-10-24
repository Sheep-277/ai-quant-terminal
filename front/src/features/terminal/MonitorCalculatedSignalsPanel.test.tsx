import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { App } from 'antd';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import enUS from '../../locales/en-US/terminal';
import zhCN from '../../locales/zh-CN/terminal';
import type { MonitorCalculatedSignalsResponse } from './apiTypes';
import { formatDateTime } from './formatters';
import { MonitorCalculatedSignalsPanel } from './MonitorCalculatedSignalsPanel';
import type { MarketCode } from './types';

const mocks = vi.hoisted(() => ({ service: vi.fn(), locale: 'zh-CN' }));
vi.mock('@ant-design/icons', () => ({ CalculatorOutlined: () => null, StopOutlined: () => null }));
vi.mock('@/services/terminal/monitor', () => ({
  getMonitorCalculatedSignals: mocks.service,
}));
vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: mocks.locale,
    formatMessage: (
      { id }: { id: string },
      values: Record<string, string | number> = {},
    ) =>
      Object.entries(values).reduce(
        (message, [key, value]) =>
          message.replaceAll(`{${key}}`, String(value)),
        (mocks.locale === 'en-US' ? enUS : zhCN)[id as keyof typeof zhCN] ?? id,
      ),
  }),
}));

const response: MonitorCalculatedSignalsResponse = {
  market: 'US',
  symbol: 'NVDA',
  timezone: 'America/New_York',
  currency: 'USD',
  source: 'yahoo_finance',
  data_status: 'delayed',
  timestamp: '2026-10-20T13:30:00Z',
  bar_count: 65,
  calculation_scope: 'price_only',
  signals: [
    {
      code: 'momentum_weakness',
      title: '20D momentum weakened',
      direction: 'negative',
      severity: 'warning',
      score: 0.6042,
      evidence: ['momentum_20d=-0.0542'],
    },
  ],
};
let client: QueryClient;
const content = (market: MarketCode = 'US') => (
  <QueryClientProvider client={client}>
    <App>
      <MonitorCalculatedSignalsPanel market={market} />
    </App>
  </QueryClientProvider>
);
const enterSymbol = (symbol = 'NVDA') =>
  fireEvent.change(screen.getByLabelText('股票代码'), {
    target: { value: symbol },
  });
const run = () =>
  fireEvent.click(screen.getByRole('button', { name: '计算信号' }));

beforeEach(() => {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  mocks.locale = 'zh-CN';
  mocks.service.mockReset();
});
afterEach(() => {
  cleanup();
  client.clear();
});

describe('MonitorCalculatedSignalsPanel', () => {
  it('初始不请求，空标的和非法标的不能提交', () => {
    render(content());
    expect(screen.getByText('尚未计算')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '计算信号' })).toBeDisabled();
    enterSymbol('NVDA/AAPL');
    expect(screen.getByRole('alert')).toHaveTextContent('请输入单个股票代码');
    expect(screen.getByRole('button', { name: '计算信号' })).toBeDisabled();
    expect(mocks.service).not.toHaveBeenCalled();
  });

  it('手动请求后展示来源、时间、样本数和中文信号', async () => {
    mocks.service.mockResolvedValue(response);
    render(content());
    enterSymbol(' nvda ');
    expect(mocks.service).not.toHaveBeenCalled();
    run();
    expect(await screen.findByText('20 日动量转弱')).toBeInTheDocument();
    expect(mocks.service).toHaveBeenCalledWith(
      { market: 'US', symbol: 'NVDA' },
      { signal: expect.any(AbortSignal) },
    );
    expect(screen.getByText('US / NVDA')).toBeInTheDocument();
    expect(screen.getByText('65')).toBeInTheDocument();
    expect(
      screen.getByText(
        formatDateTime(response.timestamp, {
          timezone: response.timezone,
          locale: 'zh-CN',
        }),
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('momentum_20d=-0.0542')).toBeInTheDocument();
    expect(screen.getByText('60.42%')).toBeInTheDocument();
    expect(screen.queryByText('20D momentum weakened')).not.toBeInTheDocument();
  });

  it('空结果显示未命中，不填入Seed信号', async () => {
    mocks.service.mockResolvedValue({ ...response, signals: [] });
    render(content());
    enterSymbol();
    run();
    expect(
      await screen.findByText('本次价格规则未命中信号'),
    ).toBeInTheDocument();
    expect(screen.queryByText('20 日动量转弱')).not.toBeInTheDocument();
  });

  it('等待时可取消，取消后不显示晚到结果', async () => {
    let resolve!: (value: MonitorCalculatedSignalsResponse) => void;
    const pending = new Promise<MonitorCalculatedSignalsResponse>(
      (complete) => {
        resolve = complete;
      },
    );
    mocks.service.mockReturnValue(pending);
    render(content());
    enterSymbol();
    run();
    await screen.findByText('正在读取公开日 K 线并计算…');
    fireEvent.click(screen.getByRole('button', { name: '取消计算' }));
    await screen.findByText('已取消等待，后端计算可能仍在结束中。');
    expect(mocks.service.mock.calls[0][1].signal.aborted).toBe(true);
    await act(async () => {
      resolve(response);
      await pending;
    });
    expect(screen.queryByText('US / NVDA')).not.toBeInTheDocument();
  });

  it('刷新失败保留旧结果并明确提示，原时间不变', async () => {
    mocks.service
      .mockResolvedValueOnce(response)
      .mockRejectedValueOnce(new Error('503'));
    render(content());
    enterSymbol();
    run();
    await screen.findByText('20 日动量转弱');
    run();
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(
        '以下保留上次成功结果',
      ),
    );
    expect(screen.getByText('20 日动量转弱')).toBeInTheDocument();
    expect(
      screen.getByText(
        formatDateTime(response.timestamp, {
          timezone: response.timezone,
          locale: 'zh-CN',
        }),
      ),
    ).toBeInTheDocument();
  });

  it('超时显示中文错误，不暴露原始异常或模拟替代结果', async () => {
    mocks.service.mockRejectedValue(
      Object.assign(new Error('secret-url'), { code: 'ECONNABORTED' }),
    );
    render(content());
    enterSymbol();
    run();
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('请求超时'),
    );
    expect(screen.queryByText(/secret-url/)).not.toBeInTheDocument();
    expect(screen.queryByText('US / NVDA')).not.toBeInTheDocument();
  });

  it('切换市场重置输入和结果，不自动请求', async () => {
    mocks.service.mockResolvedValue(response);
    const view = render(content());
    enterSymbol();
    run();
    await screen.findByText('20 日动量转弱');
    view.rerender(content('HK'));
    expect(screen.getByLabelText('股票代码')).toHaveValue('');
    expect(screen.queryByText('US / NVDA')).not.toBeInTheDocument();
    expect(mocks.service).toHaveBeenCalledTimes(1);
  });

  it('编辑标的不显示旧标的结果，不自动请求新代码', async () => {
    mocks.service.mockResolvedValue(response);
    render(content());
    enterSymbol();
    run();
    await screen.findByText('20 日动量转弱');
    enterSymbol('AAPL');
    expect(screen.queryByText('US / NVDA')).not.toBeInTheDocument();
    expect(mocks.service).toHaveBeenCalledTimes(1);
  });

  it('响应标的不匹配时拒绝展示', async () => {
    mocks.service.mockResolvedValue({ ...response, symbol: 'AAPL' });
    render(content());
    enterSymbol();
    run();
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(
        '响应市场或标的与当前选择不一致',
      ),
    );
    expect(screen.queryByText('US / AAPL')).not.toBeInTheDocument();
  });

  it('英文环境显示本地化状态及信号名称', async () => {
    mocks.locale = 'en-US';
    mocks.service.mockResolvedValue(response);
    render(content());
    fireEvent.change(screen.getByLabelText('Stock symbol'), {
      target: { value: 'NVDA' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Calculate signals' }));
    expect(
      await screen.findByText('20-day momentum weakened'),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/terminal\.monitor\.calculation/),
    ).not.toBeInTheDocument();
  });
});

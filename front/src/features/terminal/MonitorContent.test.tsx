import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';
import { App } from 'antd';
import { afterEach, describe, expect, it, vi } from 'vitest';
import zhCN from '../../locales/zh-CN/terminal';
import enUS from '../../locales/en-US/terminal';
import { MonitorContent } from './MonitorContent';
import type { MonitorSnapshot } from './types';

const localeState = vi.hoisted(() => ({ locale: 'zh-CN' }));

vi.mock('./MonitorCalculatedSignalsPanel', () => ({
  MonitorCalculatedSignalsPanel: ({ market }: { market: string }) => <section data-testid="monitor-calculation-panel">{market}</section>,
}));

vi.mock('@ant-design/icons', () => ({
  ApiOutlined: () => null,
  ThunderboltOutlined: () => null,
}));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: localeState.locale,
    formatMessage: (
      { id }: { id: string },
      values: Record<string, string | number> = {},
    ) =>
      Object.entries(values).reduce(
        (message, [key, value]) =>
          message.replaceAll(`{${key}}`, String(value)),
        (localeState.locale === 'en-US' ? enUS : zhCN)[id as keyof typeof zhCN] ?? id,
      ),
  }),
}));

const monitor: MonitorSnapshot = {
  market: 'HK',
  timestamp: '2026-10-16T02:10:00Z',
  timezone: 'Asia/Hong_Kong',
  currency: 'HKD',
  stream: {
    status: 'connected',
    latencyMs: 86,
    lastHeartbeatAt: '2026-10-16T02:09:58Z',
    reconnectAttempts: 0,
    dataStatus: 'realtime',
  },
  streamMetrics: [
    { labelId: 'terminal.metric.latencyMs', value: 86, tone: 'positive' },
    {
      labelId: 'terminal.metric.reconnectAttempts',
      value: 0,
      tone: 'positive',
    },
    { labelId: 'terminal.metric.signalCount', value: 3, tone: 'accent' },
    { labelId: 'terminal.metric.eventCount', value: 4, tone: 'accent' },
  ],
  signals: [
    {
      key: 'signal-info',
      signalId: 'signal-info',
      market: 'HK',
      symbol: '00700.HK',
      title: '成交量温和放大',
      direction: 'positive',
      severity: 'info',
      score: 0.68,
      triggeredAt: '2026-10-16T02:06:00Z',
      evidence: ['volume_ratio=1.3'],
    },
    {
      key: 'signal-warning',
      signalId: 'signal-warning',
      market: 'HK',
      symbol: '03690.HK',
      title: '波动率快速上升',
      direction: 'warning',
      severity: 'warning',
      score: 0.79,
      triggeredAt: '2026-10-16T02:07:00Z',
      evidence: ['volatility_20d=0.42'],
    },
    {
      key: 'signal-critical',
      signalId: 'signal-critical',
      market: 'HK',
      symbol: '09988.HK',
      title: '价格跌破风险阈值',
      direction: 'negative',
      severity: 'critical',
      score: 0.93,
      triggeredAt: '2026-10-16T02:08:00Z',
      evidence: ['drawdown=-0.12'],
    },
  ],
  events: [
    {
      key: 'event-fast',
      eventId: 'event-fast',
      market: 'HK',
      source: 'FAST_PATH',
      title: '盘口波动加速',
      summary: '短时成交量与价格波动同步扩大。',
      impact: 'warning',
      confidence: 0.84,
      createdAt: '2026-10-16T02:05:00Z',
    },
    {
      key: 'event-ai',
      eventId: 'event-ai',
      market: 'HK',
      source: 'AI_PATH',
      title: '新闻事件完成映射',
      summary: '公开新闻已关联至互联网板块。',
      impact: 'neutral',
      confidence: 0.76,
      createdAt: '2026-10-16T02:06:00Z',
    },
    {
      key: 'event-risk',
      eventId: 'event-risk',
      market: 'HK',
      source: 'RISK_ENGINE',
      title: '集中度风险提示',
      summary: '单一标的权重接近组合限制。',
      impact: 'warning',
      confidence: 0.91,
      createdAt: '2026-10-16T02:07:00Z',
    },
    {
      key: 'event-provider',
      eventId: 'event-provider',
      market: 'HK',
      source: 'PROVIDER',
      title: '行情源延迟升高',
      summary: '公开行情响应时间超过监控阈值。',
      impact: 'warning',
      confidence: 1,
      createdAt: '2026-10-16T02:08:00Z',
    },
  ],
};

const renderMonitor = (snapshot: MonitorSnapshot = monitor) =>
  render(
    <App>
      <MonitorContent monitor={snapshot} />
    </App>,
  );

const getSignalPanel = () => {
  const heading = screen.getByRole('heading', { name: '信号集' });
  const panel = heading.closest('.terminal-panel');
  if (!(panel instanceof HTMLElement)) {
    throw new Error('Signal panel was not rendered.');
  }
  return panel;
};

afterEach(() => { cleanup(); localeState.locale = 'zh-CN'; });

describe('MonitorContent', () => {
  it('信号表显示结构化分类和原始来源，证据不决定分类', () => {
    renderMonitor({ ...monitor, signals: [
      { ...monitor.signals[0], source: 'mock_seed', dataOrigin: 'seed' },
      { ...monitor.signals[1], source: 'mock_quant_pipeline', dataOrigin: 'mock' },
      { ...monitor.signals[2], source: 'yahoo_finance', evidence: ['source=mock_seed'] },
    ] });
    expect(screen.getByRole('columnheader', { name: '信号来源' })).toBeInTheDocument();
    expect(screen.getByText('Seed 样例 / mock_seed')).toBeInTheDocument();
    expect(screen.getByText('Mock 模拟 / mock_quant_pipeline')).toBeInTheDocument();
    expect(screen.getByText('来源未验证 / yahoo_finance')).toBeInTheDocument();
  });

  it('英文逐条来源与缺失来源均本地化', () => {
    localeState.locale = 'en-US';
    renderMonitor({ ...monitor, signals: [
      { ...monitor.signals[0], source: 'mock_seed', dataOrigin: 'seed' },
      { ...monitor.signals[1] },
    ] });
    expect(screen.getByText('Seed sample / mock_seed')).toBeInTheDocument();
    expect(screen.getByText('Unverified origin / Not provided')).toBeInTheDocument();
  });

  it('模拟快照显示模拟状态而非实时或延迟', () => {
    renderMonitor({ ...monitor, stream: { ...monitor.stream, dataStatus: 'mock' } });
    expect(screen.getByText('数据状态：模拟数据')).toBeInTheDocument();
    expect(screen.getByText(/快照记录连接正常/)).toHaveTextContent('数据状态为 模拟数据');
    expect(screen.queryByText('数据状态：实时数据')).not.toBeInTheDocument();
    expect(screen.queryByText('数据状态：延迟数据')).not.toBeInTheDocument();
  });

  it('英文环境显示模拟数据状态译文', () => {
    localeState.locale = 'en-US';
    renderMonitor({ ...monitor, stream: { ...monitor.stream, dataStatus: 'mock' } });
    expect(screen.getByText('Data status: Simulated data')).toBeInTheDocument();
  });

  it('显示分区来源，数据库信号不冒充真实行情', () => {
    renderMonitor({ ...monitor, provenance: {
      transport: 'rest_polling', streamSource: 'mock', signalSource: 'database', eventSource: 'mixed', heartbeatBasis: 'latest_signal',
    } });
    const source = screen.getByText(/连接状态来源：/);
    expect(source).toHaveTextContent('连接状态来源：Mock 模拟');
    expect(source).toHaveTextContent('信号来源：数据库（可能含 Seed 模拟记录）');
    expect(source).toHaveTextContent('事件来源：模拟与系统事件混合');
    expect(source).toHaveTextContent('心跳口径：最新信号时间');
    expect(source).toHaveTextContent('传输方式：REST 轮询');
  });

  it('旧快照显示未知来源而非自动认定为 Mock 或数据库', () => {
    renderMonitor();
    expect(screen.getByText(/连接状态来源：/)).toHaveTextContent('信号来源：来源未知');
    expect(screen.getByText(/连接状态来源：/)).toHaveTextContent('心跳口径：口径未知');
  });

  it('英文环境显示来源译文而非 locale key', () => {
    localeState.locale = 'en-US';
    renderMonitor({ ...monitor, provenance: {
      transport: 'rest_polling', streamSource: 'mock', signalSource: 'mock', eventSource: 'mock', heartbeatBasis: 'mock_clock',
    } });
    expect(screen.getByText(/Connection status source:/)).toHaveTextContent('signal source: Mock simulation');
    expect(screen.getByText(/Connection status source:/)).toHaveTextContent('heartbeat basis: Simulated clock');
    expect(screen.queryByText(/terminal\.monitor\./)).not.toBeInTheDocument();
  });

  it('状态摘要位于表格上方且表格不再嵌在左右分栏中', () => {
    const { container } = renderMonitor();
    const workspace = container.querySelector('.terminal-monitor-workspace');
    const overview = container.querySelector('.terminal-monitor-overview');
    expect(workspace?.children).toHaveLength(3);
    expect(screen.getByTestId('monitor-calculation-panel')).toHaveTextContent('HK');
    expect(overview?.children).toHaveLength(2);
    expect(
      overview?.querySelector('.terminal-monitor-connection'),
    ).not.toBeNull();
    expect(
      overview?.querySelector('.terminal-monitor-risk-summary'),
    ).not.toBeNull();
    expect(workspace?.children[2]).toHaveClass('terminal-monitor-tables');
    expect(
      getSignalPanel().closest('.terminal-monitor-tables')?.parentElement,
    ).toBe(workspace);
    expect(workspace?.querySelector('.ant-col')).toBeNull();
  });

  it('监控快照刷新后保留筛选并更新表格内容', () => {
    const view = renderMonitor();
    const panel = getSignalPanel();
    fireEvent.click(
      within(panel).getByText('严重', {
        selector: '.ant-segmented-item-label',
      }),
    );
    view.rerender(
      <App>
        <MonitorContent
          monitor={{
            ...monitor,
            signals: monitor.signals.map((signal) =>
              signal.severity === 'critical'
                ? { ...signal, title: '刷新后的风险信号' }
                : signal,
            ),
          }}
        />
      </App>,
    );
    expect(
      within(panel).getByText('信号：显示 1 / 共 3 条'),
    ).toBeInTheDocument();
    expect(within(panel).getByText('刷新后的风险信号')).toBeInTheDocument();
    expect(within(panel).queryByText('成交量温和放大')).not.toBeInTheDocument();
  });

  it('展示实时流健康状态和风险摘要', () => {
    const { container } = renderMonitor();

    expect(screen.getAllByText('重连次数')).toHaveLength(1);
    expect(screen.getByText('延迟 Latency ms').nextElementSibling).toHaveTextContent('86');
    expect(screen.getByText('重连次数').nextElementSibling).toHaveTextContent('0');
    expect(container.querySelector('.terminal-monitor-overview .terminal-builder-grid')).toBeNull();

    expect(screen.getByText('快照：已连接')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '监控快照' })).toBeInTheDocument();
    expect(screen.getByText(/以下为监控快照中的信号与事件/)).toBeInTheDocument();
    expect(
      screen.getByText('快照记录连接正常，记录延迟 86 ms，数据状态为 实时数据。'),
    ).toBeInTheDocument();
    expect(screen.getByText('数据状态：实时数据')).toBeInTheDocument();
    expect(screen.getByText('REST 轮询')).toBeInTheDocument();
    expect(screen.getByText('非 WebSocket 推送')).toBeInTheDocument();
    expect(screen.getByText(/快照时间：/)).toHaveTextContent('快照心跳：');
    expect(screen.getByText(/快照时间：/)).toHaveTextContent('并非浏览器连接心跳');
    expect(screen.getByText('最高严重程度')).toBeInTheDocument();
    expect(screen.getAllByText('严重').length).toBeGreaterThan(0);
    expect(screen.getByText('风险信号数').nextElementSibling).toHaveTextContent(
      '2',
    );
    expect(
      screen.getByText('Provider 警告').nextElementSibling,
    ).toHaveTextContent('1');
    expect(screen.getByText(/FAST PATH 1 \/ AI PATH 1/)).toHaveTextContent(
      '数据 Provider 1',
    );
  });

  it('按严重程度筛选信号并可清除筛选', () => {
    renderMonitor();
    const panel = getSignalPanel();

    fireEvent.click(
      within(panel).getByText('严重', {
        selector: '.ant-segmented-item-label',
      }),
    );

    expect(
      within(panel).getByText('信号：显示 1 / 共 3 条'),
    ).toBeInTheDocument();
    expect(within(panel).getByText('价格跌破风险阈值')).toBeInTheDocument();
    expect(within(panel).queryByText('成交量温和放大')).not.toBeInTheDocument();
    expect(within(panel).queryByText('波动率快速上升')).not.toBeInTheDocument();

    fireEvent.click(within(panel).getByRole('button', { name: '清除筛选' }));
    expect(
      within(panel).getByText('信号：显示 3 / 共 3 条'),
    ).toBeInTheDocument();
    expect(within(panel).getByText('成交量温和放大')).toBeInTheDocument();
  });

  it('在事件标签页按来源筛选并标记 Provider 警告行', () => {
    const { container } = renderMonitor();
    const panel = getSignalPanel();

    fireEvent.click(
      within(panel).getByRole('tab', { name: '实时事件流 Live Event Stream' }),
    );
    fireEvent.click(
      within(panel).getByText('数据 Provider', {
        selector: '.ant-segmented-item-label',
      }),
    );

    expect(
      within(panel).getByText('事件：显示 1 / 共 4 条'),
    ).toBeInTheDocument();
    expect(within(panel).getByText('行情源延迟升高')).toBeInTheDocument();
    expect(within(panel).queryByText('盘口波动加速')).not.toBeInTheDocument();
    expect(
      container.querySelectorAll('.terminal-monitor-provider-warning-row'),
    ).toHaveLength(1);
  });

  it('展示重连健康状态以及信号和事件空状态', () => {
    renderMonitor({
      ...monitor,
      stream: {
        ...monitor.stream,
        status: 'reconnecting',
        reconnectAttempts: 2,
        dataStatus: 'delayed',
      },
      streamMetrics: [],
      signals: [],
      events: [],
    });

    expect(screen.getByText('快照：重连中')).toBeInTheDocument();
    expect(screen.getByText('数据状态：延迟数据')).toBeInTheDocument();
    expect(screen.queryByText('实时数据', { exact: true })).not.toBeInTheDocument();
    expect(
      screen.getByText(
        '快照记录监控流正在重连，累计重连 2 次，数据状态为 延迟数据。',
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('暂无实时信号')).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole('tab', { name: '实时事件流 Live Event Stream' }),
    );
    expect(screen.getByText('暂无实时事件')).toBeInTheDocument();
  });
});

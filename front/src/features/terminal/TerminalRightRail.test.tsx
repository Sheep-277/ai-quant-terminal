import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, describe, expect, it, vi } from 'vitest';
import zhCN from '../../locales/zh-CN/terminal';
import { StrategyGuardrails, TerminalRightRail } from './TerminalRightRail';
import type { TerminalPageKey } from './types';

vi.mock('@ant-design/icons', () => ({
  ControlOutlined: () => null,
  LineChartOutlined: () => null,
  RobotOutlined: () => null,
  SafetyCertificateOutlined: () => null,
}));

// 只替换 Umi 的语言上下文，真实 Ant Design 折叠面板仍参与交互测试。
vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: 'zh-CN',
    formatMessage: ({ id }: { id: string }) =>
      zhCN[id as keyof typeof zhCN] ?? id,
  }),
}));

const renderRail = (pageKey: TerminalPageKey) =>
  render(
    <App>
      <TerminalRightRail pageKey={pageKey} />
    </App>,
  );

afterEach(cleanup);

describe('TerminalRightRail', () => {
  it('shows strategy guidance and checklist inside a single collapsible editor section', () => {
    const { container } = render(<App><StrategyGuardrails /></App>);
    expect(container.querySelector('.terminal-panel')).toBeNull();
    const toggle = screen.getByRole('button', { name: /策略护栏/ });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText(zhCN['terminal.rightRail.checklist.universe'])).toBeInTheDocument();
    expect(screen.getByText(zhCN['terminal.rightRail.checklist.riskLimit'])).toBeInTheDocument();
  });
  it.each([
    [
      'dashboard',
      '市场 AI 简报 Market AI Brief',
      '市场解释优先',
      ['指数', '市场宽度', '行业轮动'],
    ],
    [
      'stock-research',
      '个股研究简报 Stock Brief',
      '单标的研究优先',
      ['单标的', '估值', '因子'],
    ],
    [
      'ai-research',
      'Agent 研究任务',
      'Agent 可审计优先',
      ['任务', '工具调用', '证据'],
    ],
    [
      'strategy-lab',
      '策略护栏 Strategy Guardrails',
      '规则可执行优先',
      ['股票池', '入场/出场', '风险规则'],
    ],
    [
      'backtest',
      '回测质量检查 Backtest QA',
      '回测可信度优先',
      ['权益曲线', '回撤', '基准'],
    ],
    [
      'portfolio',
      '组合风险简报 Portfolio Risk',
      '模拟风控优先',
      ['模拟订单', '敞口', '现金'],
    ],
    [
      'monitor',
      '实时流健康 Stream Health',
      '实时状态优先',
      ['心跳', '延迟', '信号证据'],
    ],
  ] as const)('shows the page-specific summary for %s', (pageKey, panelTitle, briefTitle, focusTags) => {
    renderRail(pageKey);

    expect(screen.getByText(panelTitle)).toBeInTheDocument();
    expect(screen.getByText(briefTitle)).toBeInTheDocument();
    focusTags.forEach((tag) => {
      expect(screen.getByText(tag)).toBeInTheDocument();
    });
  });

  it.each([
    [
      'stock-research',
      '研究检查清单 Research Checklist',
      ['价格与成交量', '基本面指标', '估值指标', '风险标记'],
    ],
    [
      'strategy-lab',
      '策略检查清单 Strategy Checklist',
      ['股票池范围', '入场与出场规则', '调仓频率', '风险约束先于模拟交易'],
    ],
    [
      'backtest',
      '回测检查清单 Backtest Checklist',
      [
        '禁止使用未来数据',
        '费用与滑点口径',
        '同市场基准比较',
        '样本切分与时间范围',
      ],
    ],
    [
      'portfolio',
      '组合检查清单 Portfolio Checklist',
      ['仅模拟交易，不接真实资金', '现金权重', '组合敞口', '下单前风控结果'],
    ],
    [
      'monitor',
      '监控检查清单 Monitor Checklist',
      ['心跳状态', '数据延迟', '信号对应证据', '连接与重连状态'],
    ],
  ] as const)('expands the page-specific checklist for %s', (pageKey, checklistTitle, checklistItems) => {
    renderRail(pageKey);

    fireEvent.click(
      screen.getByRole('button', { name: new RegExp(checklistTitle) }),
    );
    checklistItems.forEach((item) => {
      expect(screen.getByText(item)).toBeInTheDocument();
    });
    ['01', '02', '03', '04'].forEach((index) => {
      expect(screen.getByText(index)).toBeInTheDocument();
    });
  });

  it.each([
    'dashboard',
    'ai-research',
  ] as const)('does not show a checklist on %s', (pageKey) => {
    const { container } = renderRail(pageKey);
    expect(
      container.querySelector('.terminal-right-details'),
    ).not.toBeInTheDocument();
  });

  it('shows the paper-trading boundary only for the portfolio page', () => {
    const { rerender } = renderRail('portfolio');
    expect(screen.getByText('仅模拟交易')).toBeInTheDocument();

    rerender(
      <App>
        <TerminalRightRail pageKey="dashboard" />
      </App>,
    );
    expect(screen.queryByText('仅模拟交易')).not.toBeInTheDocument();
  });
});

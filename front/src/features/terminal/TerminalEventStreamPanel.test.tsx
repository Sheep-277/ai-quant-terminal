import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { App } from 'antd';
import { afterEach, describe, expect, it, vi } from 'vitest';
import enUS from '../../locales/en-US/terminal';
import zhCN from '../../locales/zh-CN/terminal';
import { marketSnapshots } from './mockData';
import { TerminalEventStreamPanel } from './TerminalEventStreamPanel';
import { useEventColumns } from './terminalEventColumns';
import type { EventRow } from './types';

const localeState = vi.hoisted(() => ({ locale: 'zh-CN' }));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: localeState.locale,
    formatMessage: ({ id }: { id: string }) => {
      const dictionary = localeState.locale === 'en-US' ? enUS : zhCN;
      return dictionary[id as keyof typeof dictionary] ?? id;
    },
  }),
}));

vi.mock('./MarketContext', () => ({
  useMarket: () => ({ snapshot: marketSnapshots.US }),
}));

const events: EventRow[] = [
  { key: 'mock', time: '2026-10-14T01:00:00Z', sourceId: 'terminal.source.fastPath', eventOrigin: 'mock_sample', eventTitle: '样例信号', impactLabel: '观察', confidence: 0.8 },
  { key: 'system', time: '2026-10-14T01:01:00Z', sourceId: 'terminal.source.provider', eventOrigin: 'system', eventTitle: '行情延迟', impactLabel: '提示', confidence: 1 },
  { key: 'news', time: '2026-10-14T01:02:00Z', sourceId: 'terminal.source.aiPath', eventOrigin: 'news', eventTitle: '新闻事件样例', impactLabel: '关注', confidence: 0.7 },
];

const Harness = () => {
  const columns = useEventColumns();
  return <TerminalEventStreamPanel pageKey="dashboard" events={events} eventColumns={columns} />;
};

afterEach(() => {
  cleanup();
  localeState.locale = 'zh-CN';
});

describe('terminal event provenance', () => {
  it('labels mock, system and public-news rows explicitly', () => {
    render(<App><Harness /></App>);
    expect(screen.getByText('事件与系统动态 Event Feed')).toBeInTheDocument();
    expect(screen.getByText('Mock 样例')).toBeInTheDocument();
    expect(screen.getByText('系统事件')).toBeInTheDocument();
    expect(screen.getByText('公开新闻')).toBeInTheDocument();
  });

  it('shows a localized explanation for the sample label', async () => {
    render(<App><Harness /></App>);
    const badge = screen.getByText('Mock 样例');
    fireEvent.mouseOver(badge);
    const tooltip = await screen.findByText('预置演示事件，不代表当前市场真实发生的新闻或信号。');
    expect(tooltip).toHaveAttribute('role', 'tooltip');
  });

  it('uses the English locale without inline Chinese labels', () => {
    localeState.locale = 'en-US';
    render(<App><Harness /></App>);
    expect(screen.getByText('Events & System Activity')).toBeInTheDocument();
    expect(screen.getByText('Mock sample')).toBeInTheDocument();
    expect(screen.getByText('System event')).toBeInTheDocument();
    expect(screen.getByText('Public news')).toBeInTheDocument();
  });
});

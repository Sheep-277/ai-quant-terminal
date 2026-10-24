import { cleanup, render, screen } from '@testing-library/react';
import { App, Table } from 'antd';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import enUS from '../../locales/en-US/terminal';
import zhCN from '../../locales/zh-CN/terminal';
import { marketSnapshots } from './mockData';
import { useEventColumns } from './terminalEventColumns';
import type { EventRow, MarketCode } from './types';

const state = vi.hoisted(() => ({
  locale: 'zh-CN',
  market: 'US' as MarketCode,
}));

vi.mock('@umijs/max', () => ({
  useIntl: () => ({
    locale: state.locale,
    formatMessage: ({ id }: { id: string }) => {
      const dictionary = state.locale === 'en-US' ? enUS : zhCN;
      return dictionary[id as keyof typeof dictionary] ?? id;
    },
  }),
}));

vi.mock('./MarketContext', () => ({
  useMarket: () => ({ snapshot: marketSnapshots[state.market] }),
}));

const event: EventRow = {
  key: 'event-1',
  time: '2026-10-14T01:00:00Z',
  sourceId: 'terminal.source.fastPath',
  eventOrigin: 'system',
  eventTitle: '行情延迟状态更新',
  impactLabel: '数据时效性提示',
  confidence: 0.856,
};

const Harness = () => (
  <App>
    <Table<EventRow>
      columns={useEventColumns()}
      dataSource={[event]}
      pagination={false}
      rowKey="key"
    />
  </App>
);

beforeEach(() => {
  state.locale = 'zh-CN';
  state.market = 'US';
});

afterEach(cleanup);

describe('terminal event columns', () => {
  it('renders localized headers and all event fields', () => {
    render(<Harness />);

    expect(screen.getByRole('columnheader', { name: '时间' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: '来源' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: '事件' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: '影响' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: '置信度' })).toBeInTheDocument();
    expect(screen.getByText('FAST PATH')).toBeInTheDocument();
    expect(screen.getByText('系统事件')).toBeInTheDocument();
    expect(screen.getByText('行情延迟状态更新')).toBeInTheDocument();
    expect(screen.getByText('数据时效性提示')).toBeInTheDocument();
    expect(screen.getByText('86%')).toBeInTheDocument();
  });

  it('shows only the time converted to the active market timezone', () => {
    render(<Harness />);

    expect(screen.getByText('21:00:00')).toBeInTheDocument();
    expect(screen.queryByText(/2026/)).not.toBeInTheDocument();
  });

  it('uses the Hong Kong timezone and English table labels when selected', () => {
    state.locale = 'en-US';
    state.market = 'HK';

    render(<Harness />);

    expect(screen.getByRole('columnheader', { name: 'Time' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Source' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Conf.' })).toBeInTheDocument();
    expect(screen.getByText('09:00:00')).toBeInTheDocument();
    expect(screen.getByText('System event')).toBeInTheDocument();
  });
});

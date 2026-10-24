import { useIntl } from '@umijs/max';
import { Tag, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { formatDateTime, formatPercent } from './formatters';
import { useMarket } from './MarketContext';
import { TerminalTableText } from './TerminalShared';
import type { EventRow } from './types';

const useLocaleCode = () => {
  const intl = useIntl();
  return intl.locale?.startsWith('en') ? 'en-US' : 'zh-CN';
};

export const useEventColumns = (): ColumnsType<EventRow> => {
  const intl = useIntl();
  const locale = useLocaleCode();
  const { snapshot } = useMarket();

  return [
    {
      title: intl.formatMessage({ id: 'terminal.table.time' }),
      dataIndex: 'time',
      width: 128,
      render: (value: string) => (
        <TerminalTableText code>
          {formatDateTime(value, { timezone: snapshot.timezone, locale, pattern: 'HH:mm:ss' })}
        </TerminalTableText>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.source' }),
      dataIndex: 'sourceId',
      width: 146,
      render: (value: string, record) => {
        const originConfig = {
          mock_sample: { color: 'gold', labelId: 'terminal.eventOrigin.mockSample', detailId: 'terminal.eventOrigin.mockSample.detail' },
          system: { color: 'blue', labelId: 'terminal.eventOrigin.system', detailId: 'terminal.eventOrigin.system.detail' },
          news: { color: 'green', labelId: 'terminal.eventOrigin.news', detailId: 'terminal.eventOrigin.news.detail' },
        }[record.eventOrigin];

        return (
          <span className="terminal-event-source-cell">
            <TerminalTableText>{intl.formatMessage({ id: value })}</TerminalTableText>
            <Tooltip title={intl.formatMessage({ id: originConfig.detailId })}>
              <Tag color={originConfig.color}>{intl.formatMessage({ id: originConfig.labelId })}</Tag>
            </Tooltip>
          </span>
        );
      },
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.event' }),
      dataIndex: 'eventTitle',
      width: 320,
      render: (value: string) => <TerminalTableText>{value}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.impact' }),
      dataIndex: 'impactLabel',
      width: 170,
      render: (value: string) => <TerminalTableText>{value}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.confidence' }),
      dataIndex: 'confidence',
      width: 92,
      align: 'right',
      render: (value: number) => (
        <TerminalTableText>{formatPercent(value, { signDisplay: 'never', maximumFractionDigits: 0 }, locale)}</TerminalTableText>
      ),
    },
  ];
};

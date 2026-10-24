import {
  AlertOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { Table } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { Panel } from './TerminalShared';
import type { EventRow, TerminalPageKey } from './types';

export const TerminalEventStreamPanel = ({
  pageKey,
  events,
  eventColumns,
}: {
  pageKey: TerminalPageKey;
  events: EventRow[];
  eventColumns: ColumnsType<EventRow>;
}) => {
  const intl = useIntl();

  return (
    <Panel
      title={intl.formatMessage({ id: 'terminal.panel.eventFeed' })}
      icon={pageKey === 'monitor' ? <ThunderboltOutlined /> : <AlertOutlined />}
    >
      <Table size="small" columns={eventColumns} dataSource={events} pagination={false} scroll={{ x: 836 }} />
    </Panel>
  );
};

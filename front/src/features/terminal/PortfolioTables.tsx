import { StockOutlined } from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { Table, Tabs, Tag, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { ReactNode } from 'react';
import { formatCurrency, formatDateTime, formatNumber, formatPercent } from './formatters';
import { TerminalTableText } from './TerminalShared';
import type { PaperOrder, PortfolioPosition, PortfolioSnapshot } from './types';

const orderSourceMeta: Record<string, { color: string; labelId: string; tooltipId: string }> = {
  mock_summary: {
    color: 'default',
    labelId: 'terminal.portfolio.orderSource.mockSummary',
    tooltipId: 'terminal.portfolio.orderSource.mockSummary.tooltip',
  },
  paper_order: {
    color: 'blue',
    labelId: 'terminal.portfolio.orderSource.paperOrder',
    tooltipId: 'terminal.portfolio.orderSource.paperOrder.tooltip',
  },
};

const orderStatusColorMap: Record<PaperOrder['status'], string> = {
  submitted: 'processing',
  filled: 'success',
  cancelled: 'default',
  rejected: 'error',
};

const getPositionPricingMeta = (dataMode: PortfolioSnapshot['dataMode']) =>
  dataMode === 'paper'
    ? {
        color: 'green',
        labelId: 'terminal.portfolio.positionPricing.provider',
        tooltipId: 'terminal.portfolio.positionPricing.provider.tooltip',
      }
    : {
        color: 'default',
        labelId: 'terminal.portfolio.positionPricing.mock',
        tooltipId: 'terminal.portfolio.positionPricing.mock.tooltip',
      };

const Panel = ({
  title,
  icon,
  children,
}: {
  title: string;
  icon?: ReactNode;
  children: ReactNode;
}) => (
  <section className="terminal-panel">
    <div className="terminal-panel-header">
      <h2>
        {icon}
        {title}
      </h2>
    </div>
    {children}
  </section>
);

const usePositionColumns = (portfolio: PortfolioSnapshot): ColumnsType<PortfolioPosition> => {
  const intl = useIntl();
  const pricingMeta = getPositionPricingMeta(portfolio.dataMode);

  return [
    {
      title: intl.formatMessage({ id: 'terminal.table.symbol' }),
      dataIndex: 'symbol',
      width: 116,
      render: (value: string) => <TerminalTableText code>{value}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.name' }),
      dataIndex: 'name',
      width: 180,
      render: (value: string) => <TerminalTableText>{value}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.backtest.quantity' }),
      dataIndex: 'quantity',
      align: 'right',
      width: 96,
      render: (value: number) => <TerminalTableText>{formatNumber(value, {}, intl.locale)}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.averageCost' }),
      dataIndex: 'averageCost',
      align: 'right',
      width: 112,
      render: (value: number) => <TerminalTableText>{formatCurrency(value, portfolio.market)}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.lastPrice' }),
      dataIndex: 'lastPrice',
      align: 'right',
      width: 112,
      render: (value: number) => <TerminalTableText>{formatCurrency(value, portfolio.market)}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.valuationSource' }),
      dataIndex: 'key',
      width: 132,
      render: () => (
        <Tooltip title={intl.formatMessage({ id: pricingMeta.tooltipId })}>
          <Tag color={pricingMeta.color}>{intl.formatMessage({ id: pricingMeta.labelId })}</Tag>
        </Tooltip>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.marketValue' }),
      dataIndex: 'marketValue',
      align: 'right',
      width: 128,
      render: (value: number) => <TerminalTableText>{formatCurrency(value, portfolio.market)}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.weight' }),
      dataIndex: 'weight',
      align: 'right',
      width: 92,
      render: (value: number) => <TerminalTableText>{formatPercent(value, {}, intl.locale)}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.unrealizedPnl' }),
      dataIndex: 'unrealizedPnl',
      align: 'right',
      width: 138,
      render: (value: number, row) => (
        <TerminalTableText className={value >= 0 ? 'terminal-positive' : 'terminal-negative'}>
          {formatCurrency(value, portfolio.market)} / {formatPercent(row.unrealizedPnlPercent, {}, intl.locale)}
        </TerminalTableText>
      ),
    },
  ];
};

const useOrderColumns = (portfolio: PortfolioSnapshot): ColumnsType<PaperOrder> => {
  const intl = useIntl();

  return [
    {
      title: intl.formatMessage({ id: 'terminal.table.orderId' }),
      dataIndex: 'orderId',
      width: 150,
      render: (value: string) => <TerminalTableText code>{value}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.time' }),
      dataIndex: 'submittedAt',
      width: 170,
      render: (value: string) => (
        <TerminalTableText code>
          {formatDateTime(value, { timezone: portfolio.timezone, locale: intl.locale })}
        </TerminalTableText>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.symbol' }),
      dataIndex: 'symbol',
      width: 116,
      render: (value: string) => <TerminalTableText code>{value}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.backtest.side' }),
      dataIndex: 'side',
      width: 76,
      render: (value: PaperOrder['side']) => (
        <Tag color={value === 'buy' ? 'red' : 'green'}>
          {intl.formatMessage({ id: `terminal.portfolio.side.${value}` })}
        </Tag>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.backtest.quantity' }),
      dataIndex: 'quantity',
      align: 'right',
      width: 96,
      render: (value: number) => <TerminalTableText>{formatNumber(value, {}, intl.locale)}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.backtest.price' }),
      dataIndex: 'limitPrice',
      align: 'right',
      width: 112,
      render: (value: number | null) => <TerminalTableText>{value === null ? '-' : formatCurrency(value, portfolio.market)}</TerminalTableText>,
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.status' }),
      dataIndex: 'status',
      width: 96,
      render: (value: PaperOrder['status']) => (
        <Tag color={orderStatusColorMap[value]}>{intl.formatMessage({ id: `terminal.portfolio.status.${value}` })}</Tag>
      ),
    },
    {
      title: intl.formatMessage({ id: 'terminal.table.source' }),
      dataIndex: 'source',
      width: 116,
      render: (value: PaperOrder['source']) => {
        const meta = orderSourceMeta[value];
        const label = meta ? intl.formatMessage({ id: meta.labelId }) : value;
        return (
          <Tooltip title={meta ? intl.formatMessage({ id: meta.tooltipId }) : value}>
            <Tag color={meta?.color ?? 'default'}>{label}</Tag>
          </Tooltip>
        );
      },
    },
  ];
};

export const PortfolioTables = ({ portfolio }: { portfolio: PortfolioSnapshot }) => {
  const intl = useIntl();
  const positionColumns = usePositionColumns(portfolio);
  const orderColumns = useOrderColumns(portfolio);
  const positionPricingNoteId =
    portfolio.dataMode === 'paper'
      ? 'terminal.portfolio.positionPricing.note.provider'
      : 'terminal.portfolio.positionPricing.note.mock';

  return (
    <div className="terminal-stack">
      <Panel title={intl.formatMessage({ id: 'terminal.panel.positionsOrders' })} icon={<StockOutlined />}>
        <Tabs
          size="small"
          items={[
            {
              key: 'positions',
              label: `${intl.formatMessage({ id: 'terminal.panel.positionsOrders' })}: ${portfolio.positions.length}`,
              children: (
                <>
                  <Table size="small" columns={positionColumns} dataSource={portfolio.positions} pagination={false} rowKey="key" scroll={{ x: 1112 }} />
                  <p className="terminal-data-footnote">{intl.formatMessage({ id: positionPricingNoteId })}</p>
                </>
              ),
            },
            {
              key: 'orders',
              label: `${intl.formatMessage({ id: 'terminal.panel.paperOrders' })}: ${portfolio.orders.length}`,
              children: (
                <Table size="small" columns={orderColumns} dataSource={portfolio.orders} pagination={false} rowKey="key" scroll={{ x: 924 }} />
              ),
            },
          ]}
        />
      </Panel>
    </div>
  );
};

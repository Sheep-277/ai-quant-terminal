import { WalletOutlined } from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { Tag } from 'antd';
import type { ReactNode } from 'react';
import { formatDateTime } from './formatters';
import { StockMetricStrip } from './StockMetricStrip';
import type { PortfolioSnapshot } from './types';

const Panel = ({
  title,
  icon,
  extra,
  children,
}: {
  title: string;
  icon?: ReactNode;
  extra?: ReactNode;
  children: ReactNode;
}) => (
  <section className="terminal-panel">
    <div className="terminal-panel-header">
      <h2>
        {icon}
        {title}
      </h2>
      {extra}
    </div>
    {children}
  </section>
);

export const PortfolioSummaryPanel = ({ portfolio }: { portfolio: PortfolioSnapshot }) => {
  const intl = useIntl();
  const isProviderPriced = portfolio.dataMode === 'paper';

  return (
    <Panel
      title={intl.formatMessage({ id: 'terminal.panel.paperTradingConsole' })}
      icon={<WalletOutlined />}
      extra={
        <div className="terminal-tag-row">
          <Tag color="gold">{intl.formatMessage({ id: 'terminal.paperTradingOnly' })}</Tag>
          {isProviderPriced ? <Tag color="green">{intl.formatMessage({ id: 'terminal.portfolio.providerPriced' })}</Tag> : null}
        </div>
      }
    >
      <div className="terminal-portfolio-meta">
        <span>
          {intl.formatMessage({ id: 'terminal.portfolio.accountId' })}
          <strong>{portfolio.account.accountId}</strong>
        </span>
        <span>
          {intl.formatMessage({ id: 'terminal.portfolio.currency' })}
          <strong>{portfolio.currency}</strong>
        </span>
        <span>
          {intl.formatMessage({ id: 'terminal.portfolio.dataMode' })}
          <strong>{intl.formatMessage({ id: `terminal.portfolio.dataMode.${portfolio.dataMode}` })}</strong>
        </span>
      </div>
      <StockMetricStrip metrics={portfolio.accountMetrics} market={portfolio.market} />
      <p className="terminal-data-footnote">
        {intl.formatMessage(
          { id: 'terminal.portfolio.positionsUpdatedAt' },
          {
            timestamp: formatDateTime(portfolio.account.updatedAt, {
              timezone: portfolio.timezone,
              locale: intl.locale,
            }),
          },
        )}
      </p>
    </Panel>
  );
};

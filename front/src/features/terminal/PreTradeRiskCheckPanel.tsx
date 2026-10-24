import { SafetyCertificateOutlined } from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { Tag } from 'antd';
import type { ReactNode } from 'react';
import type { PreTradeRiskCheckResponse, RiskCheckDecision } from './apiTypes';
import { formatCurrency, formatDateTime, formatPercent } from './formatters';
import { getToneClass } from './mockData';
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

const riskDecisionColorMap: Record<RiskCheckDecision, string> = {
  approved: 'green',
  warning: 'gold',
  rejected: 'red',
};

export const PreTradeRiskCheckPanel = ({
  portfolio,
  receipt,
}: {
  portfolio: PortfolioSnapshot;
  receipt: PreTradeRiskCheckResponse;
}) => {
  const intl = useIntl();

  return (
    <Panel
      title={intl.formatMessage({ id: 'terminal.portfolio.riskCheckReceipt' })}
      icon={<SafetyCertificateOutlined />}
      extra={
        <Tag color={riskDecisionColorMap[receipt.decision]}>
          {intl.formatMessage({ id: `terminal.portfolio.riskDecision.${receipt.decision}` })}
        </Tag>
      }
    >
      <div className="terminal-portfolio-meta">
        <span>
          {intl.formatMessage({ id: 'terminal.table.symbol' })}
          <strong>{receipt.symbol}</strong>
        </span>
        <span>
          {intl.formatMessage({ id: 'terminal.portfolio.projectedOrderValue' })}
          <strong>{formatCurrency(receipt.projected_order_value, portfolio.market)}</strong>
        </span>
        <span>
          {intl.formatMessage({ id: 'terminal.portfolio.projectedCash' })}
          <strong>{formatCurrency(receipt.projected_cash, portfolio.market)}</strong>
        </span>
        <span>
          {intl.formatMessage({ id: 'terminal.portfolio.projectedCashWeight' })}
          <strong>{formatPercent(receipt.projected_cash_weight, {}, intl.locale)}</strong>
        </span>
        <span>
          {intl.formatMessage({ id: 'terminal.portfolio.projectedPositionWeight' })}
          <strong>{formatPercent(receipt.projected_position_weight, {}, intl.locale)}</strong>
        </span>
        <span>
          {intl.formatMessage({ id: 'terminal.aiResearch.acceptedAt' })}
          <strong>{formatDateTime(receipt.checked_at, { timezone: portfolio.timezone, locale: intl.locale })}</strong>
        </span>
      </div>
      {receipt.reasons.length > 0 ? (
        <div className="terminal-risk-list">
          {receipt.reasons.map((reason) => (
            <div className="terminal-risk-item" key={reason.code}>
              <span className={getToneClass(reason.severity === 'critical' ? 'negative' : 'warning')}>{reason.message}</span>
            </div>
          ))}
        </div>
      ) : null}
      <p className="terminal-muted">{intl.formatMessage({ id: 'terminal.portfolio.riskCheckReceiptFootnote' })}</p>
    </Panel>
  );
};

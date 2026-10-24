import { WalletOutlined } from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { Tag } from 'antd';
import type { ReactNode } from 'react';
import type { PaperOrderCreateResponse, PaperOrderStatus, RiskCheckDecision } from './apiTypes';
import { formatCurrency, formatDateTime, formatNumber } from './formatters';
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

const orderStatusColorMap: Record<PaperOrderStatus, string> = {
  submitted: 'processing',
  filled: 'success',
  cancelled: 'default',
  rejected: 'error',
};

export const PaperOrderReceiptPanel = ({
  portfolio,
  receipt,
}: {
  portfolio: PortfolioSnapshot;
  receipt: PaperOrderCreateResponse;
}) => {
  const intl = useIntl();
  const riskReasons = receipt.risk_reasons.map((reason, index) => ({
    code: receipt.risk_reason_codes[index] ?? reason,
    message: reason,
  }));
  const fallbackReason = receipt.fallback_active && receipt.fallback_reason ? receipt.fallback_reason : null;

  return (
    <Panel
      title={intl.formatMessage({ id: 'terminal.portfolio.orderReceipt' })}
      icon={<WalletOutlined />}
      extra={
        <>
          {fallbackReason ? <Tag color="gold">{intl.formatMessage({ id: 'terminal.providerStatus.fallback' })}</Tag> : null}
          <Tag color={orderStatusColorMap[receipt.status]}>
            {intl.formatMessage({ id: `terminal.portfolio.status.${receipt.status}` })}
          </Tag>
        </>
      }
    >
      <div className="terminal-portfolio-meta">
        <span>
          {intl.formatMessage({ id: 'terminal.table.orderId' })}
          <strong>{receipt.order_id}</strong>
        </span>
        <span>
          {intl.formatMessage({ id: 'terminal.table.symbol' })}
          <strong>{receipt.symbol}</strong>
        </span>
        <span>
          {intl.formatMessage({ id: 'terminal.backtest.quantity' })}
          <strong>{formatNumber(receipt.quantity, {}, intl.locale)}</strong>
        </span>
        <span>
          {intl.formatMessage({ id: 'terminal.backtest.price' })}
          <strong>{receipt.limit_price === null ? '-' : formatCurrency(receipt.limit_price, portfolio.market)}</strong>
        </span>
        <span>
          {intl.formatMessage({ id: 'terminal.portfolio.riskChecked' })}
          <strong>{intl.formatMessage({ id: `terminal.boolean.${receipt.risk_checked ? 'yes' : 'no'}` })}</strong>
        </span>
        <span>
          {intl.formatMessage({ id: 'terminal.portfolio.orderRiskDecision' })}
          <strong>
            <Tag color={riskDecisionColorMap[receipt.risk_decision]}>
              {intl.formatMessage({ id: `terminal.portfolio.riskDecision.${receipt.risk_decision}` })}
            </Tag>
          </strong>
        </span>
        <span>
          {intl.formatMessage({ id: 'terminal.aiResearch.acceptedAt' })}
          <strong>{formatDateTime(receipt.submitted_at, { timezone: portfolio.timezone, locale: intl.locale })}</strong>
        </span>
      </div>
      {riskReasons.length > 0 ? (
        <div className="terminal-risk-list">
          {riskReasons.map((reason) => (
            <div className="terminal-risk-item" key={`${reason.code}-${reason.message}`}>
              <span className={getToneClass(receipt.risk_decision === 'rejected' ? 'negative' : 'warning')}>{reason.message}</span>
            </div>
          ))}
        </div>
      ) : null}
      {fallbackReason ? (
        <div className="terminal-risk-item terminal-risk-item-fallback">
          <Tag color="gold">{intl.formatMessage({ id: 'terminal.providerStatus.fallback' })}</Tag>
          <span className={getToneClass('warning')}>{fallbackReason}</span>
        </div>
      ) : null}
      <p className="terminal-data-footnote">
        {intl.formatMessage({ id: `terminal.portfolio.orderReceiptStatus.${receipt.status}` })}
      </p>
      <p className="terminal-muted">{intl.formatMessage({ id: 'terminal.portfolio.orderReceiptFootnote' })}</p>
    </Panel>
  );
};

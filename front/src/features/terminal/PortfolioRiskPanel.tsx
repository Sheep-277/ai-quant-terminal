import { SafetyCertificateOutlined } from '@ant-design/icons';
import { useIntl } from '@umijs/max';
import { Tag } from 'antd';
import type { ReactNode } from 'react';
import { getToneClass } from './mockData';
import { StockMetricStrip } from './StockMetricStrip';
import type { PortfolioSnapshot } from './types';

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

const isPortfolioFallbackRiskFlag = (flag: string) =>
  flag.includes('数据库组合快照读取失败') ||
  flag.toLowerCase().includes('database portfolio snapshot read failed');

const isProviderQuoteFallbackRiskFlag = (flag: string) =>
  flag.includes('真实持仓行情读取失败') ||
  flag.toLowerCase().includes('provider quote unavailable') ||
  flag.toLowerCase().includes('quote fallback');

export const PortfolioRiskPanel = ({ portfolio }: { portfolio: PortfolioSnapshot }) => {
  const intl = useIntl();

  return (
    <Panel title={intl.formatMessage({ id: 'terminal.panel.tradingBoundary' })} icon={<SafetyCertificateOutlined />}>
      <StockMetricStrip metrics={portfolio.riskMetrics} market={portfolio.market} />
      <div className="terminal-risk-list">
        {portfolio.riskFlags.map((flag) => {
          const isDatabaseFallback = isPortfolioFallbackRiskFlag(flag);
          const isQuoteFallback = isProviderQuoteFallbackRiskFlag(flag);
          const isFallback = isDatabaseFallback || isQuoteFallback;

          return (
            <div className={`terminal-risk-item ${isFallback ? 'terminal-risk-item-fallback' : ''}`} key={flag}>
              {isDatabaseFallback ? <Tag color="gold">{intl.formatMessage({ id: 'terminal.providerStatus.fallback' })}</Tag> : null}
              {isQuoteFallback ? <Tag color="orange">{intl.formatMessage({ id: 'terminal.portfolio.quoteFallback' })}</Tag> : null}
              <span className={getToneClass('warning')}>{flag}</span>
            </div>
          );
        })}
      </div>
    </Panel>
  );
};

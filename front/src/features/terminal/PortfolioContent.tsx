import { useIntl } from '@umijs/max';
import { Alert } from 'antd';
import type { PaperOrderCreateResponse, PreTradeRiskCheckResponse } from './apiTypes';
import { PaperOrderReceiptPanel } from './PaperOrderReceiptPanel';
import { PreTradeRiskCheckPanel } from './PreTradeRiskCheckPanel';
import { PortfolioRiskPanel } from './PortfolioRiskPanel';
import { PortfolioSummaryPanel } from './PortfolioSummaryPanel';
import { PortfolioTables } from './PortfolioTables';
import type { PortfolioSnapshot } from './types';

export const PortfolioContent = ({
  portfolio,
  paperOrderReceipt,
  preTradeRiskCheckReceipt,
}: {
  portfolio: PortfolioSnapshot;
  paperOrderReceipt?: PaperOrderCreateResponse;
  preTradeRiskCheckReceipt?: PreTradeRiskCheckResponse;
}) => {
  const intl = useIntl();
  const boundaryDescriptionId =
    portfolio.dataMode === 'paper'
      ? 'terminal.portfolio.dataBoundaryDescription.paper'
      : 'terminal.portfolio.dataBoundaryDescription.mock';

  return (
    <div className="terminal-portfolio-layout">
      <Alert
        showIcon
        type={portfolio.dataMode === 'paper' ? 'success' : 'info'}
        title={intl.formatMessage({ id: 'terminal.portfolio.dataBoundaryTitle' })}
        description={intl.formatMessage(
          { id: boundaryDescriptionId },
          {
            accountId: portfolio.account.accountId,
            market: portfolio.market,
            dataMode: intl.formatMessage({ id: `terminal.portfolio.dataMode.${portfolio.dataMode}` }),
          },
        )}
      />
      <div className="terminal-portfolio-primary-row">
        <div className="terminal-portfolio-summary">
          <PortfolioSummaryPanel portfolio={portfolio} />
        </div>
        <div className="terminal-portfolio-risk">
          <PortfolioRiskPanel portfolio={portfolio} />
        </div>
      </div>
      {preTradeRiskCheckReceipt || paperOrderReceipt ? (
        <div className="terminal-portfolio-receipts">
          {preTradeRiskCheckReceipt ? <PreTradeRiskCheckPanel portfolio={portfolio} receipt={preTradeRiskCheckReceipt} /> : null}
          {paperOrderReceipt ? <PaperOrderReceiptPanel portfolio={portfolio} receipt={paperOrderReceipt} /> : null}
        </div>
      ) : null}
      <section className="terminal-portfolio-table-area">
        <PortfolioTables portfolio={portfolio} />
      </section>
    </div>
  );
};

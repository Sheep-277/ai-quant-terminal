import type { PaperOrderRequest, PreTradeRiskCheckRequest } from './apiTypes';
import type { PortfolioSnapshot } from './types';

const getFirstPortfolioPosition = (portfolio: PortfolioSnapshot) => {
  const position = portfolio.positions[0];

  if (!position) {
    throw new Error('Portfolio position is required to create a mock paper order.');
  }

  return position;
};

export const buildPaperOrderCreatePayload = (portfolio: PortfolioSnapshot): PaperOrderRequest => {
  // 当前没有独立下单表单，先用第一条持仓生成一笔最小模拟买入订单，验证前后端调用链。
  const position = getFirstPortfolioPosition(portfolio);

  return {
    account_id: portfolio.account.accountId,
    market: portfolio.market,
    symbol: position.symbol,
    side: 'buy',
    quantity: 1,
    limit_price: position.lastPrice,
    paper_trading: true,
  };
};

export const buildPreTradeRiskCheckPayload = (portfolio: PortfolioSnapshot): PreTradeRiskCheckRequest => {
  // 前端先用当前页面快照做下单前风险检查，后端创建订单时仍会再次校验。
  const position = getFirstPortfolioPosition(portfolio);

  return {
    account_id: portfolio.account.accountId,
    market: portfolio.market,
    symbol: position.symbol,
    side: 'buy',
    quantity: 1,
    limit_price: position.lastPrice,
    nav: portfolio.account.nav,
    cash: portfolio.account.cash,
    current_positions: portfolio.positions.map((item) => ({
      market: item.market,
      symbol: item.symbol,
      market_value: item.marketValue,
      side: 'long',
    })),
    max_position_weight: 0.3,
    min_cash_weight: 0.05,
    paper_trading: true,
  };
};

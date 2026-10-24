from decimal import Decimal

from app.core.market import MarketCode
from app.db.init_db import init_database
from app.db.repositories.portfolio_repository import PortfolioRepository
from app.db.session import create_database_engine, create_session_factory
from app.schemas.portfolio import PaperOrderRequest, PaperOrderSide
from app.services.mock_portfolio_service import create_mock_paper_order, get_mock_portfolio_summary
from app.services.portfolio_write_service import save_paper_order_receipt, save_portfolio_summary


def test_save_portfolio_summary_persists_response_parts() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    session_factory = create_session_factory(engine)
    response = get_mock_portfolio_summary(MarketCode.US)

    with session_factory() as session:
        saved_portfolio = save_portfolio_summary(session, response)
        repository = PortfolioRepository(session)

        stored_portfolio = repository.get_by_account_id(response.account.account_id)
        positions = repository.list_positions(response.account.account_id)
        orders = repository.list_orders(response.account.account_id)
        trades = repository.list_trades(response.account.account_id)

        assert saved_portfolio.account_id == response.account.account_id
        assert stored_portfolio is not None
        assert stored_portfolio.market == "US"
        assert stored_portfolio.source == "mock_summary"
        assert len(positions) == len(response.positions)
        assert len(orders) == len(response.orders)
        assert len(trades) == len([order for order in response.orders if order.filled_at is not None])
        assert trades[0].trade_id.endswith("-fill")


def test_save_portfolio_summary_replaces_children_on_repeat_save() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    session_factory = create_session_factory(engine)
    response = get_mock_portfolio_summary(MarketCode.HK)

    with session_factory() as session:
        save_portfolio_summary(session, response)
        save_portfolio_summary(session, response)
        repository = PortfolioRepository(session)

        market_portfolios = repository.list_by_market("HK")
        positions = repository.list_positions(response.account.account_id)
        orders = repository.list_orders(response.account.account_id)
        trades = repository.list_trades(response.account.account_id)

        assert len(market_portfolios) == 1
        assert len(positions) == len(response.positions)
        assert len(orders) == len(response.orders)
        assert len(trades) == len([order for order in response.orders if order.filled_at is not None])


def test_save_paper_order_receipt_appends_order_without_duplicates() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    session_factory = create_session_factory(engine)
    response = get_mock_portfolio_summary(MarketCode.US)
    request = PaperOrderRequest(
        account_id=response.account.account_id,
        market=MarketCode.US,
        symbol="NVDA",
        side=PaperOrderSide.BUY,
        quantity=10,
        limit_price=180.5,
    )
    receipt = create_mock_paper_order(request)

    with session_factory() as session:
        save_portfolio_summary(session, response)
        saved_order = save_paper_order_receipt(session, receipt)
        save_paper_order_receipt(session, receipt)
        repository = PortfolioRepository(session)

        stored_portfolio = repository.get_by_account_id(response.account.account_id)
        positions = repository.list_positions(response.account.account_id)
        orders = repository.list_orders(response.account.account_id)
        trades = repository.list_trades(response.account.account_id)
        nvda_position = next(position for position in positions if position.symbol == "NVDA")
        matching_orders = [order for order in orders if order.order_id == receipt.order_id]
        matching_trades = [trade for trade in trades if trade.order_id == receipt.order_id]

        assert saved_order is not None
        assert saved_order.order_id == receipt.order_id
        assert stored_portfolio is not None
        assert stored_portfolio.cash == Decimal("16615.000000")
        assert nvda_position.quantity == 190
        assert len(matching_orders) == 1
        assert matching_orders[0].status == "filled"
        assert matching_orders[0].source == "paper_order"
        assert matching_orders[0].risk_decision == receipt.risk_decision.value
        assert len(matching_trades) == 1
        assert matching_trades[0].source == "paper_order"

from datetime import datetime
from decimal import Decimal

from app.db.init_db import init_database
from app.db.repositories.portfolio_repository import PortfolioRepository
from app.db.session import create_database_engine, create_session_factory
from app.models.portfolio import Order, Portfolio, Position, Trade


def test_portfolio_repository_saves_and_reads_snapshot_parts() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = PortfolioRepository(session)
        portfolio = repository.save_portfolio(_build_portfolio(nav=Decimal("125000.00")))
        session.flush()
        repository.replace_positions(portfolio, [_build_position("NVDA", Decimal("0.42")), _build_position("MSFT", Decimal("0.25"))])
        repository.replace_orders(portfolio, [_build_order("paper-us-001")])
        repository.replace_trades(portfolio, [_build_trade("trade-us-001")])
        session.commit()

        saved_portfolio = repository.get_by_account_id("paper-us-001")
        market_portfolios = repository.list_by_market("us")
        positions = repository.list_positions("paper-us-001")
        orders = repository.list_orders("paper-us-001")
        trades = repository.list_trades("paper-us-001")

        assert saved_portfolio is not None
        assert saved_portfolio.nav == Decimal("125000.000000")
        assert [item.account_id for item in market_portfolios] == ["paper-us-001"]
        assert [position.symbol for position in positions] == ["NVDA", "MSFT"]
        assert orders[0].order_id == "paper-us-001"
        assert trades[0].trade_id == "trade-us-001"


def test_portfolio_repository_updates_existing_snapshot_and_replaces_children() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = PortfolioRepository(session)
        portfolio = repository.save_portfolio(_build_portfolio(nav=Decimal("125000.00")))
        session.flush()
        repository.replace_positions(portfolio, [_build_position("NVDA", Decimal("0.42"))])
        repository.replace_orders(portfolio, [_build_order("paper-us-001")])
        repository.replace_trades(portfolio, [_build_trade("trade-us-001")])
        session.commit()

        updated_portfolio = repository.save_portfolio(_build_portfolio(nav=Decimal("130000.00")))
        session.flush()
        repository.replace_positions(updated_portfolio, [_build_position("AAPL", Decimal("0.33"))])
        repository.replace_orders(updated_portfolio, [])
        repository.replace_trades(updated_portfolio, [])
        session.commit()

        saved_portfolio = repository.get_by_account_id("paper-us-001")
        positions = repository.list_positions("paper-us-001")
        orders = repository.list_orders("paper-us-001")
        trades = repository.list_trades("paper-us-001")

        assert saved_portfolio is not None
        assert saved_portfolio.nav == Decimal("130000.000000")
        assert [position.symbol for position in positions] == ["AAPL"]
        assert orders == []
        assert trades == []


def test_portfolio_repository_filters_market_and_orders_latest_first() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = PortfolioRepository(session)
        repository.save_portfolio(
            _build_portfolio(
                account_id="paper-us-old",
                nav=Decimal("120000.00"),
                updated_at=datetime(2026, 1, 1, 10, 0),
            )
        )
        repository.save_portfolio(
            _build_portfolio(
                account_id="paper-us-latest",
                nav=Decimal("130000.00"),
                updated_at=datetime(2026, 1, 1, 11, 0),
            )
        )
        repository.save_portfolio(
            _build_portfolio(
                account_id="paper-hk-latest",
                market="HK",
                currency="HKD",
                nav=Decimal("140000.00"),
                updated_at=datetime(2026, 1, 1, 12, 0),
            )
        )
        session.commit()

        portfolios = repository.list_by_market("us")

        assert [portfolio.account_id for portfolio in portfolios] == [
            "paper-us-latest",
            "paper-us-old",
        ]


def _build_portfolio(
    *,
    nav: Decimal,
    account_id: str = "paper-us-001",
    market: str = "US",
    currency: str = "USD",
    updated_at: datetime = datetime(2026, 1, 1, 10, 0),
) -> Portfolio:
    """构造最小合法组合账户记录，供 Repository 测试复用。"""

    return Portfolio(
        account_id=account_id,
        market=market,
        currency=currency,
        data_mode="mock",
        nav=nav,
        cash=Decimal("25000.00"),
        market_value=nav - Decimal("25000.00"),
        daily_pnl=Decimal("500.00"),
        total_pnl=Decimal("25000.00"),
        total_return=Decimal("0.25"),
        gross_exposure=Decimal("0.80"),
        net_exposure=Decimal("0.80"),
        largest_position_weight=Decimal("0.42"),
        cash_weight=Decimal("0.20"),
        risk_flags=["测试风险提示"],
        source="test",
        updated_at=updated_at,
    )


def _build_position(symbol: str, weight: Decimal) -> Position:
    """构造持仓记录；portfolio_id/account_id 由 Repository 写入。"""

    return Position(
        portfolio_id=0,
        account_id="",
        market="US",
        symbol=symbol,
        name=f"{symbol} Inc.",
        quantity=10,
        average_cost=Decimal("100.00"),
        last_price=Decimal("120.00"),
        market_value=Decimal("1200.00"),
        weight=weight,
        unrealized_pnl=Decimal("200.00"),
        unrealized_pnl_percent=Decimal("0.20"),
        source="test",
        updated_at=datetime(2026, 1, 1, 10, 0),
    )


def _build_order(order_id: str) -> Order:
    """构造模拟订单记录；portfolio_id/account_id 由 Repository 写入。"""

    return Order(
        portfolio_id=0,
        order_id=order_id,
        account_id="",
        market="US",
        symbol="NVDA",
        side="buy",
        quantity=10,
        limit_price=Decimal("120.00"),
        status="filled",
        currency="USD",
        risk_checked=True,
        risk_decision="approved",
        risk_reason_codes=[],
        risk_reasons=[],
        submitted_at=datetime(2026, 1, 1, 10, 0),
        filled_at=datetime(2026, 1, 1, 10, 3),
        source="test",
    )


def _build_trade(trade_id: str) -> Trade:
    """构造模拟成交记录；portfolio_id/account_id 由 Repository 写入。"""

    return Trade(
        portfolio_id=0,
        order_id="paper-us-001",
        trade_id=trade_id,
        account_id="",
        market="US",
        symbol="NVDA",
        side="buy",
        quantity=10,
        price=Decimal("120.00"),
        fee=Decimal("1.20"),
        filled_at=datetime(2026, 1, 1, 10, 3),
        source="test",
    )

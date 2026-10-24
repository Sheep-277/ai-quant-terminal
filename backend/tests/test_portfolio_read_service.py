from datetime import datetime
from decimal import Decimal

from app.core.market import MarketCode
from app.db.init_db import init_database
from app.db.repositories.portfolio_repository import PortfolioRepository
from app.db.session import create_database_engine, create_session_factory
from app.models.portfolio import Portfolio
from app.schemas.portfolio import PaperOrderRequest, PaperOrderSide
from app.services.mock_portfolio_service import create_mock_paper_order, get_mock_portfolio_summary
from app.services.portfolio_read_service import get_latest_portfolio_snapshot, get_portfolio_snapshot_by_account_id
from app.services.portfolio_write_service import save_paper_order_receipt, save_portfolio_summary


def test_get_latest_portfolio_snapshot_reads_saved_summary() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    session_factory = create_session_factory(engine)
    response = get_mock_portfolio_summary(MarketCode.CN)

    with session_factory() as session:
        save_portfolio_summary(session, response)

        snapshot = get_latest_portfolio_snapshot(session, MarketCode.CN)

        assert snapshot is not None
        assert snapshot.source == "database"
        assert snapshot.response.account.account_id == response.account.account_id
        assert snapshot.response.market == MarketCode.CN
        assert snapshot.response.account.nav == round(response.account.nav, 6)
        assert len(snapshot.response.positions) == len(response.positions)
        assert len(snapshot.response.orders) == len(response.orders)
        assert {order.source for order in snapshot.response.orders} == {"mock_summary"}


def test_get_latest_portfolio_snapshot_returns_none_without_market_data() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        snapshot = get_latest_portfolio_snapshot(session, MarketCode.US)

        assert snapshot is None


def test_get_portfolio_snapshot_by_account_id_reads_saved_summary() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    session_factory = create_session_factory(engine)
    response = get_mock_portfolio_summary(MarketCode.US)

    with session_factory() as session:
        save_portfolio_summary(session, response)

        snapshot = get_portfolio_snapshot_by_account_id(session, response.account.account_id)

        assert snapshot is not None
        assert snapshot.source == "database"
        assert snapshot.response.currency == response.currency
        assert snapshot.response.positions[0].market == MarketCode.US
        assert snapshot.response.orders[0].symbol == response.orders[0].symbol


def test_get_latest_portfolio_snapshot_exposes_user_order_source() -> None:
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

    with session_factory() as session:
        save_portfolio_summary(session, response)
        save_paper_order_receipt(session, create_mock_paper_order(request))

        snapshot = get_latest_portfolio_snapshot(session, MarketCode.US)

        assert snapshot is not None
        sources = {order.order_id: order.source for order in snapshot.response.orders}
        assert sources["paper-us-paper-us-001-nvda-submitted"] == "paper_order"


def test_get_latest_portfolio_snapshot_uses_only_current_market_latest_account() -> None:
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

        snapshot = get_latest_portfolio_snapshot(session, MarketCode.US)

        assert snapshot is not None
        assert snapshot.response.market == MarketCode.US
        assert snapshot.response.account.account_id == "paper-us-latest"
        assert snapshot.response.account.nav == 130000.0


def _build_portfolio(
    *,
    account_id: str,
    nav: Decimal,
    market: str = "US",
    currency: str = "USD",
    updated_at: datetime,
) -> Portfolio:
    """构造只读服务测试所需的组合账户记录。"""

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

from datetime import datetime
from decimal import Decimal

from app.core.market import MarketCode
from app.db.repositories.latest_quote_repository import LatestQuoteRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.latest_quote import LatestQuote
from app.models.stock import Stock
from app.services.market_read_service import get_market_overview_read_snapshot
from app.services.mock_market_service import get_mock_market_overview


def test_market_read_service_uses_only_current_market_quotes() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = LatestQuoteRepository(session)
        nvda = _add_stock(session, market="US", symbol="NVDA")
        aapl = _add_stock(session, market="US", symbol="AAPL")
        tencent = _add_stock(session, market="HK", symbol="00700.HK")
        repository.save_latest(
            _build_quote(
                nvda,
                price=Decimal("181.42"),
                change_percent=Decimal("0.0133"),
                data_status="realtime",
                quote_timestamp=datetime(2026, 9, 28, 10, 30),
            )
        )
        repository.save_latest(
            _build_quote(
                aapl,
                price=Decimal("220.15"),
                change_percent=Decimal("-0.0080"),
                data_status="delayed",
                quote_timestamp=datetime(2026, 9, 28, 10, 35),
            )
        )
        repository.save_latest(
            _build_quote(
                tencent,
                price=Decimal("420.00"),
                change_percent=Decimal("0.0200"),
                data_status="realtime",
                quote_timestamp=datetime(2026, 9, 28, 11, 0),
            )
        )
        session.commit()

        snapshot = get_market_overview_read_snapshot(
            session,
            MarketCode.US,
            get_mock_market_overview(MarketCode.US),
        )

    assert snapshot is not None
    assert snapshot.market == MarketCode.US
    assert snapshot.data_status == "realtime"
    assert snapshot.timestamp.isoformat() == "2026-09-28T10:35:00+00:00"
    assert [index.symbol for index in snapshot.indices] == ["SPX", "NDX", "VIX"]
    assert snapshot.indices[0].name == "S&P 500"
    assert snapshot.indices[0].value != 220.15
    assert snapshot.breadth.advancers_percent == 0.5
    assert snapshot.breadth.decliners_percent == 0.5
    assert snapshot.breadth.unchanged_percent == 0.0
    assert snapshot.events[0].source == "DATABASE"
    assert "2 条本地最新行情" in snapshot.events[0].title
    assert "0 条" in snapshot.events[0].title
    assert "来源与时间" in snapshot.events[0].title


def test_market_read_service_updates_only_matching_index_and_excludes_it_from_breadth() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = LatestQuoteRepository(session)
        spx = _add_stock(session, market="US", symbol="SPX")
        aapl = _add_stock(session, market="US", symbol="AAPL")
        repository.save_latest(_build_quote(
            spx,
            price=Decimal("6500"),
            change_percent=Decimal("0.01"),
            data_status="delayed",
            quote_timestamp=datetime(2026, 9, 28, 10, 30),
        ))
        repository.save_latest(_build_quote(
            aapl,
            price=Decimal("220"),
            change_percent=Decimal("-0.01"),
            data_status="realtime",
            quote_timestamp=datetime(2026, 9, 28, 10, 35),
        ))
        session.commit()
        fallback = get_mock_market_overview(MarketCode.US)
        snapshot = get_market_overview_read_snapshot(session, MarketCode.US, fallback)

    assert snapshot is not None
    assert snapshot.indices[0].symbol == "SPX"
    assert snapshot.indices[0].name == "S&P 500"
    assert snapshot.indices[0].value == 6500
    assert snapshot.indices[0].status == "delayed"
    assert snapshot.indices[1:] == fallback.indices[1:]
    assert snapshot.breadth.advancers_percent == 0
    assert snapshot.breadth.decliners_percent == 1


def test_market_read_service_retains_breadth_when_only_index_quotes_exist() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        spx = _add_stock(session, market="US", symbol="SPX")
        LatestQuoteRepository(session).save_latest(_build_quote(
            spx,
            price=Decimal("6500"),
            change_percent=Decimal("0.01"),
            data_status="delayed",
            quote_timestamp=datetime(2026, 9, 28, 10, 30),
        ))
        session.commit()
        fallback = get_mock_market_overview(MarketCode.US)
        snapshot = get_market_overview_read_snapshot(session, MarketCode.US, fallback)

    assert snapshot is not None
    assert snapshot.indices[0].value == 6500
    assert snapshot.breadth == fallback.breadth


def test_market_read_service_returns_none_without_quotes() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        snapshot = get_market_overview_read_snapshot(
            session,
            MarketCode.CN,
            get_mock_market_overview(MarketCode.CN),
        )

    assert snapshot is None


def _add_stock(session, *, market: str, symbol: str) -> Stock:
    """构造行情测试所需的股票基础信息。"""

    stock = Stock(
        market=market,
        symbol=symbol,
        name=f"{symbol} Example",
        exchange="NASDAQ" if market == "US" else "HKEX",
        currency="USD" if market == "US" else "HKD",
        timezone="America/New_York" if market == "US" else "Asia/Hong_Kong",
    )
    session.add(stock)
    session.flush()
    return stock


def _build_quote(
    stock: Stock,
    *,
    price: Decimal,
    change_percent: Decimal,
    data_status: str,
    quote_timestamp: datetime,
) -> LatestQuote:
    """构造 latest_quotes 记录，模拟 Provider 写入的最新行情。"""

    return LatestQuote(
        stock_id=stock.id,
        market=stock.market,
        symbol=stock.symbol,
        price=price,
        change_amount=price * change_percent,
        change_percent=change_percent,
        volume=1_000_000,
        turnover=price * Decimal("1000000"),
        data_status=data_status,
        source="test",
        quote_timestamp=quote_timestamp,
    )

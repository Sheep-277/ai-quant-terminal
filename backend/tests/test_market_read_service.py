from datetime import datetime
from decimal import Decimal
import pytest

from app.core.market import MarketCode
from app.db.repositories.latest_quote_repository import LatestQuoteRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.latest_quote import LatestQuote
from app.models.stock import Stock
from app.services.market_read_service import _build_breadth, get_market_overview_read_snapshot
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
    assert snapshot.breadth.sample_size == 2
    assert snapshot.breadth.sample_sources == ["test"]
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
    assert snapshot.breadth.sample_size == 1
    assert snapshot.breadth.sample_sources == ["test"]


def test_breadth_excludes_seed_without_borrowing_index_state() -> None:
    """只有样例个股时不输出占比，也不借用较新的真实指数状态。"""
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with create_session_factory(engine)() as session:
        repository = LatestQuoteRepository(session)
        for symbol, change, source, when in [
            ("SPX", "0.01", "yahoo_finance", datetime(2026, 10, 26, 10)),
            ("NVDA", "0.01", "mock_seed", datetime(2026, 10, 12, 10)),
            ("AAPL", "-0.01", "mock_seed", datetime(2026, 10, 12, 11)),
        ]:
            quote = _build_quote(_add_stock(session, market="US", symbol=symbol),
                                 price=Decimal("100"), change_percent=Decimal(change),
                                 data_status="delayed", quote_timestamp=when)
            quote.source = source
            repository.save_latest(quote)
        session.commit()
        snapshot = get_market_overview_read_snapshot(session, MarketCode.US, get_mock_market_overview(MarketCode.US))
    assert snapshot is not None
    assert snapshot.breadth.sample_size == 0
    assert snapshot.breadth.excluded_sample_size == 2
    assert snapshot.breadth.sample_sources == []
    assert snapshot.breadth.timestamp is None
    assert snapshot.breadth.advancers_percent is None
    assert snapshot.breadth.decliners_percent is None
    assert snapshot.breadth.status == "unavailable"


def test_market_read_service_has_no_breadth_when_only_index_quotes_exist() -> None:
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
    assert snapshot.breadth.sample_size == 0
    assert snapshot.breadth.advancers_percent is None
    assert snapshot.breadth.new_highs is None
    assert snapshot.breadth.new_lows is None
    assert snapshot.breadth.status == "unavailable"


def _breadth_quote(symbol: str, when: str, *, change: str = "0.02", source: str = "yahoo_finance", status: str = "delayed") -> LatestQuote:
    """只测试纯统计口径，无需网络或实际数据库。"""
    return LatestQuote(symbol=symbol, market="US", price=Decimal("100"), change_percent=Decimal(change),
                       source=source, data_status=status, quote_timestamp=datetime.fromisoformat(when))


def test_breadth_keeps_only_latest_market_local_date_and_real_samples() -> None:
    breadth = _build_breadth([
        _breadth_quote("AAPL", "2026-10-26T00:30:00+00:00"),  # 纽约仍为25日。
        _breadth_quote("NVDA", "2026-10-26T05:30:00+00:00", change="-0.02"),
        _breadth_quote("MSFT", "2026-10-26T06:30:00+00:00", change="0"),
        _breadth_quote("AMD", "2026-10-27T00:00:00+00:00", source="mock_seed"),
        _breadth_quote("META", "2026-10-26T07:00:00+00:00", status="unavailable"),
    ], MarketCode.US)
    assert breadth.sample_size == 2
    assert breadth.excluded_sample_size == 3
    assert breadth.advancers_percent == 0
    assert breadth.decliners_percent == 0.5
    assert breadth.unchanged_percent == 0.5
    assert breadth.sample_sources == ["yahoo_finance"]
    assert breadth.timestamp.isoformat() == "2026-10-26T06:30:00+00:00"
    assert breadth.new_highs is None and breadth.new_lows is None


@pytest.mark.parametrize("source,status", [("mock_seed", "delayed"), ("mock_fallback", "unavailable"),
    ("demo_provider", "realtime"), ("seed", "realtime"), ("", "delayed"), ("yahoo_finance", "unavailable")])
def test_breadth_rejects_sample_and_unavailable_quotes(source: str, status: str) -> None:
    result = _build_breadth([_breadth_quote("NVDA", "2026-10-20T20:00:00", source=source, status=status)], MarketCode.US)
    assert result.sample_size == 0
    assert result.excluded_sample_size == 1
    assert result.advancers_percent is None
    assert result.unchanged_percent is None
    assert result.status == "unavailable"


def test_historical_realtime_label_does_not_make_breadth_realtime() -> None:
    result = _build_breadth([_breadth_quote("NVDA", "2026-10-20T20:00:00", status="realtime")], MarketCode.US)
    assert result.sample_size == 1
    assert result.status == "delayed"
    assert result.advancers_percent == 1
    assert result.decliners_percent == 0
    assert result.new_highs is None  # 当日涨2%不能推断突破历史新高。


@pytest.mark.parametrize("price,change,when", [
    ("NaN", "0.02", "2026-10-20T20:00:00"),
    ("0", "0.02", "2026-10-20T20:00:00"),
    ("100", "Infinity", "2026-10-20T20:00:00"),
    ("100", "0.02", "2999-10-20T20:00:00"),
])
def test_invalid_numeric_values_and_future_dates_are_excluded(price: str, change: str, when: str) -> None:
    quote = _breadth_quote("NVDA", when, change=change)
    quote.price = Decimal(price)
    result = _build_breadth([quote], MarketCode.US)
    assert result.sample_size == 0
    assert result.excluded_sample_size == 1
    assert result.timestamp is None


def test_market_read_service_returns_explicit_empty_pool_without_quotes() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        snapshot = get_market_overview_read_snapshot(
            session,
            MarketCode.CN,
            get_mock_market_overview(MarketCode.CN),
        )

    assert snapshot is not None
    assert snapshot.watchlist == []
    assert snapshot.breadth.sample_size == 0
    assert snapshot.breadth.advancers_percent is None


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

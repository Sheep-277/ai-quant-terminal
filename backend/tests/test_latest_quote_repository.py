from datetime import datetime
from decimal import Decimal

from app.db.repositories.latest_quote_repository import LatestQuoteRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.latest_quote import LatestQuote
from app.models.stock import Stock


def _create_test_session():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return create_session_factory(engine)()


def _add_stock(session, market: str = "US", symbol: str = "NVDA") -> Stock:
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


def _build_quote(stock: Stock, price: str = "181.420000") -> LatestQuote:
    return LatestQuote(
        stock_id=stock.id,
        market=stock.market,
        symbol=stock.symbol,
        price=Decimal(price),
        change_amount=Decimal("2.380000"),
        change_percent=Decimal("0.01330000"),
        volume=218430000,
        turnover=Decimal("39612000000.0000"),
        data_status="delayed",
        source="mock",
        quote_timestamp=datetime(2026, 9, 28, 10, 30, 0),
    )


def test_latest_quote_repository_saves_and_gets_quote_by_market_symbol() -> None:
    session = _create_test_session()
    repository = LatestQuoteRepository(session)
    stock = _add_stock(session)

    quote = repository.save_latest(_build_quote(stock))
    session.commit()

    found = repository.get_by_market_symbol("us", " nvda ")

    assert found == quote
    assert found is not None
    assert found.price == Decimal("181.420000")

    session.close()


def test_latest_quote_repository_updates_existing_quote() -> None:
    session = _create_test_session()
    repository = LatestQuoteRepository(session)
    stock = _add_stock(session)
    repository.save_latest(_build_quote(stock, price="181.420000"))
    session.commit()

    updated_quote = _build_quote(stock, price="188.500000")
    saved_quote = repository.save_latest(updated_quote)
    session.commit()

    quotes = repository.list_by_market("US")
    assert len(quotes) == 1
    assert saved_quote.id == quotes[0].id
    assert quotes[0].price == Decimal("188.500000")

    session.close()


def test_latest_quote_repository_lists_quotes_by_market() -> None:
    session = _create_test_session()
    repository = LatestQuoteRepository(session)
    us_stock = _add_stock(session, market="US", symbol="NVDA")
    hk_stock = _add_stock(session, market="HK", symbol="00700.HK")
    repository.save_latest(_build_quote(us_stock))
    repository.save_latest(_build_quote(hk_stock, price="420.000000"))
    session.commit()

    us_quotes = repository.list_by_market("us")

    assert [quote.symbol for quote in us_quotes] == ["NVDA"]
    assert repository.get_by_market_symbol("CN", "600000") is None

    session.close()

from datetime import datetime

from app.db.repositories.signal_repository import SignalRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.signal import Signal
from app.models.stock import Stock


def _create_stock(
    session,
    *,
    market: str = "US",
    symbol: str = "NVDA",
    name: str = "NVIDIA Corporation",
    exchange: str = "NASDAQ",
    currency: str = "USD",
    timezone: str = "America/New_York",
) -> Stock:
    stock = Stock(
        market=market,
        symbol=symbol,
        name=name,
        exchange=exchange,
        currency=currency,
        timezone=timezone,
    )
    session.add(stock)
    session.flush()
    return stock


def _signal(
    stock: Stock,
    signal_type: str,
    triggered_at: datetime,
    *,
    score: float,
    evidence: list[str] | None = None,
) -> Signal:
    return Signal(
        stock_id=stock.id,
        market=stock.market,
        symbol=stock.symbol,
        signal_type=signal_type,
        direction="positive",
        severity="info",
        score=score,
        evidence=evidence or ["source=test"],
        triggered_at=triggered_at,
        source="test",
    )


def test_signal_repository_returns_latest_signals() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        stock = _create_stock(session)
        repository = SignalRepository(session)

        repository.save_signals([
            _signal(stock, "momentum_strength", datetime(2026, 9, 27, 10, 0), score=0.72),
            _signal(stock, "composite_score_high", datetime(2026, 9, 28, 10, 0), score=0.91),
        ])
        session.commit()

        latest_signals = repository.list_latest_by_market_symbol("us", " nvda ")

        assert [signal.signal_type for signal in latest_signals] == ["composite_score_high", "momentum_strength"]
        assert latest_signals[0].evidence == ["source=test"]


def test_signal_repository_returns_latest_signals_by_market_only() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        us_stock = _create_stock(session)
        hk_stock = _create_stock(
            session,
            market="HK",
            symbol="00700.HK",
            name="Tencent Holdings",
            exchange="HKEX",
            currency="HKD",
            timezone="Asia/Hong_Kong",
        )
        repository = SignalRepository(session)

        repository.save_signals([
            _signal(us_stock, "momentum_strength", datetime(2026, 9, 27, 10, 0), score=0.72),
            _signal(us_stock, "composite_score_high", datetime(2026, 9, 28, 10, 0), score=0.91),
            _signal(hk_stock, "momentum_strength", datetime(2026, 9, 29, 10, 0), score=0.95),
        ])
        session.commit()

        us_signals = repository.list_latest_by_market("us")

        assert [signal.market for signal in us_signals] == ["US", "US"]
        assert [signal.signal_type for signal in us_signals] == ["composite_score_high", "momentum_strength"]


def test_signal_repository_keeps_same_symbol_separated_by_market() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        us_stock = _create_stock(session, market="US", symbol="ABC")
        hk_stock = _create_stock(
            session,
            market="HK",
            symbol="ABC",
            name="ABC HK",
            exchange="HKEX",
            currency="HKD",
            timezone="Asia/Hong_Kong",
        )
        repository = SignalRepository(session)

        repository.save_signals([
            _signal(us_stock, "composite_score_high", datetime(2026, 9, 28, 10, 0), score=0.91),
            _signal(hk_stock, "momentum_strength", datetime(2026, 9, 28, 10, 0), score=0.62),
        ])
        session.commit()

        us_signals = repository.list_latest_by_market_symbol("us", " abc ")
        hk_signals = repository.list_latest_by_market_symbol("hk", " abc ")

        assert [signal.signal_type for signal in us_signals] == ["composite_score_high"]
        assert [signal.signal_type for signal in hk_signals] == ["momentum_strength"]
        assert [signal.score for signal in us_signals] == [0.91]
        assert [signal.score for signal in hk_signals] == [0.62]


def test_signal_repository_updates_existing_signal() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        stock = _create_stock(session)
        repository = SignalRepository(session)
        triggered_at = datetime(2026, 9, 28, 10, 0)

        first = repository.save_signals([
            _signal(stock, "momentum_strength", triggered_at, score=0.72),
        ])[0]
        session.commit()

        updated = repository.save_signals([
            _signal(stock, "momentum_strength", triggered_at, score=0.88, evidence=["score=0.8800"]),
        ])[0]
        session.commit()

        latest_signals = repository.list_latest_by_market_symbol("US", "NVDA")

        assert updated.id == first.id
        assert latest_signals[0].score == 0.88
        assert latest_signals[0].evidence == ["score=0.8800"]

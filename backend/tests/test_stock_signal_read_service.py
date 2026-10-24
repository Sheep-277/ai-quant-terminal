from datetime import datetime

from app.core.market import MarketCode
from app.db.repositories.signal_repository import SignalRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.signal import Signal
from app.models.stock import Stock
from app.services.stock_signal_read_service import get_stock_signal_read_snapshot


def _create_stock(session, *, market: str = "US", symbol: str = "NVDA") -> Stock:
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


def test_stock_signal_read_service_returns_database_signals() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        stock = _create_stock(session)
        SignalRepository(session).save_signals([
            Signal(
                stock_id=stock.id,
                market="US",
                symbol="NVDA",
                signal_type="composite_score_high",
                direction="positive",
                severity="info",
                score=0.93,
                evidence=["composite_score=0.9300"],
                triggered_at=datetime(2026, 9, 28, 10, 30),
                source="test",
            )
        ])
        session.commit()

        snapshot = get_stock_signal_read_snapshot(session, MarketCode.US, " nvda ")

        assert snapshot is not None
        assert snapshot.source == "database"
        assert len(snapshot.quant_signals) == 1
        assert snapshot.quant_signals[0].code == "composite_score_high"
        assert snapshot.quant_signals[0].title == "综合因子评分较高"
        assert snapshot.quant_signals[0].direction == "positive"
        assert snapshot.quant_signals[0].severity == "info"
        assert snapshot.quant_signals[0].score == 0.93
        assert snapshot.quant_signals[0].evidence == ["composite_score=0.9300"]


def test_stock_signal_read_service_returns_none_without_signals() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        snapshot = get_stock_signal_read_snapshot(session, MarketCode.US, "NVDA")

        assert snapshot is None


def test_stock_signal_read_service_keeps_same_symbol_separated_by_market() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        us_stock = _create_stock(session, market="US", symbol="ABC")
        hk_stock = _create_stock(session, market="HK", symbol="ABC")
        repository = SignalRepository(session)
        repository.save_signals([
            Signal(
                stock_id=us_stock.id,
                market="US",
                symbol="ABC",
                signal_type="composite_score_high",
                direction="positive",
                severity="info",
                score=0.91,
                evidence=["US composite_score=0.9100"],
                triggered_at=datetime(2026, 9, 28, 10, 30),
                source="test",
            ),
            Signal(
                stock_id=hk_stock.id,
                market="HK",
                symbol="ABC",
                signal_type="momentum_strength",
                direction="positive",
                severity="warning",
                score=0.62,
                evidence=["HK momentum_20d=0.0500"],
                triggered_at=datetime(2026, 9, 28, 10, 30),
                source="test",
            ),
        ])
        session.commit()

        us_snapshot = get_stock_signal_read_snapshot(session, MarketCode.US, " abc ")
        hk_snapshot = get_stock_signal_read_snapshot(session, MarketCode.HK, " abc ")

        assert us_snapshot is not None
        assert hk_snapshot is not None
        assert [signal.code for signal in us_snapshot.quant_signals] == ["composite_score_high"]
        assert [signal.code for signal in hk_snapshot.quant_signals] == ["momentum_strength"]
        assert us_snapshot.quant_signals[0].score == 0.91
        assert hk_snapshot.quant_signals[0].score == 0.62
        assert us_snapshot.quant_signals[0].evidence == ["US composite_score=0.9100"]
        assert hk_snapshot.quant_signals[0].evidence == ["HK momentum_20d=0.0500"]

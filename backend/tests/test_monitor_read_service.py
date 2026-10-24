from datetime import datetime
import pytest

from app.core.market import MarketCode
from app.db.repositories.signal_repository import SignalRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.signal import Signal
from app.models.stock import Stock
from app.services.mock_monitor_service import get_mock_monitor_stream
from app.services.monitor_read_service import get_monitor_signal_read_snapshot


def _create_stock(session) -> Stock:
    """创建测试股票，满足 signals.stock_id 外键约束。"""

    stock = Stock(
        market="US",
        symbol="NVDA",
        name="NVIDIA Corporation",
        exchange="NASDAQ",
        currency="USD",
        timezone="America/New_York",
    )
    session.add(stock)
    session.flush()
    return stock


def _signal(stock: Stock, *, signal_type: str, severity: str, score: float, source: str = "test") -> Signal:
    """构造一条数据库监控信号，用于验证 service 转换逻辑。"""

    return Signal(
        stock_id=stock.id,
        market=stock.market,
        symbol=stock.symbol,
        signal_type=signal_type,
        direction="positive",
        severity=severity,
        score=score,
        evidence=[f"{signal_type}={score:.4f}"],
        triggered_at=datetime(2026, 9, 28, 10, 30),
        source=source,
    )


def test_monitor_read_service_replaces_signals_and_appends_source_events() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        stock = _create_stock(session)
        SignalRepository(session).save_signals([
            _signal(stock, signal_type="composite_score_high", severity="info", score=0.93),
            _signal(stock, signal_type="volatility_elevated", severity="critical", score=0.88),
        ])
        session.commit()

        fallback = get_mock_monitor_stream(MarketCode.US)
        snapshot = get_monitor_signal_read_snapshot(session, MarketCode.US, fallback)

        assert snapshot is not None
        assert snapshot.timestamp == datetime(2026, 9, 28, 10, 30)
        assert snapshot.stream.last_heartbeat_at == datetime(2026, 9, 28, 10, 30)
        assert snapshot.stream.data_status == "delayed"
        assert snapshot.provenance.transport == "rest_polling"
        assert snapshot.provenance.stream_source == "mock"
        assert snapshot.provenance.signal_source == "database"
        assert snapshot.provenance.event_source == "mixed"
        assert snapshot.provenance.heartbeat_basis == "latest_signal"
        assert fallback.provenance.signal_source == "mock"
        assert fallback.provenance.heartbeat_basis == "mock_clock"
        assert [signal.signal_id for signal in snapshot.signals] == ["db-signal-1", "db-signal-2"]
        assert snapshot.signals[0].title == "综合因子评分较高"
        assert snapshot.signals[0].evidence[-1] == "source=test"
        assert snapshot.signals[0].source == "test"
        assert snapshot.signals[0].data_origin == "unknown"

        events_by_id = {event.event_id: event for event in snapshot.events}
        assert events_by_id["event-us-db-signals"].source == "FAST_PATH"
        assert "最新触发标的为 NVDA" in events_by_id["event-us-db-signals"].summary
        assert "最高严重程度为 critical" in events_by_id["event-us-db-signals"].summary
        assert events_by_id["event-us-db-source-status"].source == "PROVIDER"
        assert "连接状态=connected" in events_by_id["event-us-db-source-status"].summary
        assert "传输方式=REST 轮询" in events_by_id["event-us-db-source-status"].summary
        assert "信号来源=数据库 signals 表" in events_by_id["event-us-db-source-status"].summary
        assert "心跳时间=数据库最新信号时间" in events_by_id["event-us-db-source-status"].summary
        assert events_by_id["event-us-db-risk-summary"].source == "RISK_ENGINE"
        assert "1 条 critical" in events_by_id["event-us-db-risk-summary"].summary
        assert events_by_id["event-us-db-risk-summary"].impact == "warning"


def test_monitor_read_service_returns_none_without_database_signals() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        fallback = get_mock_monitor_stream(MarketCode.US)
        snapshot = get_monitor_signal_read_snapshot(session, MarketCode.US, fallback)

        assert snapshot is None
        assert fallback.provenance.signal_source == "mock"
        assert fallback.stream.data_status == "mock"


@pytest.mark.parametrize("source, expected", [
    ("mock_seed", "seed"),
    ("quant_pipeline", "unknown"),
    ("yahoo_finance", "unknown"),
    ("custom_source", "unknown"),
])
def test_monitor_signal_origin_does_not_infer_live_inputs(source: str, expected: str) -> None:
    """除明确 Seed 来源外，不根据来源名称或证据文字猜测真实输入。"""

    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with create_session_factory(engine)() as session:
        stock = _create_stock(session)
        signal = _signal(stock, signal_type="momentum_strength", severity="info", score=0.8, source=source)
        signal.evidence = ["source=mock_seed", "provider=yahoo_finance"]
        SignalRepository(session).save_signals([signal])
        session.commit()
        snapshot = get_monitor_signal_read_snapshot(session, MarketCode.US, get_mock_monitor_stream(MarketCode.US))
        assert snapshot is not None
        assert snapshot.signals[0].source == source
        assert snapshot.signals[0].data_origin == expected

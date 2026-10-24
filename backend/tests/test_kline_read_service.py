from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.core.market import MarketCode
from app.db.repositories.market_bar_repository import MarketBarRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.market_bar import MarketBar
from app.models.stock import Stock
from app.providers.market_data import MockMarketDataProvider
from app.schemas.market import DataStatus
from app.schemas.stock import KLineInterval
from app.services.kline_read_service import get_kline_read_snapshot
from app.services.mock_stock_service import get_mock_stock_research


def test_kline_read_service_returns_latest_limited_bars_in_ascending_order() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        repository = MarketBarRepository(session)
        us_stock = _add_stock(session, market="US", symbol="ABC")
        hk_stock = _add_stock(session, market="HK", symbol="ABC")
        repository.add_many([_build_bar(us_stock, offset, Decimal(100 + offset), "delayed") for offset in range(35)])
        repository.add_many([_build_bar(hk_stock, 40, Decimal("240.00"), "realtime")])
        session.commit()

        snapshot = get_kline_read_snapshot(
            session,
            MarketCode.US,
            " abc ",
            interval=KLineInterval.ONE_DAY,
            limit=30,
        )

    assert snapshot is not None
    assert snapshot.source == "database"
    assert snapshot.kline.interval == KLineInterval.ONE_DAY
    assert snapshot.kline.data_status == "delayed"
    assert len(snapshot.kline.bars) == 30
    assert snapshot.kline.bars[0].timestamp == datetime(2026, 9, 6, 0, 0)
    assert snapshot.kline.bars[-1].timestamp == datetime(2026, 10, 5, 0, 0)
    assert snapshot.kline.bars[0].close == 105.0
    assert snapshot.kline.bars[-1].close == 134.0


def test_kline_read_service_returns_none_without_bars() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        snapshot = get_kline_read_snapshot(session, MarketCode.CN, "600519.SH")

    assert snapshot is None


@pytest.mark.parametrize("market,symbol", [(MarketCode.US, "NVDA"), (MarketCode.HK, "00700.HK"), (MarketCode.CN, "600519.SH")])
@pytest.mark.parametrize("field,value", [("high_price", Decimal("90")), ("low_price", Decimal("110")), ("volume", -1)])
def test_invalid_database_bars_are_unavailable_without_mock_replacement(
    monkeypatch: pytest.MonkeyPatch, market: MarketCode, symbol: str, field: str, value: Decimal | int,
) -> None:
    """坏记录留在数据库，页面仍可获得报价，但不展示坏 K 线或用样例替代。"""

    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    provider = MockMarketDataProvider()
    monkeypatch.setattr("app.services.mock_stock_service.get_market_data_provider", lambda: provider)

    def unexpected_bars(*args, **kwargs):
        raise AssertionError("异常数据库快照不得被 Provider K 线替换")

    monkeypatch.setattr(provider, "get_bars", unexpected_bars)
    with create_session_factory(engine)() as session:
        stock = _add_stock(session, market=market.value, symbol=symbol)
        bar = _build_bar(stock, 0, Decimal("100"), "delayed")
        original_value = getattr(bar, field)
        setattr(bar, field, value)
        session.add(bar)
        session.add(_build_bar(stock, 1, Decimal("101"), "delayed"))
        session.commit()

        snapshot = get_kline_read_snapshot(session, market, symbol)
        assert snapshot is not None
        assert snapshot.source == "database"
        assert snapshot.kline.data_status == DataStatus.UNAVAILABLE
        assert snapshot.kline.bars == []
        assert "校验失败" in snapshot.detail
        session.refresh(bar)
        assert getattr(bar, field) == value

        response = get_mock_stock_research(market, symbol, kline_read_snapshot=snapshot)
        assert response.quote.price > 0
        assert response.kline.bars == []
        assert response.kline_data_source.source == "database"
        assert response.kline_data_source.detail == snapshot.detail
        assert response.kline_data_source.fallback_active is False
        assert response.kline_data_source.data_status == DataStatus.UNAVAILABLE
        assert response.technical_data_source.data_status == DataStatus.UNAVAILABLE
        assert response.summary_data_source.data_status == DataStatus.UNAVAILABLE
        assert response.technical.rsi_14 is None
        assert response.technical.macd is None
        assert response.factor_snapshot.momentum_20d is None
        assert any("K 线数据不可用" in flag for flag in response.risk_flags)

        # 模拟数据维护后下一次读取恢复，不需要服务保存额外的错误状态。
        setattr(bar, field, original_value)
        session.commit()
        restored = get_kline_read_snapshot(session, market, symbol)
        assert restored is not None
        assert restored.kline.data_status == DataStatus.DELAYED
        assert len(restored.kline.bars) == 2
        assert "校验失败" not in restored.detail
    engine.dispose()


def test_database_query_errors_are_not_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    """仅处理数据校验失败，不将连接故障或程序错误吞成行情不可用。"""

    def broken_query(*args, **kwargs):
        raise RuntimeError("database query failed")

    monkeypatch.setattr(MarketBarRepository, "list_latest", broken_query)
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    with create_session_factory(engine)() as session:
        with pytest.raises(RuntimeError, match="database query failed"):
            get_kline_read_snapshot(session, MarketCode.US, "NVDA")
    engine.dispose()


def _add_stock(session, *, market: str, symbol: str) -> Stock:
    """构造 K 线读取测试所需的股票基础信息。"""

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


def _build_bar(stock: Stock, offset: int, close_price: Decimal, data_status: str) -> MarketBar:
    """构造 market_bars 记录，模拟 Provider 写入的日线 K 线。"""

    timestamp = datetime(2026, 9, 1, 0, 0, 0) + timedelta(days=offset)
    return MarketBar(
        stock_id=stock.id,
        market=stock.market,
        symbol=stock.symbol,
        interval_code="1d",
        bar_timestamp=timestamp,
        open_price=close_price - Decimal("1.00"),
        high_price=close_price + Decimal("2.00"),
        low_price=close_price - Decimal("2.00"),
        close_price=close_price,
        volume=1_000 + offset,
        source="test",
        data_status=data_status,
    )

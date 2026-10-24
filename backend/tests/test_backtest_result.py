import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.v1.backtest import build_backtest_by_id_response, build_backtest_result_response, build_backtest_task_response
from app.core.config import Settings, get_settings
from app.core.market import MarketCode
from app.db.init_db import init_database
from app.db.session import create_database_engine, get_engine, get_session_factory
from app.main import app
from app.schemas.backtest import BacktestDataMode, BacktestRequest, BacktestStatus, BacktestTaskCreateResponse
from app.schemas.market import DataStatus
from app.schemas.strategy import StrategyStatus
from app.services.backtest_read_service import get_backtest_snapshot_by_id
from app.services.backtest_write_service import save_backtest_result
from app.services.backtest_result_service import create_backtest_task_receipt, get_backtest_result
from app.services.backtest_result_service import get_mock_backtest_result


client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_backtest_database_reads_by_default(monkeypatch: pytest.MonkeyPatch):
    """大多数接口测试验证默认 Mock 行为，避免本地 .env 影响测试结果。"""

    monkeypatch.setenv("ENABLE_BACKTEST_DATABASE_READS", "false")
    monkeypatch.setenv("ENABLE_BACKTEST_DATABASE_WRITES", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_backtest_result_defaults_to_us() -> None:
    # 不传 market 时应返回默认美股 Mock 回测结果。
    response = client.get("/api/v1/backtest/result")

    assert response.status_code == 200
    payload = response.json()
    assert payload["market"] == "US"
    assert payload["status"] == "completed"
    assert payload["data_mode"] == "mock"
    assert payload["currency"] == "USD"
    assert payload["performance"]["initial_capital"] > 0
    assert payload["performance"]["final_value"] == pytest.approx(payload["equity_curve"][-1]["equity"])
    assert payload["equity_curve"]
    assert payload["trades"][0]["side"] == "buy"
    assert payload["trades"][-1]["side"] == "sell"


def test_backtest_result_supports_all_v1_markets() -> None:
    # 回测结果必须显式绑定市场、币种和基准，避免跨市场口径混用。
    expected = {
        "US": ("USD", "S&P 500"),
        "HK": ("HKD", "Hang Seng Index"),
        "CN": ("CNY", "CSI 300"),
    }

    for market, (currency, benchmark) in expected.items():
        response = client.get("/api/v1/backtest/result", params={"market": market})

        assert response.status_code == 200
        payload = response.json()
        assert payload["market"] == market
        assert payload["currency"] == currency
        assert payload["benchmark"] == benchmark
        assert payload["performance"]["trade_count"] == 1
        assert len(payload["equity_curve"]) == 12
        assert payload["trades"]
        assert all(trade["fee"] >= 0 and trade["slippage"] >= 0 for trade in payload["trades"])


def test_backtest_result_contains_mock_safety_assumptions() -> None:
    # 当前阶段只允许 Mock 回测，不应让用户误解为真实可交易结果。
    response = client.get("/api/v1/backtest/result", params={"market": "CN"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_mode"] == "mock"
    assert any("Mock" in item for item in payload["assumptions"])


def test_backtest_result_can_use_provider_history_when_real_mode() -> None:
    # real 模式下，回测服务应优先把 Provider K 线送入确定性回测引擎。
    response = get_backtest_result(
        MarketCode.US,
        settings=Settings(
            DATA_PROVIDER="real",
            REAL_PROVIDER_NAME="DemoProvider",
            _env_file=None,
        ),
        provider=_FakeBacktestProvider(),
    )

    assert response.market == MarketCode.US
    assert response.data_mode == BacktestDataMode.HISTORICAL
    assert response.backtest_id == "historical-us-backtest-001"
    assert response.start_date.isoformat() == "2025-01-01"
    assert response.end_date.isoformat() == "2025-01-03"
    assert len(response.equity_curve) == 3
    assert response.performance.trade_count == 1
    assert any("Provider 历史 K 线" in item for item in response.assumptions)


def test_backtest_result_falls_back_to_mock_when_provider_history_fails() -> None:
    # 真实 Provider 超时或异常时，页面仍应可展示 Mock 结果并说明回退原因。
    response = get_backtest_result(
        MarketCode.US,
        settings=Settings(
            DATA_PROVIDER="real",
            REAL_PROVIDER_NAME="DemoProvider",
            _env_file=None,
        ),
        provider=_FailingBacktestProvider(),
    )

    assert response.data_mode == BacktestDataMode.MOCK
    assert response.backtest_id == "mock-us-backtest-001"
    assert any("真实历史行情读取失败" in item for item in response.assumptions)
    assert any("RuntimeError" in item for item in response.assumptions)


def test_backtest_result_falls_back_when_provider_returns_marked_mock_bars() -> None:
    # RealMarketDataProvider 内部回退出的 Mock K 线不能被误标成 historical。
    response = get_backtest_result(
        MarketCode.US,
        settings=Settings(
            DATA_PROVIDER="real",
            REAL_PROVIDER_NAME="DemoProvider",
            _env_file=None,
        ),
        provider=_FallbackBarsProvider(),
    )

    assert response.data_mode == BacktestDataMode.MOCK
    assert response.backtest_id == "mock-us-backtest-001"
    assert any("真实历史行情读取失败" in item for item in response.assumptions)


def test_backtest_result_can_use_database_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    init_database(engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)
    session_factory = get_session_factory(database_url)
    mock_response = get_mock_backtest_result(MarketCode.HK)
    with session_factory() as session:
        save_backtest_result(session, mock_response)

    response = build_backtest_result_response(
        MarketCode.HK,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_BACKTEST_DATABASE_READS=True,
            _env_file=None,
        ),
    )

    assert response.backtest_id == "mock-hk-backtest-001"
    assert response.market == MarketCode.HK
    assert response.performance.final_value == round(mock_response.performance.final_value, 6)
    assert len(response.equity_curve) == len(mock_response.equity_curve)


def test_backtest_result_appends_fallback_assumption_when_database_read_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)

    def raise_database_read_error(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("app.api.v1.backtest.get_latest_backtest_snapshot", raise_database_read_error)

    response = build_backtest_result_response(
        MarketCode.US,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_BACKTEST_DATABASE_READS=True,
            _env_file=None,
        ),
    )

    assert response.backtest_id == "mock-us-backtest-001"
    assert response.data_mode == "mock"
    assert any("数据库回测结果读取失败" in item for item in response.assumptions)
    assert any("RuntimeError" in item for item in response.assumptions)


def test_backtest_result_rejects_unknown_market() -> None:
    # 未支持市场必须返回参数校验错误，避免套用错误市场规则。
    response = client.get("/api/v1/backtest/result", params={"market": "EU"})

    assert response.status_code == 422


def test_create_backtest_task_returns_pending_receipt() -> None:
    # POST 创建回测任务当前只返回 Mock 接收回执，不运行真实异步回测。
    request = _build_backtest_request()

    response = client.post("/api/v1/backtests", json=request.model_dump(mode="json"))

    assert response.status_code == 202
    payload = response.json()
    assert payload["backtest_id"] == "backtest-us-mock-us-momentum-quality-draft"
    assert payload["strategy_id"] == request.strategy_id
    assert payload["market"] == "US"
    assert payload["status"] == "pending"
    assert payload["data_mode"] == "mock"
    assert payload["poll_url"] == "/api/v1/backtests/backtest-us-mock-us-momentum-quality-draft"


def test_create_backtest_task_can_write_database(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    init_database(engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)
    request = _build_backtest_request()

    receipt = build_backtest_task_response(
        request,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_BACKTEST_DATABASE_WRITES=True,
            _env_file=None,
        ),
    )

    session_factory = get_session_factory(database_url)
    with session_factory() as session:
        snapshot = get_backtest_snapshot_by_id(session, receipt.backtest_id)

    assert receipt.backtest_id == "backtest-us-mock-us-momentum-quality-draft"
    assert receipt.status == BacktestStatus.PENDING
    assert receipt.data_mode == BacktestDataMode.MOCK
    assert receipt.result_data_mode == BacktestDataMode.MOCK
    assert snapshot is not None
    assert snapshot.response.backtest_id == receipt.backtest_id
    assert snapshot.response.strategy_id == request.strategy_id
    assert snapshot.response.market == MarketCode.US
    assert snapshot.response.data_mode == BacktestDataMode.MOCK


def test_create_backtest_task_does_not_mislabel_mock_snapshot_as_historical(monkeypatch: pytest.MonkeyPatch) -> None:
    # 请求 historical 但当前环境只能生成 Mock 结果时，保存快照必须保留真实生成结果的数据模式。
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    init_database(engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)
    request = _build_backtest_request(data_mode=BacktestDataMode.HISTORICAL)

    receipt = build_backtest_task_response(
        request,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_BACKTEST_DATABASE_WRITES=True,
            DATA_PROVIDER="mock",
            _env_file=None,
        ),
    )

    session_factory = get_session_factory(database_url)
    with session_factory() as session:
        snapshot = get_backtest_snapshot_by_id(session, receipt.backtest_id)

    assert receipt.data_mode == BacktestDataMode.HISTORICAL
    assert receipt.result_data_mode == BacktestDataMode.MOCK
    assert snapshot is not None
    assert snapshot.response.data_mode == BacktestDataMode.MOCK


def test_create_backtest_task_marks_fallback_when_database_write_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_database_write_error(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)
    monkeypatch.setattr("app.api.v1.backtest.save_backtest_result", raise_database_write_error)

    receipt = build_backtest_task_response(
        _build_backtest_request(),
        Settings(
            DATABASE_URL=database_url,
            ENABLE_BACKTEST_DATABASE_WRITES=True,
            _env_file=None,
        ),
    )

    assert receipt.backtest_id == "backtest-us-mock-us-momentum-quality-draft"
    assert receipt.status == BacktestStatus.PENDING
    assert receipt.data_status == "unavailable"
    assert receipt.fallback_active is True
    assert receipt.storage_source == "mock_fallback"
    assert "RuntimeError" in receipt.fallback_reason
    assert "未持久化回测任务回执" in receipt.fallback_reason


def test_backtest_poll_url_can_read_database_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    init_database(engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)
    request = _build_backtest_request()

    receipt = build_backtest_task_response(
        request,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_BACKTEST_DATABASE_WRITES=True,
            _env_file=None,
        ),
    )
    response = build_backtest_by_id_response(
        receipt.backtest_id,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_BACKTEST_DATABASE_READS=True,
            _env_file=None,
        ),
    )

    assert receipt.poll_url == f"/api/v1/backtests/{receipt.backtest_id}"
    assert response.backtest_id == receipt.backtest_id
    assert response.strategy_id == request.strategy_id
    assert response.market == MarketCode.US
    assert response.equity_curve
    assert response.trades


def test_backtest_poll_url_returns_404_when_snapshot_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    init_database(engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)

    with pytest.raises(HTTPException) as error:
        build_backtest_by_id_response(
            "missing-backtest-id",
            Settings(
                DATABASE_URL=database_url,
                ENABLE_BACKTEST_DATABASE_READS=True,
                _env_file=None,
            ),
        )

    assert error.value.status_code == 404
    assert error.value.detail["code"] == "backtest_result_not_found"
    assert error.value.detail["backtest_id"] == "missing-backtest-id"


def test_backtest_poll_url_returns_404_when_database_reads_disabled() -> None:
    with pytest.raises(HTTPException) as error:
        build_backtest_by_id_response(
            "backtest-us-mock-us-momentum-quality-draft",
            Settings(
                ENABLE_BACKTEST_DATABASE_READS=False,
                _env_file=None,
            ),
        )

    assert error.value.status_code == 404
    assert error.value.detail["code"] == "backtest_database_reads_disabled"
    assert error.value.detail["backtest_id"] == "backtest-us-mock-us-momentum-quality-draft"


def test_create_backtest_task_rejects_draft_strategy() -> None:
    # HTTP 层应复用 BacktestRequest 校验，草案策略不能直接发起回测。
    request = _build_backtest_request().model_dump(mode="json")
    request["strategy_status"] = "draft"

    response = client.post("/api/v1/backtests", json=request)

    assert response.status_code == 422


def test_backtest_request_accepts_confirmed_strategy_with_sample_split() -> None:
    # 只有用户确认后的策略才能进入回测请求，样本切分点必须在回测区间内部。
    request = _build_backtest_request()

    assert request.strategy_status == StrategyStatus.CONFIRMED
    assert request.data_mode == BacktestDataMode.MOCK
    assert request.sample_split_at.isoformat() == "2025-07-01"


def test_backtest_request_rejects_draft_strategy() -> None:
    # 草案策略不能直接回测，必须先经过用户确认。
    with pytest.raises(ValidationError, match="strategy_status must be confirmed"):
        _build_backtest_request(strategy_status=StrategyStatus.DRAFT)


def test_backtest_request_rejects_invalid_sample_split() -> None:
    # 样本切分不能落在区间外，否则样本内/样本外验证没有意义。
    with pytest.raises(ValidationError, match="sample_split_at must be between"):
        _build_backtest_request(sample_split_at="2026-01-01")


def test_backtest_task_create_response_accepts_relative_poll_url() -> None:
    # 回测创建回执只允许返回站内轮询地址，前端据此查询任务状态。
    response = BacktestTaskCreateResponse(
        backtest_id="backtest-us-001",
        strategy_id="mock-us-momentum-quality-draft",
        market="US",
        status=BacktestStatus.PENDING,
        accepted_at="2026-09-07T00:00:00Z",
        data_mode=BacktestDataMode.MOCK,
        timezone="America/New_York",
        currency="USD",
        poll_url="/api/v1/backtests/backtest-us-001",
    )

    assert response.poll_url == "/api/v1/backtests/backtest-us-001"


def test_backtest_task_create_response_rejects_external_poll_url() -> None:
    # 不能让后端在回执里返回外部地址，避免前端轮询被引到非本站资源。
    with pytest.raises(ValidationError, match="poll_url must not be an external URL"):
        BacktestTaskCreateResponse(
            backtest_id="backtest-us-001",
            strategy_id="mock-us-momentum-quality-draft",
            market="US",
            status=BacktestStatus.PENDING,
            accepted_at="2026-09-07T00:00:00Z",
            data_mode=BacktestDataMode.MOCK,
            timezone="America/New_York",
            currency="USD",
            poll_url="https://example.com/backtests/backtest-us-001",
        )


def test_create_backtest_task_receipt_returns_pending_receipt() -> None:
    # 回测 service 只返回任务接收回执，不运行真实异步回测任务。
    request = _build_backtest_request()

    response = create_backtest_task_receipt(request)

    assert response.backtest_id == "backtest-us-mock-us-momentum-quality-draft"
    assert response.strategy_id == request.strategy_id
    assert response.market == request.market
    assert response.status == BacktestStatus.PENDING
    assert response.data_mode == BacktestDataMode.MOCK
    assert response.timezone == "America/New_York"
    assert response.currency == "USD"
    assert response.poll_url == "/api/v1/backtests/backtest-us-mock-us-momentum-quality-draft"


def _build_backtest_request(
    *,
    strategy_status: StrategyStatus = StrategyStatus.CONFIRMED,
    sample_split_at: str = "2025-07-01",
    data_mode: BacktestDataMode = BacktestDataMode.MOCK,
) -> BacktestRequest:
    """构造最小合法回测请求，便于测试请求边界。"""

    return BacktestRequest(
        market="US",
        strategy_id="mock-us-momentum-quality-draft",
        strategy_status=strategy_status,
        data_mode=data_mode,
        start_date="2025-01-01",
        end_date="2025-12-31",
        sample_split_at=sample_split_at,
        initial_capital=100_000,
        benchmark="S&P 500",
    )


class _FakeBacktestProvider:
    """测试用 Provider，只实现本轮回测服务会调用的最小方法。"""

    def get_provider_status(self):
        return {
            "provider_name": "DemoProvider",
            "mode": "real",
            "ready": True,
            "data_status": DataStatus.DELAYED,
            "fallback_active": False,
            "fallback_reason": None,
            "active_source": "demo_provider",
        }

    def get_bars(self, *_args, **_kwargs):
        return [
            {"offset": 2, "timestamp": "2025-01-01T00:00:00+00:00", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
            {"offset": 1, "timestamp": "2025-01-02T00:00:00+00:00", "open": 102, "high": 103, "low": 101, "close": 102, "volume": 1100},
            {"offset": 0, "timestamp": "2025-01-03T00:00:00+00:00", "open": 104, "high": 105, "low": 103, "close": 104, "volume": 1200},
        ]


class _FailingBacktestProvider(_FakeBacktestProvider):
    """测试真实行情不可用时的 Mock 回退路径。"""

    def get_bars(self, *_args, **_kwargs):
        raise RuntimeError("provider unavailable")


class _FallbackBarsProvider(_FakeBacktestProvider):
    """测试真实 Provider 内部返回已标记的 Mock 回退 K 线。"""

    def get_bars(self, *_args, **_kwargs):
        return [
            {
                "offset": 1,
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 1000,
                "data_status": DataStatus.UNAVAILABLE,
                "source": "mock_fallback",
            },
            {
                "offset": 0,
                "open": 101,
                "high": 102,
                "low": 100,
                "close": 101,
                "volume": 1100,
                "data_status": DataStatus.UNAVAILABLE,
                "source": "mock_fallback",
            },
        ]

import pytest
from pydantic import ValidationError

from app.api.v1.monitor import build_monitor_stream_response
from app.core.config import Settings, get_settings
from app.core.market import MarketCode
from app.db.seed import seed_development_data
from app.db.session import create_database_engine, get_engine, get_session_factory
from app.schemas.monitor import MonitorProvenance, MonitorResponse


@pytest.fixture(autouse=True)
def disable_monitor_database_reads_by_default(monkeypatch: pytest.MonkeyPatch):
    """多数 Monitor 测试验证默认 Mock 行为，避免本地 .env 影响测试结果。"""

    monkeypatch.setenv("ENABLE_MONITOR_DATABASE_READS", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _build_mock_stream(market: MarketCode = MarketCode.US):
    """直接测试实时监控响应构造逻辑，避开当前环境中 TestClient.get 阻塞问题。"""

    return build_monitor_stream_response(
        market=market,
        settings=Settings(
            ENABLE_MONITOR_DATABASE_READS=False,
            _env_file=None,
        ),
    )


def test_monitor_stream_can_use_database_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    seed_development_data(engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_settings.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)

    response = build_monitor_stream_response(
        market=MarketCode.US,
        settings=Settings(
            DATABASE_URL=database_url,
            ENABLE_MONITOR_DATABASE_READS=True,
            _env_file=None,
        ),
    )

    assert response.market == MarketCode.US
    assert response.signals
    assert response.signals[0].signal_id.startswith("db-signal-")
    assert response.signals[0].evidence[-1] == "source=mock_seed"
    assert response.signals[0].source == "mock_seed"
    assert response.signals[0].data_origin == "seed"
    assert response.provenance.signal_source == "database"
    assert response.provenance.stream_source == "mock"
    assert response.provenance.heartbeat_basis == "latest_signal"
    assert response.provenance.event_source == "mixed"
    assert response.stream.data_status == "delayed"
    assert any(
        event.source == "FAST_PATH" and event.event_id == "event-us-db-signals"
        for event in response.events
    )
    assert any(
        event.source == "RISK_ENGINE" and event.event_id == "event-us-db-risk-summary"
        for event in response.events
    )
    assert any(
        event.source == "PROVIDER" and event.event_id == "event-us-db-source-status"
        for event in response.events
    )


def test_monitor_stream_appends_fallback_event_when_database_read_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_settings.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)

    def raise_database_read_error(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("app.api.v1.monitor.get_monitor_signal_read_snapshot", raise_database_read_error)

    response = build_monitor_stream_response(
        market=MarketCode.US,
        settings=Settings(
            DATABASE_URL=database_url,
            ENABLE_MONITOR_DATABASE_READS=True,
            _env_file=None,
        ),
    )

    fallback_event = next(
        event for event in response.events if event.event_id == "event-us-db-read-fallback"
    )
    assert response.signals[0].signal_id == "signal-us-001"
    assert fallback_event.source == "PROVIDER"
    assert fallback_event.impact == "warning"
    assert "RuntimeError" in fallback_event.summary
    assert response.stream.data_status == "mock"
    assert response.provenance.signal_source == "mock"
    assert response.provenance.stream_source == "mock"
    assert response.provenance.heartbeat_basis == "mock_clock"
    assert response.provenance.event_source == "mixed"


def test_monitor_stream_defaults_to_us() -> None:
    # 不传 market 时应返回默认美股实时监控 Mock 数据。
    payload = _build_mock_stream()

    assert payload.market == MarketCode.US
    assert payload.currency == "USD"
    assert payload.stream.status == "connected"
    assert payload.signals
    assert payload.signals[0].evidence[-1] == "source=ToolRegistry.run_quant_pipeline"


def test_monitor_stream_supports_all_v1_markets() -> None:
    # Monitor 数据必须显式绑定市场和币种，避免跨市场信号混用。
    expected = {
        MarketCode.US: "USD",
        MarketCode.HK: "HKD",
        MarketCode.CN: "CNY",
    }

    for market, currency in expected.items():
        payload = _build_mock_stream(market)

        assert payload.market == market
        assert payload.currency == currency
        assert all(signal.market == market for signal in payload.signals)
        assert all(signal.data_origin == "mock" for signal in payload.signals)
        assert payload.signals[0].source == "mock_quant_pipeline"
        assert all(event.market == market for event in payload.events)
        assert payload.stream.data_status == "mock"
        assert payload.model_dump(mode="json")["provenance"] == {
            "transport": "rest_polling",
            "stream_source": "mock",
            "signal_source": "mock",
            "event_source": "mock",
            "heartbeat_basis": "mock_clock",
        }


def test_monitor_provenance_defaults_to_unknown_for_legacy_payload() -> None:
    """缺少来源的旧快照不能自动标成真实或 Mock 数据。"""

    payload = _build_mock_stream().model_dump(mode="json")
    payload.pop("provenance")
    response = MonitorResponse.model_validate(payload)
    assert set(response.provenance.model_dump().values()) == {"unknown"}


def test_legacy_signal_source_is_unknown() -> None:
    """旧版本缺少逐条来源时，不从 evidence 中补造分类。"""

    payload = _build_mock_stream().model_dump(mode="json")
    for signal in payload["signals"]:
        signal.pop("source")
        signal.pop("data_origin")
    response = MonitorResponse.model_validate(payload)
    assert all(signal.source is None and signal.data_origin == "unknown" for signal in response.signals)


@pytest.mark.parametrize("field", [
    "transport", "stream_source", "signal_source", "event_source", "heartbeat_basis",
])
def test_monitor_provenance_rejects_unsupported_sources(field: str) -> None:
    """来源必须遵循合同，不允许把供应商名称当成已实现的监控连接来源。"""

    with pytest.raises(ValidationError):
        MonitorProvenance.model_validate({field: "yahoo_finance"})


def test_monitor_stream_keeps_fast_and_ai_path_visible() -> None:
    # 响应需要让前端区分确定性 FAST PATH 和解释型 AI PATH。
    payload = _build_mock_stream(MarketCode.CN)

    sources = {event.source for event in payload.events}
    assert "FAST_PATH" in sources
    assert "AI_PATH" in sources
    assert all(signal.evidence for signal in payload.signals)
    assert payload.signals[0].signal_id == "signal-cn-001"


@pytest.mark.parametrize("market", list(MarketCode))
def test_monitor_stream_mock_status_contains_truthful_provider_event(market: MarketCode) -> None:
    """模拟路径不得伪造 Provider 读到了延迟行情。"""

    payload = _build_mock_stream(market)

    provider_events = [
        event for event in payload.events if event.source == "PROVIDER"
    ]
    assert payload.stream.data_status == "mock"
    assert provider_events
    assert any("来自 Mock Monitor" in event.summary for event in provider_events)
    assert all("Provider 返回 delayed" not in event.summary for event in provider_events)


def test_monitor_stream_event_summary_has_severity_prefix() -> None:
    # 事件摘要应统一带严重程度前缀，方便前端用同一规则展示。
    payload = _build_mock_stream(MarketCode.US)

    assert all(
        event.summary.startswith(("信息：", "警告："))
        for event in payload.events
    )


def test_monitor_stream_rejects_unknown_market() -> None:
    # 未支持市场必须返回参数校验错误，不能套用默认市场监控流。
    with pytest.raises(ValueError):
        MarketCode("EU")

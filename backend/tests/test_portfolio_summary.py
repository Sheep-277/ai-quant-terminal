import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.v1.portfolio import build_paper_order_response, build_portfolio_summary_response
from app.core.config import Settings, get_settings
from app.core.market import MarketCode
from app.db.seed import seed_development_data
from app.db.repositories.portfolio_repository import PortfolioRepository
from app.db.session import create_database_engine, get_engine, get_session_factory
from app.main import app
from app.schemas.market import DataStatus
from app.schemas.portfolio import (
    PaperOrderCreateResponse,
    PaperOrderRequest,
    PaperOrderRiskDecision,
    PaperOrderSide,
    PaperOrderStatus,
    PortfolioDataMode,
)
from app.services.mock_portfolio_service import create_mock_paper_order, get_portfolio_summary


client = TestClient(app)


class _FakePortfolioProvider:
    """测试用行情 Provider，只实现组合重估需要的 quote 能力。"""

    quotes = {
        "NVDA": {"price": 200.0, "change": 2.0, "change_percent": 0.01},
        "MSFT": {"price": 550.0, "change": 3.0, "change_percent": 0.0055},
        "AMD": {"price": 180.0, "change": 1.5, "change_percent": 0.0083},
    }

    def get_provider_status(self) -> dict:
        return {
            "provider_name": "fake",
            "active_source": "fake_public_quote",
            "data_status": DataStatus.DELAYED,
        }

    def get_quote(self, market: MarketCode, symbol: str) -> dict:
        quote = self.quotes[symbol]
        return {
            "market": market,
            "symbol": symbol,
            "price": quote["price"],
            "change": quote["change"],
            "change_percent": quote["change_percent"],
            "volume": 1000,
            "turnover": 100000.0,
            "data_status": DataStatus.DELAYED,
        }


class _UnavailablePortfolioProvider(_FakePortfolioProvider):
    """测试 Provider 不可用时，组合页必须退回 Mock 估值。"""

    def get_quote(self, market: MarketCode, symbol: str) -> dict:
        quote = super().get_quote(market, symbol)
        quote["data_status"] = DataStatus.UNAVAILABLE
        return quote


@pytest.fixture(autouse=True)
def disable_portfolio_database_reads_by_default(monkeypatch: pytest.MonkeyPatch):
    """大多数接口测试验证默认 Mock 行为，避免本地 .env 影响测试结果。"""

    monkeypatch.setenv("DATA_PROVIDER", "mock")
    monkeypatch.setenv("ENABLE_PORTFOLIO_DATABASE_READS", "false")
    monkeypatch.setattr(
        "app.api.v1.portfolio.get_settings",
        lambda: Settings(
            DATA_PROVIDER="mock",
            ENABLE_PORTFOLIO_DATABASE_READS=False,
            _env_file=None,
        ),
    )
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_portfolio_summary_defaults_to_us() -> None:
    # 不传 market 时应返回默认美股模拟组合摘要。
    response = client.get("/api/v1/portfolio/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["market"] == "US"
    assert payload["data_mode"] == "mock"
    assert payload["currency"] == "USD"
    assert payload["account"]["nav"] > 0
    assert payload["account"]["nav"] == pytest.approx(
        payload["account"]["cash"] + payload["account"]["market_value"]
    )
    assert payload["positions"]


def test_portfolio_summary_supports_all_v1_markets() -> None:
    # Portfolio 必须显式绑定市场和币种，避免不同市场资产口径混用。
    expected = {
        "US": "USD",
        "HK": "HKD",
        "CN": "CNY",
    }

    for market, currency in expected.items():
        response = client.get("/api/v1/portfolio/summary", params={"market": market})

        assert response.status_code == 200
        payload = response.json()
        assert payload["market"] == market
        assert payload["currency"] == currency
        assert payload["account"]["market"] == market
        assert all(position["market"] == market for position in payload["positions"])


def test_portfolio_summary_contains_mock_orders_and_risk() -> None:
    # 当前阶段只允许模拟订单，并且响应必须包含组合级风险摘要。
    response = client.get("/api/v1/portfolio/summary", params={"market": "CN"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["orders"]
    assert all(order["status"] == "filled" for order in payload["orders"])
    assert payload["risk"]["gross_exposure"] >= 0
    assert payload["risk"]["gross_exposure"] == payload["risk"]["net_exposure"]
    assert payload["risk"]["gross_exposure"] == pytest.approx(
        payload["account"]["market_value"] / payload["account"]["nav"],
        abs=0.0001,
    )
    assert payload["risk"]["largest_position_weight"] == max(
        position["weight"] for position in payload["positions"]
    )
    assert payload["risk"]["risk_flags"]
    assert any("模拟交易" in item for item in payload["risk"]["risk_flags"])


def test_portfolio_summary_can_reprice_positions_with_provider_quotes() -> None:
    # DATA_PROVIDER=real 时，模拟组合的持仓最新价可以由真实行情 Provider 重估。
    response = get_portfolio_summary(
        MarketCode.US,
        settings=Settings(
            DATA_PROVIDER="real",
            REAL_PROVIDER_NAME="FakeProvider",
            _env_file=None,
        ),
        provider=_FakePortfolioProvider(),
    )

    assert response.data_mode == PortfolioDataMode.PAPER
    assert response.positions[0].symbol == "NVDA"
    assert response.positions[0].last_price == 200.0
    assert response.account.market_value == pytest.approx(180 * 200 + 80 * 550 + 120 * 180)
    assert response.account.daily_pnl == pytest.approx(180 * 2 + 80 * 3 + 120 * 1.5)
    assert any("Provider 行情" in item for item in response.risk.risk_flags)
    assert any("模拟账户" in item for item in response.risk.risk_flags)


def test_portfolio_summary_falls_back_when_provider_quote_is_unavailable() -> None:
    # Provider 返回不可用行情时，页面继续展示 Mock 组合并暴露回退原因。
    response = get_portfolio_summary(
        MarketCode.US,
        settings=Settings(
            DATA_PROVIDER="real",
            REAL_PROVIDER_NAME="FakeProvider",
            _env_file=None,
        ),
        provider=_UnavailablePortfolioProvider(),
    )

    assert response.data_mode == PortfolioDataMode.MOCK
    assert response.positions[0].last_price == 181.42
    assert any("真实持仓行情读取失败" in item for item in response.risk.risk_flags)
    assert any("ValueError" in item for item in response.risk.risk_flags)
    assert any("symbol=NVDA" in item for item in response.risk.risk_flags)
    assert any("status=unavailable" in item for item in response.risk.risk_flags)


def test_portfolio_summary_can_use_database_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    # 开启数据库读取后，组合页优先展示 seed 写入的本地模拟组合快照。
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    seed_development_data(engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)

    response = build_portfolio_summary_response(
        MarketCode.US,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_PORTFOLIO_DATABASE_READS=True,
            _env_file=None,
        ),
    )

    assert response.market == MarketCode.US
    assert response.account.account_id == "paper-us-001"
    assert response.account.currency == "USD"
    assert len(response.positions) == 3
    assert len(response.orders) == 2
    assert response.risk.risk_flags


def test_portfolio_summary_prefers_provider_pricing_when_real_mode_and_database_reads_are_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # real 模式下，组合摘要优先展示 Provider 重估结果，避免 seed 数据库快照覆盖真实行情估值。
    provider_response = get_portfolio_summary(
        MarketCode.US,
        settings=Settings(
            DATA_PROVIDER="real",
            REAL_PROVIDER_NAME="FakeProvider",
            _env_file=None,
        ),
        provider=_FakePortfolioProvider(),
    )
    monkeypatch.setattr(
        "app.api.v1.portfolio.build_service_portfolio_summary",
        lambda *, market, settings: provider_response,
    )

    response = build_portfolio_summary_response(
        MarketCode.US,
        Settings(
            DATA_PROVIDER="real",
            ENABLE_PORTFOLIO_DATABASE_READS=True,
            _env_file=None,
        ),
    )

    assert response.data_mode == PortfolioDataMode.PAPER
    assert response.positions[0].last_price == 200.0
    assert any("Provider 行情" in item for item in response.risk.risk_flags)


def test_portfolio_summary_appends_fallback_risk_flag_when_database_read_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)

    def raise_database_read_error(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("app.api.v1.portfolio.get_latest_portfolio_snapshot", raise_database_read_error)

    response = build_portfolio_summary_response(
        MarketCode.US,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_PORTFOLIO_DATABASE_READS=True,
            _env_file=None,
        ),
    )

    assert response.account.account_id == "paper-us-001"
    assert response.data_mode == "mock"
    assert any("数据库组合快照读取失败" in item for item in response.risk.risk_flags)
    assert any("RuntimeError" in item for item in response.risk.risk_flags)


def test_portfolio_summary_rejects_unknown_market() -> None:
    # 未支持市场必须返回参数校验错误，不能套用默认市场组合。
    response = client.get("/api/v1/portfolio/summary", params={"market": "EU"})

    assert response.status_code == 422


def test_create_paper_order_returns_mock_receipt() -> None:
    # POST 模拟订单当前只返回 Mock 回执，不提交真实券商订单。
    request = PaperOrderRequest(
        account_id="paper-us-001",
        market="US",
        symbol=" nvda ",
        side=PaperOrderSide.BUY,
        quantity=10,
        limit_price=180.5,
    )

    response = client.post("/api/v1/paper/orders", json=request.model_dump(mode="json"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["order_id"] == "paper-us-paper-us-001-nvda-submitted"
    assert payload["account_id"] == "paper-us-001"
    assert payload["market"] == "US"
    assert payload["symbol"] == "NVDA"
    assert payload["status"] == "submitted"
    assert payload["currency"] == "USD"
    assert payload["risk_checked"] is True


def test_create_paper_order_can_write_database(monkeypatch: pytest.MonkeyPatch) -> None:
    # 开启数据库写入后，模拟订单回执会追加到本地订单表，但仍不触发真实券商订单。
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    seed_development_data(engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)
    request = PaperOrderRequest(
        account_id="paper-us-001",
        market="US",
        symbol="NVDA",
        side=PaperOrderSide.BUY,
        quantity=10,
        limit_price=180.5,
    )

    receipt = build_paper_order_response(
        request,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_PORTFOLIO_DATABASE_WRITES=True,
            _env_file=None,
        ),
    )
    session_factory = get_session_factory(database_url)

    with session_factory() as session:
        repository = PortfolioRepository(session)
        orders = repository.list_orders("paper-us-001")
        saved_order = next(order for order in orders if order.order_id == receipt.order_id)

    assert receipt.status == PaperOrderStatus.FILLED
    assert saved_order.status == "filled"
    assert saved_order.source == "paper_order"
    assert saved_order.risk_decision == receipt.risk_decision.value
    assert saved_order.risk_reason_codes == receipt.risk_reason_codes

    summary = build_portfolio_summary_response(
        MarketCode.US,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_PORTFOLIO_DATABASE_READS=True,
            _env_file=None,
        ),
    )
    saved_order_response = next(order for order in summary.orders if order.order_id == receipt.order_id)
    assert saved_order_response.source == "paper_order"
    assert saved_order_response.status == PaperOrderStatus.FILLED
    assert summary.account.cash < 18_420


def test_create_paper_order_marks_fallback_when_database_write_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_database_write_error(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    seed_development_data(engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)
    monkeypatch.setattr("app.api.v1.portfolio.save_paper_order_receipt", raise_database_write_error)
    request = PaperOrderRequest(
        account_id="paper-us-001",
        market="US",
        symbol="NVDA",
        side=PaperOrderSide.BUY,
        quantity=10,
        limit_price=180.5,
    )

    receipt = build_paper_order_response(
        request,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_PORTFOLIO_DATABASE_WRITES=True,
            _env_file=None,
        ),
    )

    assert receipt.order_id == "paper-us-paper-us-001-nvda-submitted"
    assert receipt.data_status == "unavailable"
    assert receipt.fallback_active is True
    assert receipt.storage_source == "mock_fallback"
    assert "RuntimeError" in receipt.fallback_reason
    assert "未持久化 Mock 模拟订单" in receipt.fallback_reason


def test_create_paper_order_marks_fallback_when_account_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    seed_development_data(engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)
    request = PaperOrderRequest(
        account_id="missing-paper-account",
        market="US",
        symbol="NVDA",
        side=PaperOrderSide.BUY,
        quantity=10,
        limit_price=180.5,
    )

    receipt = build_paper_order_response(
        request,
        Settings(
            DATABASE_URL=database_url,
            ENABLE_PORTFOLIO_DATABASE_WRITES=True,
            _env_file=None,
        ),
    )

    assert receipt.fallback_active is True
    assert receipt.storage_source == "mock_fallback"
    assert "模拟账户不存在" in receipt.fallback_reason


def test_create_paper_order_rejects_live_trading_flag() -> None:
    # HTTP 层应复用 schema 校验，拒绝真实交易意图。
    request = {
        "account_id": "paper-us-001",
        "market": "US",
        "symbol": "NVDA",
        "side": "buy",
        "quantity": 10,
        "paper_trading": False,
    }

    response = client.post("/api/v1/paper/orders", json=request)

    assert response.status_code == 422


def test_paper_order_request_normalizes_symbol() -> None:
    # 模拟订单进入风控前先规范化证券代码，但仍然必须显式携带 market。
    request = PaperOrderRequest(
        account_id="paper-us-001",
        market="US",
        symbol=" nvda ",
        side=PaperOrderSide.BUY,
        quantity=10,
        limit_price=180.5,
    )

    assert request.symbol == "NVDA"
    assert request.paper_trading is True


def test_paper_order_request_rejects_live_trading_flag() -> None:
    # V1 禁止真实交易意图进入模拟订单接口。
    with pytest.raises(ValidationError, match="paper_trading must be true"):
        PaperOrderRequest(
            account_id="paper-us-001",
            market="US",
            symbol="NVDA",
            side=PaperOrderSide.BUY,
            quantity=10,
            paper_trading=False,
        )


def test_paper_order_create_response_keeps_risk_boundary() -> None:
    # 创建回执必须显式标记风控检查状态，后续接 Risk Engine 时保持合同稳定。
    response = PaperOrderCreateResponse(
        order_id="paper-us-order-001",
        account_id="paper-us-001",
        market="US",
        symbol="NVDA",
        side=PaperOrderSide.BUY,
        quantity=10,
        limit_price=180.5,
        status=PaperOrderStatus.SUBMITTED,
        submitted_at="2026-09-07T00:00:00Z",
        currency="USD",
        risk_checked=True,
        risk_decision=PaperOrderRiskDecision.APPROVED,
    )

    assert response.status == PaperOrderStatus.SUBMITTED
    assert response.risk_checked is True
    assert response.risk_decision == PaperOrderRiskDecision.APPROVED


def test_create_mock_paper_order_returns_submitted_receipt() -> None:
    # Mock service 先经过 Risk service，再返回模拟订单接收回执。
    request = PaperOrderRequest(
        account_id="paper-us-001",
        market="US",
        symbol=" nvda ",
        side=PaperOrderSide.BUY,
        quantity=10,
        limit_price=180.5,
    )

    response = create_mock_paper_order(request)

    assert response.order_id == "paper-us-paper-us-001-nvda-submitted"
    assert response.account_id == request.account_id
    assert response.market == request.market
    assert response.symbol == "NVDA"
    assert response.status == PaperOrderStatus.SUBMITTED
    assert response.currency == "USD"
    assert response.risk_checked is True
    assert response.risk_decision == PaperOrderRiskDecision.WARNING
    assert "position_weight_exceeded" in response.risk_reason_codes
    assert response.risk_reasons


def test_create_mock_paper_order_rejects_order_when_risk_check_fails() -> None:
    # 现金不足的大额买入应被 Risk service 标记为 rejected，但仍不连接真实券商。
    request = PaperOrderRequest(
        account_id="paper-us-001",
        market="US",
        symbol="NVDA",
        side=PaperOrderSide.BUY,
        quantity=10_000,
        limit_price=180.5,
    )

    response = create_mock_paper_order(request)

    assert response.status == PaperOrderStatus.REJECTED
    assert response.risk_checked is True
    assert response.risk_decision == PaperOrderRiskDecision.REJECTED
    assert "insufficient_cash" in response.risk_reason_codes
    assert response.risk_reasons

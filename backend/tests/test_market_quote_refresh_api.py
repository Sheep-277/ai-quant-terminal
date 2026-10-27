from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1 import market as route
from app.core.config import Settings
from app.core.exceptions import ProviderResponseError
from app.db.repositories.latest_quote_repository import LatestQuoteRepository
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.latest_quote import LatestQuote
from app.models.stock import Stock
from app.providers.base import MarketDataProvider
from app.schemas.market import MarketQuoteRefreshRequest, MarketQuoteRefreshResponse


class RefreshAPI:
    """直接验证路由函数与真实事务；HTTP 注册与输入约束由 OpenAPI 验证。"""

    def __init__(self, factory: sessionmaker[Session], provider: Mock) -> None:
        self.factory = factory
        self.provider = provider
        self.settings = Settings(ENABLE_MARKET_DATABASE_WRITES=True, _env_file=None)

    def refresh(self, body: object) -> MarketQuoteRefreshResponse:
        return route.refresh_market_quote_snapshot(MarketQuoteRefreshRequest.model_validate(body), self.settings)


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Iterator[RefreshAPI]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Stock.__table__, LatestQuote.__table__])
    factory = create_session_factory(engine)
    with factory.begin() as session:
        session.add_all([
            Stock(market="CN", symbol="600519.SH", name="贵州茅台", exchange="SSE", currency="CNY", timezone="Asia/Shanghai"),
            Stock(market="US", symbol="NVDA", name="NVIDIA", exchange="NASDAQ", currency="USD", timezone="America/New_York"),
        ])

    def database_session(_settings: Settings) -> Iterator[Session]:
        with factory() as session:
            yield session

    provider = Mock(spec=MarketDataProvider)
    provider.get_provider_status.return_value = {
        "provider_name": "YahooFinance", "mode": "real", "ready": True, "data_status": "delayed",
        "fallback_active": False, "fallback_reason": None, "active_source": "yahoo_finance",
    }
    provider.get_quote.side_effect = lambda *_args: {
        "price": 100.0, "change": 1.0, "change_percent": 0.01, "volume": 1000,
        "turnover": 100000.0, "data_status": "delayed", "timestamp": datetime(2026, 10, 26, 7, tzinfo=timezone.utc),
    }
    monkeypatch.setattr(route, "get_db_session", database_session)
    monkeypatch.setattr(route, "get_market_data_provider", lambda _settings: provider)
    yield RefreshAPI(factory, provider)
    engine.dispose()


def test_default_post_previews_without_writing(api: RefreshAPI) -> None:
    response = api.refresh({"market": "CN"})
    assert response.model_dump(mode="json") == {"market": "CN", "dry_run": True, "items": [
        {"symbol": "600519.SH", "status": "would_update", "reason": None},
    ]}
    with api.factory() as session:
        assert session.scalar(select(func.count()).select_from(LatestQuote)) == 0
    assert api.provider.get_quote.call_args.args[0].value == "CN"


def test_explicit_apply_commits_only_requested_market(api: RefreshAPI) -> None:
    response = api.refresh({"market": "CN", "dry_run": False})
    assert response.items[0].status == "updated"
    with api.factory() as session:
        quote = LatestQuoteRepository(session).get_by_market_symbol("CN", "600519.SH")
        assert quote is not None and quote.source == "yahoo_finance"
        assert quote.price == Decimal("100")
        assert quote.quote_timestamp == datetime(2026, 10, 26, 7)
        assert LatestQuoteRepository(session).list_by_market("US") == []


def test_disabled_write_gate_rejects_before_provider_or_database(api: RefreshAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    api.settings = Settings(ENABLE_MARKET_DATABASE_WRITES=False, _env_file=None)
    database = Mock(side_effect=AssertionError("database must not open"))
    monkeypatch.setattr(route, "get_db_session", database)
    with pytest.raises(HTTPException) as error:
        api.refresh({"market": "CN", "dry_run": False})
    assert error.value.status_code == 403
    assert error.value.detail["code"] == "market_database_writes_disabled"
    database.assert_not_called()
    api.provider.get_quote.assert_not_called()


def test_preview_is_allowed_with_write_gate_off(api: RefreshAPI) -> None:
    api.settings = Settings(ENABLE_MARKET_DATABASE_WRITES=False, _env_file=None)
    assert api.refresh({"market": "CN"}).dry_run is True


@pytest.mark.parametrize("body", [None, {}, {"market": "JP"}, {"market": "CN", "dry_run": "false"},
    {"market": "CN", "dry_run": 0}, {"market": "CN", "apply": True}])
def test_invalid_or_implicit_market_input_never_reads_quotes(api: RefreshAPI, body: object) -> None:
    with pytest.raises(ValidationError):
        api.refresh(body)
    api.provider.get_quote.assert_not_called()


def test_openapi_declares_post_body_and_response() -> None:
    app = FastAPI()
    app.include_router(route.router, prefix="/api/v1")
    schema = app.openapi()
    operations = schema["paths"]["/api/v1/market/quotes/refresh"]
    assert set(operations) == {"post"}
    assert operations["post"]["requestBody"]["required"] is True
    assert "200" in operations["post"]["responses"]
    request_schema = schema["components"]["schemas"]["MarketQuoteRefreshRequest"]
    assert request_schema["required"] == ["market"]
    assert request_schema["properties"]["dry_run"]["default"] is True
    assert request_schema["additionalProperties"] is False


def test_mock_provider_is_unavailable_without_synthetic_success(api: RefreshAPI) -> None:
    api.provider.get_provider_status.return_value.update(mode="mock", active_source="mock_provider")
    with pytest.raises(HTTPException) as error:
        api.refresh({"market": "CN", "dry_run": False})
    assert error.value.status_code == 503
    assert error.value.detail["code"] == "market_quote_provider_unavailable"
    api.provider.get_quote.assert_not_called()


def test_partial_read_failure_is_reported_and_successful_quotes_commit(api: RefreshAPI) -> None:
    with api.factory.begin() as session:
        session.add(Stock(market="CN", symbol="300750.SZ", name="宁德时代", exchange="SZSE", currency="CNY", timezone="Asia/Shanghai"))
    good = api.provider.get_quote(None, None)
    api.provider.get_quote.side_effect = [TimeoutError("private-secret"), good]
    response = api.refresh({"market": "CN", "dry_run": False})
    assert [item.status for item in response.items] == ["failed", "updated"]
    assert "private-secret" not in response.model_dump_json()
    with api.factory() as session:
        assert session.scalar(select(func.count()).select_from(LatestQuote)) == 1


def test_commit_failure_rolls_back_and_returns_sanitized_error(api: RefreshAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    def invalid_write(session: Session, *_args: object, **_kwargs: object) -> dict[str, object]:
        session.add(Stock(market="CN", symbol="private-secret", name=None, exchange="SSE", currency="CNY", timezone="Asia/Shanghai"))
        return {"market": "CN", "dry_run": False, "items": [{"symbol": "600519.SH", "status": "updated", "reason": None}]}

    monkeypatch.setattr(route, "refresh_market_quotes", invalid_write)
    with pytest.raises(HTTPException) as error:
        api.refresh({"market": "CN", "dry_run": False})
    assert error.value.status_code == 503
    assert error.value.detail["code"] == "market_quote_database_failed"
    assert "private-secret" not in str(error.value.detail)
    with api.factory() as session:
        assert session.scalar(select(func.count()).select_from(Stock)) == 2


def test_provider_preflight_error_is_sanitized(api: RefreshAPI) -> None:
    api.provider.get_provider_status.side_effect = ProviderResponseError("private-secret")
    with pytest.raises(HTTPException) as error:
        api.refresh({"market": "CN"})
    assert error.value.status_code == 502
    assert error.value.detail["code"] == "market_quote_provider_failed"
    assert "private-secret" not in str(error.value.detail)

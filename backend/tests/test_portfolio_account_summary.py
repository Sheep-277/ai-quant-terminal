import pytest
from fastapi import HTTPException

from app.api.v1.portfolio import build_portfolio_account_summary_response
from app.core.config import Settings
from app.db.seed import seed_development_data
from app.db.session import create_database_engine, get_engine, get_session_factory


def test_portfolio_account_summary_reads_database_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """账户级组合快照应按 account_id 精确读取 seed 写入的本地数据。"""

    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    seed_development_data(engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)

    response = build_portfolio_account_summary_response(
        "paper-us-001",
        Settings(
            DATABASE_URL=database_url,
            ENABLE_PORTFOLIO_DATABASE_READS=True,
            _env_file=None,
        ),
    )

    assert response.account.account_id == "paper-us-001"
    assert response.market.value == "US"
    assert response.positions
    assert response.orders


def test_portfolio_account_summary_returns_404_when_reads_disabled() -> None:
    """关闭数据库读取时，账户级接口不使用 Mock 顶替具体账户。"""

    with pytest.raises(HTTPException) as exc_info:
        build_portfolio_account_summary_response(
            "paper-us-001",
            Settings(
                ENABLE_PORTFOLIO_DATABASE_READS=False,
                _env_file=None,
            ),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "portfolio_database_reads_disabled"
    assert exc_info.value.detail["account_id"] == "paper-us-001"


def test_portfolio_account_summary_returns_404_for_missing_account(monkeypatch: pytest.MonkeyPatch) -> None:
    """数据库中不存在指定账户时，应返回结构化 404。"""

    database_url = "sqlite+pysqlite:///:memory:"
    engine = create_database_engine(database_url)
    seed_development_data(engine)
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    monkeypatch.setattr("app.db.session.get_engine", lambda _: engine)

    with pytest.raises(HTTPException) as exc_info:
        build_portfolio_account_summary_response(
            "paper-missing-001",
            Settings(
                DATABASE_URL=database_url,
                ENABLE_PORTFOLIO_DATABASE_READS=True,
                _env_file=None,
            ),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "portfolio_account_not_found"
    assert exc_info.value.detail["account_id"] == "paper-missing-001"

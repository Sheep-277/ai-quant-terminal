from types import SimpleNamespace
from unittest.mock import Mock
import json

import pytest
from sqlalchemy import func, select

from app.db import refresh_market_quotes as command
from app.db.session import Base, create_database_engine, create_session_factory
from app.models.latest_quote import LatestQuote
from app.models.stock import Stock


@pytest.fixture
def environment(monkeypatch: pytest.MonkeyPatch):
    """命令仅连接测试内存库，不读取实际配置或调用公开行情。"""
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Stock.__table__, LatestQuote.__table__])
    factory = create_session_factory(engine)
    settings = Mock(return_value=SimpleNamespace(database_url="test-db"))
    monkeypatch.setattr(command, "get_settings", settings)
    monkeypatch.setattr(command, "get_session_factory", lambda _url: factory)
    monkeypatch.setattr(command, "get_market_data_provider", lambda _settings: object())
    yield factory, settings
    engine.dispose()


@pytest.mark.parametrize("apply", [False, True])
def test_command_passes_explicit_market_and_write_intent(environment, monkeypatch, capsys, apply: bool) -> None:
    refresh = Mock(return_value={"market": "CN", "dry_run": not apply, "items": [
        {"symbol": "600519.SH", "status": "updated" if apply else "would_update", "reason": None},
    ]})
    monkeypatch.setattr(command, "refresh_market_quotes", refresh)
    assert command.main(["--market", "CN"] + (["--apply"] if apply else [])) == 0
    assert refresh.call_args.kwargs["dry_run"] is not apply
    assert refresh.call_args.args[1].value == "CN"
    assert json.loads(capsys.readouterr().out)["dry_run"] is not apply


@pytest.mark.parametrize("items", [[], [{"symbol": "NVDA", "status": "skipped", "reason": "older_than_saved_quote"}],
    [{"symbol": "NVDA", "status": "failed", "reason": "provider_read_failed"}]])
def test_empty_or_incomplete_report_has_distinct_exit_code(environment, monkeypatch, capsys, items) -> None:
    monkeypatch.setattr(command, "refresh_market_quotes", lambda *_args, **_kwargs: {"market": "US", "dry_run": True, "items": items})
    assert command.main(["--market", "US"]) == 3
    assert json.loads(capsys.readouterr().out)["items"] == items


def test_commit_failure_rolls_back_and_never_prints_success_or_secret(environment, monkeypatch, capsys) -> None:
    factory, _ = environment

    def bad_write(session, *_args, **_kwargs):
        # 第一条合法写入也必须随第二条约束失败一起回滚。
        for symbol, name in [("NVDA", "NVDA"), ("private-secret", None)]:
            session.add(Stock(market="US", symbol=symbol, name=name, exchange="NASDAQ", currency="USD", timezone="America/New_York"))
        return {"market": "US", "dry_run": False, "items": [{"symbol": "NVDA", "status": "updated", "reason": None}]}

    monkeypatch.setattr(command, "refresh_market_quotes", bad_write)
    assert command.main(["--market", "US", "--apply"]) == 1
    output = capsys.readouterr().out
    assert json.loads(output)["error_type"] == "IntegrityError"
    assert "private-secret" not in output and "updated" not in output
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Stock)) == 0


def test_argument_error_does_not_load_settings_or_connect(environment) -> None:
    _, settings = environment
    with pytest.raises(SystemExit) as error:
        command.main(["--market", "JP"])
    assert error.value.code == 2
    settings.assert_not_called()

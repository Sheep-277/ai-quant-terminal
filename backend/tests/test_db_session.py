from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import create_database_engine, create_session_factory, get_db_session


def test_settings_reads_database_url_from_environment(monkeypatch) -> None:
    # 数据库连接必须从环境变量进入配置层，避免在业务代码中硬编码数据库地址。
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite+pysqlite:///:memory:"


def test_create_session_factory_executes_simple_query() -> None:
    # 这里使用 SQLite 内存库验证 Session 行为，不要求本地已经启动 MySQL。
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        result = session.execute(text("select 1")).scalar_one()

    assert result == 1


def test_get_db_session_yields_sqlalchemy_session() -> None:
    settings = Settings(DATABASE_URL="sqlite+pysqlite:///:memory:", _env_file=None)

    session = next(get_db_session(settings))

    assert isinstance(session, Session)
    session.close()

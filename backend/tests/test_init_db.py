from app.db.init_db import init_database
from app.db.session import create_database_engine


def test_init_database_creates_current_orm_tables() -> None:
    # 使用 SQLite 内存库验证开发建表入口，不依赖本地 MySQL。
    engine = create_database_engine("sqlite+pysqlite:///:memory:")

    table_names = set(init_database(engine))

    assert table_names >= {
        "stocks",
        "latest_quotes",
        "market_bars",
        "provider_status_logs",
        "signals",
        "strategies",
        "agent_tasks",
        "research_evidence",
    }

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app import models  # noqa: F401
from app.db.session import Base, get_engine


def init_database(engine: Engine | None = None) -> list[str]:
    """创建当前已实现的 ORM 表，并返回数据库中可见的表名。"""

    resolved_engine = engine or get_engine()
    Base.metadata.create_all(bind=resolved_engine)
    return inspect(resolved_engine).get_table_names()


if __name__ == "__main__":
    created_tables = init_database()
    print("Created or verified tables:")
    for table_name in created_tables:
        print(f"- {table_name}")

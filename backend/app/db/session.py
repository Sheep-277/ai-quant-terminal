from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings, get_settings


class Base(DeclarativeBase):
    """所有 SQLAlchemy ORM 模型的共同基类。"""


def create_database_engine(database_url: str) -> Engine:
    """根据数据库连接字符串创建 SQLAlchemy Engine。"""

    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        # SQLite 测试库需要关闭同线程限制，方便 FastAPI 测试客户端复用连接。
        connect_args["check_same_thread"] = False

    return create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)


@lru_cache
def get_engine(database_url: str | None = None) -> Engine:
    """懒加载数据库 Engine，避免应用启动时强制连接数据库。"""

    settings = get_settings()
    return create_database_engine(database_url or settings.database_url)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """基于 Engine 创建 Session 工厂。"""

    return sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


@lru_cache
def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    """获取可缓存的 Session 工厂，供 API 依赖或 Repository 使用。"""

    return create_session_factory(get_engine(database_url))


def get_db_session(settings: Settings | None = None) -> Generator[Session, None, None]:
    """FastAPI 依赖函数：为一次请求提供一个数据库 Session。"""

    database_url = settings.database_url if settings is not None else None
    session_factory = get_session_factory(database_url)
    with session_factory() as session:
        yield session

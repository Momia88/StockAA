"""
資料庫連線與 Session 管理
"""
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .base import Base

# 延遲 import 避免循環依賴
from .asset import Asset  # noqa: F401
from .transaction import Transaction  # noqa: F401
from .price_history import PriceHistory  # noqa: F401


def get_engine(db_path: str):
    """建立 SQLAlchemy Engine"""
    # 確保資料庫目錄存在
    db_file = Path(db_path.replace("sqlite:///", ""))
    db_file.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{db_file}",
        echo=False,
        connect_args={
            "check_same_thread": False,
            "timeout": 30,
        },
    )

    # 啟用 WAL 模式（提升 SQLite 並發性能）
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def create_all_tables(engine) -> None:
    """建立所有資料表（初次使用）"""
    Base.metadata.create_all(engine)


def get_session_factory(engine):
    """建立 Session 工廠"""
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_db_session(session_factory) -> Generator[Session, None, None]:
    """Context manager 風格的 Session，自動處理 commit/rollback"""
    session: Session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

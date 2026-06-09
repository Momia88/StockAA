"""
FastAPI 依賴注入：DB session、設定
"""
from typing import Generator
from sqlalchemy.orm import Session

from ..models.database import create_all_tables, get_db_session, get_engine, get_session_factory
from ..utils.config import get_settings

_settings = get_settings()
_engine = get_engine(_settings.db_path)
create_all_tables(_engine)
_session_factory = get_session_factory(_engine)


def get_session() -> Generator[Session, None, None]:
    with get_db_session(_session_factory) as session:
        yield session


def get_sf():
    return _session_factory

"""
SQLAlchemy Base 與共用欄位 Mixin
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """回傳帶時區的 UTC 當前時間"""
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    """產生新 UUID 字串"""
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """SQLAlchemy 宣告式 Base"""
    pass


class TimestampMixin:
    """共用時間戳記欄位"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

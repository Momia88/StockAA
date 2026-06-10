"""
負債與設定資料存取層
"""
from typing import Optional

from sqlalchemy.orm import Session

from ..models.liability import Liability, Setting


class LiabilityRepository:
    """負債 CRUD"""

    def __init__(self, session: Session):
        self.session = session

    def get_all(self) -> list[Liability]:
        return (
            self.session.query(Liability)
            .order_by(Liability.lender, Liability.name)
            .all()
        )

    def get_by_id(self, liability_id: str) -> Optional[Liability]:
        return self.session.query(Liability).filter(Liability.id == liability_id).first()

    def create(self, **kwargs) -> Liability:
        obj = Liability(**kwargs)
        self.session.add(obj)
        self.session.flush()
        return obj

    def update(self, liability_id: str, **kwargs) -> Optional[Liability]:
        obj = self.get_by_id(liability_id)
        if obj is None:
            return None
        for k, v in kwargs.items():
            setattr(obj, k, v)
        self.session.flush()
        return obj

    def delete(self, liability_id: str) -> bool:
        obj = self.get_by_id(liability_id)
        if obj is None:
            return False
        self.session.delete(obj)
        return True


class SettingRepository:
    """通用 key-value 設定"""

    def __init__(self, session: Session):
        self.session = session

    def get(self, key: str, default: str = "") -> str:
        row = self.session.query(Setting).filter(Setting.key == key).first()
        return row.value if row else default

    def get_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.get(key, str(default)))
        except (ValueError, TypeError):
            return default

    def set(self, key: str, value: str) -> None:
        row = self.session.query(Setting).filter(Setting.key == key).first()
        if row is None:
            self.session.add(Setting(key=key, value=value))
        else:
            row.value = value
        self.session.flush()

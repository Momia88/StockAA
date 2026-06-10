"""
負債（貸款／質借）模型 — 呈現槓桿、資產淨值與現金流
"""
from datetime import date
from enum import Enum

from sqlalchemy import Date, Enum as SAEnum, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid


class LiabilityType(str, Enum):
    """負債類型"""
    STOCK_PLEDGE = "STOCK_PLEDGE"   # 股票質借（以持股質押借款）
    CREDIT = "CREDIT"               # 信貸
    MARGIN = "MARGIN"               # 融資
    OTHER = "OTHER"                 # 其他

    @property
    def label(self) -> str:
        return {
            "STOCK_PLEDGE": "股票質借",
            "CREDIT": "信貸",
            "MARGIN": "融資",
            "OTHER": "其他",
        }[self.value]


class Liability(Base, TimestampMixin):
    """單筆負債（一筆貸款或一筆質借）"""
    __tablename__ = "liabilities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(
        String(80), nullable=False, comment="名稱／標的（如 679B(35)(竹)、信貸）"
    )
    lender: Mapped[str] = mapped_column(
        String(40), nullable=False, default="",
        comment="機構／帳戶（如 元大證金、永豐、信貸銀行）— 供報表彙總"
    )
    kind: Mapped[LiabilityType] = mapped_column(
        SAEnum(LiabilityType), nullable=False, default=LiabilityType.STOCK_PLEDGE,
        comment="負債類型"
    )
    balance: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="貸款餘額（TWD）"
    )
    annual_rate: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="年利率（如 0.0248 表示 2.48%）"
    )
    monthly_principal: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="每月應還本金（質借通常為 0）"
    )
    maturity_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="到期日（質借常見）"
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True, comment="備註")

    @property
    def monthly_interest(self) -> float:
        """每月利息 = 餘額 × 年利率 ÷ 12"""
        return self.balance * self.annual_rate / 12.0


class Setting(Base):
    """通用 key-value 設定（目前用於現金流預算：生活費、房租學費等）"""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(200), nullable=False, default="")

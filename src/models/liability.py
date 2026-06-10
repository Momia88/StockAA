"""
負債（貸款／質借）模型 — 呈現槓桿、資產淨值與現金流
"""
from datetime import date
from enum import Enum

from sqlalchemy import Date, Enum as SAEnum, Float, Integer, String, Text
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


class RepayMethod(str, Enum):
    """還款方式"""
    INTEREST_ONLY = "INTEREST_ONLY"   # 只繳息（餘額不變，到期或自行還本；質借常見）
    AMORTIZED = "AMORTIZED"           # 本息平均攤還（月繳固定，本金/利息逐月變動；信貸常見）

    @property
    def label(self) -> str:
        return {
            "INTEREST_ONLY": "只繳息",
            "AMORTIZED": "本息平均攤還",
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
    annual_rate: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="年利率（如 0.0248 表示 2.48%）"
    )

    # ── 只繳息（INTEREST_ONLY）使用 ──
    balance: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="貸款餘額（只繳息用）"
    )
    monthly_principal: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="每月固定還本（只繳息通常為 0）"
    )

    # ── 本息平均攤還（AMORTIZED）使用 ──
    repay_method: Mapped[RepayMethod] = mapped_column(
        SAEnum(RepayMethod), nullable=False, default=RepayMethod.INTEREST_ONLY,
        comment="還款方式"
    )
    original_principal: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="原始貸款本金（攤還用）"
    )
    total_periods: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="總期數（月，攤還用）"
    )
    start_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="起貸日（攤還用，依此自動推算已繳期數）"
    )

    maturity_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="到期日（質借常見）"
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True, comment="備註")

    # ─────────────────────────────────────────────
    # 攤還計算（本息平均攤還）
    # ─────────────────────────────────────────────
    @property
    def periods_elapsed(self) -> int:
        """自起貸日至今已繳期數（夾在 0..總期數）"""
        if not self.start_date or self.total_periods <= 0:
            return 0
        today = date.today()
        months = (today.year - self.start_date.year) * 12 + (today.month - self.start_date.month)
        return max(0, min(months, self.total_periods))

    def _amortization(self) -> tuple[float, float, float, float]:
        """回傳 (當前餘額, 本月利息, 本月還本, 月繳金額)"""
        p = self.original_principal
        n = self.total_periods
        i = self.annual_rate / 12.0
        k = self.periods_elapsed
        if p <= 0 or n <= 0:
            return 0.0, 0.0, 0.0, 0.0

        if i == 0:
            payment = p / n
            bal = max(p - payment * k, 0.0)
        else:
            payment = p * i / (1 - (1 + i) ** (-n))
            bal = p * (1 + i) ** k - payment * ((1 + i) ** k - 1) / i
            bal = max(bal, 0.0)

        if k >= n or bal <= 0:
            return 0.0, 0.0, 0.0, payment

        interest = bal * i
        principal = payment - interest
        return bal, interest, principal, payment

    @property
    def is_amortized(self) -> bool:
        return self.repay_method == RepayMethod.AMORTIZED

    @property
    def current_balance(self) -> float:
        """當前貸款餘額（攤還型依條件推算，只繳息型為固定餘額）"""
        if self.is_amortized:
            return self._amortization()[0]
        return self.balance

    @property
    def monthly_interest(self) -> float:
        """本月利息"""
        if self.is_amortized:
            return self._amortization()[1]
        return self.balance * self.annual_rate / 12.0

    @property
    def monthly_principal_due(self) -> float:
        """本月應還本金"""
        if self.is_amortized:
            return self._amortization()[2]
        return self.monthly_principal

    @property
    def monthly_payment(self) -> float:
        """本月月繳（本金 + 利息）"""
        return self.monthly_interest + self.monthly_principal_due


class Setting(Base):
    """通用 key-value 設定（目前用於現金流預算：生活費、房租學費等）"""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(200), nullable=False, default="")

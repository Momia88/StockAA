"""
Asset 持倉模型 — 代表目前持有的股票/ETF 快照
每個 ticker 對應一筆 Asset 記錄
"""
from datetime import date
from typing import TYPE_CHECKING, List

from sqlalchemy import Date, Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, new_uuid
from .enums import AssetType, Exchange

if TYPE_CHECKING:
    from .transaction import Transaction


class Asset(Base, TimestampMixin):
    """持倉快照表（依 ticker 唯一）"""
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_uuid
    )
    ticker: Mapped[str] = mapped_column(
        String(10), nullable=False, unique=True, index=True,
        comment="股票代碼（如 2330, 0050, 00679B）"
    )
    name: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="股票名稱（如 台積電, 元大台灣50）"
    )
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType), nullable=False,
        comment="資產類型：STOCK/STOCK_ETF/BOND_ETF"
    )
    exchange: Mapped[Exchange] = mapped_column(
        Enum(Exchange), nullable=False,
        comment="交易所：TWSE（上市）/ TPEx（上櫃）"
    )
    # --- 持倉數量與成本 ---
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="持有股數"
    )
    avg_cost: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="平均持有成本（含手續費，元/股）"
    )
    total_invested: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="總投入金額（TWD，含所有手續費）"
    )
    realized_pnl: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="累計已實現損益（TWD）"
    )
    total_dividend: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="累計現金股利收入（TWD）"
    )
    # --- 日期 ---
    first_buy_date: Mapped[date | None] = mapped_column(
        Date, nullable=True,
        comment="首次買入日期"
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="備註"
    )

    # --- 關聯 ---
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction",
        back_populates="asset",
        order_by="Transaction.trade_date",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Asset {self.ticker} {self.name} "
            f"qty={self.quantity} avg_cost={self.avg_cost:.2f}>"
        )

    @property
    def market_value(self) -> float:
        """市值（需搭配最新股價計算，預設 0）"""
        return 0.0  # 由 service 層注入現價計算

    @property
    def cost_basis(self) -> float:
        """成本總額 = 平均成本 × 持有股數"""
        return self.avg_cost * self.quantity

    @property
    def is_active(self) -> bool:
        """是否仍持有（股數 > 0）"""
        return self.quantity > 0

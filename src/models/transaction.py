"""
Transaction 交易記錄模型 — 完整的交易歷史
"""
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, new_uuid
from .enums import TxAction

if TYPE_CHECKING:
    from .asset import Asset


class Transaction(Base, TimestampMixin):
    """交易記錄表（不可修改，只能新增/刪除）"""
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_uuid
    )
    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    ticker: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True,
        comment="股票代碼（冗餘欄位，方便查詢）"
    )
    action: Mapped[TxAction] = mapped_column(
        Enum(TxAction), nullable=False,
        comment="交易類型：BUY/SELL/DIVIDEND/STOCK_DIVIDEND/SPLIT"
    )
    # --- 價格與數量 ---
    price: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="交易單價（TWD，元/股）。DIVIDEND 時為每股股利"
    )
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="交易股數。SPLIT 時為調整後總股數差異"
    )
    # --- 費用 ---
    fee: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="手續費（TWD）"
    )
    tax: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="證券交易稅（TWD，賣出才收）"
    )
    net_amount: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="淨交易金額（正=支出，負=收入）"
    )
    # --- 損益快照（賣出時記錄）---
    realized_pnl: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="本筆交易已實現損益（賣出時計算）"
    )
    avg_cost_at_tx: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="本筆交易時的平均持有成本（快照）"
    )
    # --- 日期 ---
    trade_date: Mapped[date] = mapped_column(
        Date, nullable=False, index=True,
        comment="交易日（成交日）"
    )
    settlement_date: Mapped[date | None] = mapped_column(
        Date, nullable=True,
        comment="交割日（T+2，選填）"
    )
    note: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="備註（券商、帳號、備忘）"
    )

    # --- 關聯 ---
    asset: Mapped["Asset"] = relationship(
        "Asset", back_populates="transactions"
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction {self.action.value} {self.ticker} "
            f"qty={self.quantity} price={self.price:.2f} "
            f"date={self.trade_date}>"
        )

"""
PriceHistory 歷史價格快取模型
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class PriceHistory(Base):
    """股票歷史價格快取（避免重複打 API）"""
    __tablename__ = "price_history"
    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_price_ticker_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True,
        comment="股票代碼"
    )
    date: Mapped[date] = mapped_column(
        Date, nullable=False, index=True,
        comment="交易日期"
    )
    open: Mapped[float | None] = mapped_column(Float, nullable=True, comment="開盤價")
    high: Mapped[float | None] = mapped_column(Float, nullable=True, comment="最高價")
    low: Mapped[float | None] = mapped_column(Float, nullable=True, comment="最低價")
    close: Mapped[float] = mapped_column(Float, nullable=False, comment="收盤價")
    volume: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="成交量（股）")
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="TWSE",
        comment="數據來源：TWSE / TPEx"
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow,
        comment="資料抓取時間（UTC）"
    )

    def __repr__(self) -> str:
        return f"<PriceHistory {self.ticker} {self.date} close={self.close}>"

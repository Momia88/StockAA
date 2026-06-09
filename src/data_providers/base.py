"""
資料提供者抽象基類與共用資料結構
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class PriceData:
    """統一的股價資料結構"""
    ticker: str
    name: str
    close: float
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    volume: Optional[int]
    trade_date: date
    source: str
    is_cached: bool = False
    fetched_at: datetime = None

    def __post_init__(self):
        if self.fetched_at is None:
            from datetime import timezone
            self.fetched_at = datetime.now(timezone.utc)


@dataclass
class StockInfo:
    """股票基本資料"""
    ticker: str
    name: str
    exchange: str   # "TWSE" or "TPEx"
    sector: Optional[str] = None


class AbstractPriceProvider(ABC):
    """股價數據提供者抽象基類"""

    @abstractmethod
    def get_current_price(self, ticker: str) -> Optional[PriceData]:
        """
        取得指定股票的最新收盤價

        Args:
            ticker: 股票代碼（如 "2330", "0050"）

        Returns:
            PriceData 或 None（找不到時）
        """
        ...

    @abstractmethod
    def get_all_prices(self) -> dict[str, PriceData]:
        """
        取得所有股票的最新價格（批次查詢，效率更高）

        Returns:
            {ticker: PriceData} 字典
        """
        ...

    @abstractmethod
    def supports(self, ticker: str) -> bool:
        """判斷此 provider 是否支援該股票代碼"""
        ...

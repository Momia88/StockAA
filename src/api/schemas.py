"""
API 回應資料結構（Pydantic schemas）
"""
from datetime import date
from typing import Optional
from pydantic import BaseModel


class AssetOut(BaseModel):
    ticker: str
    name: str
    asset_type: str
    exchange: str
    quantity: int
    avg_cost: float
    cost_basis: float
    current_price: Optional[float]
    market_value: Optional[float]
    unrealized_pnl: Optional[float]
    unrealized_pnl_pct: Optional[float]
    realized_pnl: float
    total_dividend: float
    total_return: Optional[float]
    is_price_stale: bool


class PortfolioSummaryOut(BaseModel):
    assets: list[AssetOut]
    total_cost_basis: float
    total_market_value: Optional[float]
    total_unrealized_pnl: Optional[float]
    total_realized_pnl: float
    total_dividend: float
    total_return_pct: Optional[float]
    active_count: int


class TransactionOut(BaseModel):
    id: str
    ticker: str
    action: str
    price: float
    quantity: int
    fee: float
    tax: float
    net_amount: float
    realized_pnl: float
    avg_cost_at_tx: float
    trade_date: date
    note: Optional[str]


class BuyRequest(BaseModel):
    ticker: str
    name: str
    asset_type: str = "STOCK"
    exchange: str = "TWSE"
    price: float
    quantity: int
    trade_date: date
    discount: Optional[float] = None
    note: Optional[str] = None


class SellRequest(BaseModel):
    ticker: str
    price: float
    quantity: int
    trade_date: date
    discount: Optional[float] = None
    note: Optional[str] = None


class DividendRequest(BaseModel):
    ticker: str
    dividend_per_share: float
    quantity: Optional[int] = None
    trade_date: date
    note: Optional[str] = None


class StockDividendRequest(BaseModel):
    ticker: str
    bonus_shares: int
    trade_date: date
    note: Optional[str] = None


class SplitRequest(BaseModel):
    ticker: str
    split_ratio: float
    trade_date: date
    note: Optional[str] = None


class PriceOut(BaseModel):
    ticker: str
    name: str
    close: float
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    volume: Optional[int]
    trade_date: date
    source: str


class MessageOut(BaseModel):
    message: str

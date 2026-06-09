"""
列舉型別定義 — 資產類型與交易動作
"""
from enum import Enum


class AssetType(str, Enum):
    """資產類型"""
    STOCK = "STOCK"           # 個股（如 2330 台積電）
    STOCK_ETF = "STOCK_ETF"   # 股票型 ETF（如 0050 元大台灣50）
    BOND_ETF = "BOND_ETF"     # 債券型 ETF（如 00679B 元大美債20年）

    @property
    def label(self) -> str:
        labels = {
            "STOCK": "個股",
            "STOCK_ETF": "股票ETF",
            "BOND_ETF": "債券ETF",
        }
        return labels[self.value]


class Exchange(str, Enum):
    """交易所"""
    TWSE = "TWSE"   # 台灣證券交易所（上市）
    TPEx = "TPEx"   # 財團法人中華民國證券櫃檯買賣中心（上櫃）

    @property
    def label(self) -> str:
        labels = {
            "TWSE": "上市",
            "TPEx": "上櫃",
        }
        return labels[self.value]


class TxAction(str, Enum):
    """交易動作"""
    BUY = "BUY"                         # 買入
    SELL = "SELL"                       # 賣出
    DIVIDEND = "DIVIDEND"               # 現金股利（股息）
    STOCK_DIVIDEND = "STOCK_DIVIDEND"   # 股票股利
    SPLIT = "SPLIT"                     # 股票分割（正值）或合併（負值）

    @property
    def label(self) -> str:
        labels = {
            "BUY": "買入",
            "SELL": "賣出",
            "DIVIDEND": "現金股利",
            "STOCK_DIVIDEND": "股票股利",
            "SPLIT": "股票分割/合併",
        }
        return labels[self.value]

    @property
    def is_cash_flow(self) -> bool:
        """是否產生現金流"""
        return self in (TxAction.BUY, TxAction.SELL, TxAction.DIVIDEND)

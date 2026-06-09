"""
自訂例外類型
"""


class StockAAError(Exception):
    """基礎例外（所有自訂例外的父類）"""
    pass


class TickerNotFoundError(StockAAError):
    """找不到股票代碼"""
    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"找不到股票代碼：{ticker}")


class InsufficientHoldingsError(StockAAError):
    """賣出股數超過持有股數"""
    def __init__(self, ticker: str, available: int, requested: int):
        self.ticker = ticker
        self.available = available
        self.requested = requested
        super().__init__(
            f"{ticker} 持有股數不足：持有 {available} 股，嘗試賣出 {requested} 股"
        )


class AssetAlreadyExistsError(StockAAError):
    """資產已存在（重複新增）"""
    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"資產已存在：{ticker}，請直接新增交易記錄")


class AssetNotFoundError(StockAAError):
    """持倉中找不到指定資產"""
    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"持倉中找不到 {ticker}，請先新增買入交易")


class PriceFetchError(StockAAError):
    """股價抓取失敗"""
    def __init__(self, ticker: str, reason: str = ""):
        self.ticker = ticker
        super().__init__(f"無法取得 {ticker} 的股價：{reason}")


class InvalidTransactionError(StockAAError):
    """無效的交易記錄"""
    pass


class DatabaseError(StockAAError):
    """資料庫操作錯誤"""
    pass

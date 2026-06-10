"""
股價數據提供者管理器 — 自動路由到正確的 Provider，並整合 SQLite 快取
"""
from datetime import date
from typing import Optional

from ..utils.logger import logger
from ..utils.exceptions import PriceFetchError
from .base import PriceData
from .twse_provider import TWSEProvider
from .tpex_provider import TPExProvider


class PriceManager:
    """
    管理多個 Provider，依照 exchange 路由到正確的 API。
    若提供 session_factory，則將抓取結果持久化到 SQLite，
    並在當日快取存在時直接讀取，避免重複呼叫 API。
    """

    def __init__(self, timeout: int = 15, session_factory=None):
        self.twse = TWSEProvider(timeout=timeout)
        self.tpex = TPExProvider(timeout=timeout)
        self._session_factory = session_factory

    def get_price(self, ticker: str, exchange: Optional[str] = None) -> PriceData:
        """
        取得單一股票的最新股價

        Args:
            ticker: 股票代碼
            exchange: 交易所（"TWSE"/"TPEx"，省略則自動偵測）

        Returns:
            PriceData

        Raises:
            PriceFetchError: 無法取得股價
        """
        # 先查 SQLite 快取（當日）
        if self._session_factory:
            cached = self._get_from_cache(ticker, date.today())
            if cached:
                logger.debug(f"[PriceManager] {ticker} 使用 SQLite 快取")
                return cached

        # 指定交易所時直接查詢
        if exchange == "TWSE":
            result = self.twse.get_current_price(ticker)
        elif exchange == "TPEx":
            result = self.tpex.get_current_price(ticker)
        else:
            result = self.twse.get_current_price(ticker)
            if result is None:
                logger.debug(f"[PriceManager] {ticker} 不在 TWSE，嘗試 TPEx")
                result = self.tpex.get_current_price(ticker)

        if result is None:
            raise PriceFetchError(ticker, "TWSE 與 TPEx 均找不到此股票代碼")

        if self._session_factory:
            self._persist_to_cache([result])

        return result

    def get_prices_batch(
        self,
        tickers: list[str],
        cache_only: bool = False,
        force_refresh: bool = False,
    ) -> dict[str, Optional[PriceData]]:
        """
        批次取得多支股票的最新股價。
        若提供 session_factory，優先從 SQLite 快取讀取，
        若快取不足（如首次執行當日），才抓取完整市場行情並持久化。

        Args:
            cache_only: 只讀 SQLite 快取、絕不打網路（未快取者回 None）。
                        供前端「先秒開頁面」使用。
            force_refresh: 略過快取一律重新抓取（供「更新行情」用）。

        Returns:
            {ticker: PriceData or None}
        """
        today = date.today()
        result: dict[str, Optional[PriceData]] = {}

        # 嘗試從 SQLite 快取取得（force_refresh 時跳過）
        if self._session_factory and not force_refresh:
            cached_all = self._get_all_from_cache(today)
            for ticker in tickers:
                if ticker in cached_all:
                    result[ticker] = cached_all[ticker]

            missing = [t for t in tickers if t not in result]
            if not missing:
                logger.debug(f"[PriceManager] 全部 {len(tickers)} 支股票使用 SQLite 快取")
                return result
        else:
            missing = list(tickers)

        # 只讀快取模式：未快取者直接回 None，不打網路
        if cache_only:
            for ticker in missing:
                result[ticker] = None
            return result

        # 仍有未快取的股票，呼叫 API 取得完整市場行情
        logger.info(f"[PriceManager] 從 API 取得 {len(missing)} 支股票行情")
        twse_prices = self.twse.get_all_prices()
        tpex_prices = self.tpex.get_all_prices()

        new_prices: list[PriceData] = []
        for ticker in missing:
            price = twse_prices.get(ticker) or tpex_prices.get(ticker)
            if price is None:
                logger.warning(f"[PriceManager] 找不到 {ticker} 的行情")
            else:
                new_prices.append(price)
            result[ticker] = price

        # 持久化新取得的行情
        if self._session_factory and new_prices:
            self._persist_to_cache(new_prices)

        return result

    # ─────────────────────────────────────────
    # 私有：SQLite 快取讀寫
    # ─────────────────────────────────────────

    def _get_from_cache(self, ticker: str, trade_date: date) -> Optional[PriceData]:
        from ..repositories.price_history_repo import PriceHistoryRepository
        from ..models.database import get_db_session
        try:
            with get_db_session(self._session_factory) as session:
                repo = PriceHistoryRepository(session)
                row = repo.get_by_date(ticker, trade_date)
                if row is None:
                    return None
                return PriceData(
                    ticker=row.ticker,
                    name="",
                    close=row.close,
                    open=row.open,
                    high=row.high,
                    low=row.low,
                    volume=row.volume,
                    trade_date=row.date,
                    source=row.source,
                    is_cached=True,
                    fetched_at=row.fetched_at,
                )
        except Exception as e:
            logger.warning(f"[PriceManager] 讀取快取失敗：{e}")
            return None

    def _get_all_from_cache(self, trade_date: date) -> dict[str, PriceData]:
        from ..repositories.price_history_repo import PriceHistoryRepository
        from ..models.database import get_db_session
        try:
            with get_db_session(self._session_factory) as session:
                repo = PriceHistoryRepository(session)
                return repo.get_all_by_date(trade_date)
        except Exception as e:
            logger.warning(f"[PriceManager] 讀取快取失敗：{e}")
            return {}

    def _persist_to_cache(self, prices: list[PriceData]) -> None:
        from ..repositories.price_history_repo import PriceHistoryRepository
        from ..models.database import get_db_session
        try:
            with get_db_session(self._session_factory) as session:
                repo = PriceHistoryRepository(session)
                repo.upsert_batch(prices)
        except Exception as e:
            logger.warning(f"[PriceManager] 寫入快取失敗（不影響主流程）：{e}")

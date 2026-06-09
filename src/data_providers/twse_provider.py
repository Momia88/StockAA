"""
台灣證券交易所 (TWSE) Open API 資料提供者
API 文件: https://openapi.twse.com.tw/
"""
import time
from datetime import date, datetime, timezone
from typing import Optional

import requests

from ..utils.logger import logger
from .base import AbstractPriceProvider, PriceData

# TWSE Open API 端點
TWSE_ALL_STOCKS_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TWSE_STOCK_INFO_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"

# 請求 Header（避免被 403 封鎖）
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://www.twse.com.tw/",
}

MAX_RETRIES = 3
RETRY_DELAY = 2  # 秒


class TWSEProvider(AbstractPriceProvider):
    """
    台灣證券交易所上市股票與 ETF 資料提供者
    使用 TWSE Open API 取得當日全市場收盤行情
    """

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self._cache: dict[str, PriceData] = {}  # 記憶體內快取（當次執行有效）
        self._cache_time: Optional[datetime] = None

    def supports(self, ticker: str) -> bool:
        """
        TWSE 支援純數字 4~6 碼的上市股票
        （實際由 get_all_prices 的返回值決定）
        """
        return ticker.isdigit() or (len(ticker) == 6 and ticker[:4].isdigit())

    def get_all_prices(self) -> dict[str, PriceData]:
        """
        取得 TWSE 所有上市股票當日行情（批次）
        快取在記憶體中，同一程式執行期間不重複打 API
        """
        # 記憶體快取仍有效
        if self._cache and self._cache_time:
            elapsed = (datetime.now(timezone.utc) - self._cache_time).seconds
            if elapsed < 300:
                logger.debug(f"[TWSE] 使用記憶體快取（{elapsed} 秒前更新）")
                return self._cache

        logger.info("[TWSE] 正在抓取全市場收盤行情...")
        raw_data = self._fetch_with_retry(TWSE_ALL_STOCKS_URL)
        if not raw_data:
            logger.warning("[TWSE] 無法取得行情，返回空字典")
            return {}

        today = date.today()
        prices: dict[str, PriceData] = {}

        for row in raw_data:
            try:
                ticker = row.get("Code", "").strip()
                name = row.get("Name", "").strip()
                close_str = row.get("ClosingPrice", "0").replace(",", "").strip()
                open_str = row.get("OpeningPrice", "0").replace(",", "").strip()
                high_str = row.get("HighestPrice", "0").replace(",", "").strip()
                low_str = row.get("LowestPrice", "0").replace(",", "").strip()
                vol_str = row.get("TradeVolume", "0").replace(",", "").strip()

                # 跳過停牌或無效價格（以 "--" 或空值表示）
                if not ticker or close_str in ("--", "", "0", "0.00"):
                    continue

                prices[ticker] = PriceData(
                    ticker=ticker,
                    name=name,
                    close=float(close_str),
                    open=float(open_str) if open_str not in ("--", "") else None,
                    high=float(high_str) if high_str not in ("--", "") else None,
                    low=float(low_str) if low_str not in ("--", "") else None,
                    volume=int(float(vol_str)) if vol_str not in ("--", "") else None,
                    trade_date=today,
                    source="TWSE",
                    is_cached=False,
                )
            except (ValueError, KeyError) as e:
                logger.debug(f"[TWSE] 解析行 {row} 失敗：{e}")
                continue

        self._cache = prices
        self._cache_time = datetime.now(timezone.utc)
        logger.info(f"[TWSE] 成功取得 {len(prices)} 筆行情")
        return prices

    def get_current_price(self, ticker: str) -> Optional[PriceData]:
        """取得單一股票的最新收盤價"""
        all_prices = self.get_all_prices()
        result = all_prices.get(ticker)
        if result is None:
            logger.warning(f"[TWSE] 找不到股票 {ticker} 的行情")
        return result

    def _fetch_with_retry(self, url: str) -> Optional[list]:
        """帶 retry 的 HTTP GET 請求"""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.debug(f"[TWSE] 請求 {url}（第 {attempt} 次）")
                resp = requests.get(url, headers=HEADERS, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.Timeout:
                logger.warning(f"[TWSE] 請求逾時（第 {attempt} 次）")
            except requests.exceptions.HTTPError as e:
                logger.warning(f"[TWSE] HTTP 錯誤：{e}（第 {attempt} 次）")
            except requests.exceptions.RequestException as e:
                logger.warning(f"[TWSE] 網路錯誤：{e}（第 {attempt} 次）")
            except Exception as e:
                logger.error(f"[TWSE] 未預期錯誤：{e}")
                break

            if attempt < MAX_RETRIES:
                logger.info(f"[TWSE] {RETRY_DELAY} 秒後重試...")
                time.sleep(RETRY_DELAY)

        return None

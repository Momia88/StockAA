"""
財團法人中華民國證券櫃檯買賣中心 (TPEx) Open API 資料提供者
API 文件: https://www.tpex.org.tw/openapi/
"""
import time
from datetime import date, datetime, timezone
from typing import Optional

import requests
import urllib3

from ..utils.logger import logger

# TPEx SSL 憑證缺少 Subject Key Identifier，Python 3.12+ 驗證失敗
# 此為 TPEx 伺服器端問題，對本機工具關閉驗證是可接受的權宜措施
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from .base import AbstractPriceProvider, PriceData

# TPEx Open API 端點（上櫃股票日行情）
TPEX_ALL_STOCKS_URL = (
    "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://www.tpex.org.tw/",
}

MAX_RETRIES = 3
RETRY_DELAY = 2


class TPExProvider(AbstractPriceProvider):
    """
    台灣上櫃股票 ETF 資料提供者
    使用 TPEx Open API 取得上櫃市場日行情
    """

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self._cache: dict[str, PriceData] = {}
        self._cache_time: Optional[datetime] = None

    def supports(self, ticker: str) -> bool:
        """TPEx 上櫃股票通常也是數字代碼"""
        return ticker.isdigit() or (len(ticker) == 6 and ticker[:4].isdigit())

    def get_all_prices(self) -> dict[str, PriceData]:
        """取得 TPEx 所有上櫃股票當日行情（批次）"""
        if self._cache and self._cache_time:
            elapsed = (datetime.now(timezone.utc) - self._cache_time).seconds
            if elapsed < 300:
                logger.debug(f"[TPEx] 使用記憶體快取（{elapsed} 秒前更新）")
                return self._cache

        logger.info("[TPEx] 正在抓取上櫃市場收盤行情...")
        raw_data = self._fetch_with_retry(TPEX_ALL_STOCKS_URL)
        if not raw_data:
            logger.warning("[TPEx] 無法取得行情，返回空字典")
            return {}

        today = date.today()
        prices: dict[str, PriceData] = {}

        for row in raw_data:
            try:
                ticker = row.get("SecuritiesCompanyCode", "").strip()
                name = row.get("CompanyName", "").strip()
                close_str = row.get("Close", "0").replace(",", "").strip()
                open_str = row.get("Open", "0").replace(",", "").strip()
                high_str = row.get("High", "0").replace(",", "").strip()
                low_str = row.get("Low", "0").replace(",", "").strip()
                vol_str = row.get("TradingShares", "0").replace(",", "").strip()

                if not ticker or close_str in ("--", "", "0", "0.00", "nan"):
                    continue

                prices[ticker] = PriceData(
                    ticker=ticker,
                    name=name,
                    close=float(close_str),
                    open=float(open_str) if open_str not in ("--", "", "nan") else None,
                    high=float(high_str) if high_str not in ("--", "", "nan") else None,
                    low=float(low_str) if low_str not in ("--", "", "nan") else None,
                    volume=int(float(vol_str)) if vol_str not in ("--", "", "nan") else None,
                    trade_date=today,
                    source="TPEx",
                    is_cached=False,
                )
            except (ValueError, KeyError) as e:
                logger.debug(f"[TPEx] 解析行失敗：{e}")
                continue

        self._cache = prices
        self._cache_time = datetime.now(timezone.utc)
        logger.info(f"[TPEx] 成功取得 {len(prices)} 筆行情")
        return prices

    def get_current_price(self, ticker: str) -> Optional[PriceData]:
        """取得單一上櫃股票的最新收盤價"""
        all_prices = self.get_all_prices()
        result = all_prices.get(ticker)
        if result is None:
            logger.warning(f"[TPEx] 找不到股票 {ticker} 的行情")
        return result

    def _fetch_with_retry(self, url: str) -> Optional[list]:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.debug(f"[TPEx] 請求 {url}（第 {attempt} 次）")
                resp = requests.get(url, headers=HEADERS, timeout=self.timeout, verify=False)
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.Timeout:
                logger.warning(f"[TPEx] 請求逾時（第 {attempt} 次）")
            except requests.exceptions.HTTPError as e:
                logger.warning(f"[TPEx] HTTP 錯誤：{e}（第 {attempt} 次）")
            except requests.exceptions.RequestException as e:
                logger.warning(f"[TPEx] 網路錯誤：{e}（第 {attempt} 次）")
            except Exception as e:
                logger.error(f"[TPEx] 未預期錯誤：{e}")
                break

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

        return None

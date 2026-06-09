"""
PriceHistory Repository — 股價快取資料存取層
"""
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..models.price_history import PriceHistory
from ..data_providers.base import PriceData
from ..utils.logger import logger


class PriceHistoryRepository:
    """股價歷史快取 CRUD"""

    def __init__(self, session: Session):
        self.session = session

    def get_by_date(self, ticker: str, trade_date: date) -> Optional[PriceHistory]:
        """取得指定股票某日的快取價格"""
        return (
            self.session.query(PriceHistory)
            .filter(PriceHistory.ticker == ticker, PriceHistory.date == trade_date)
            .first()
        )

    def get_all_by_date(self, trade_date: date) -> dict[str, PriceData]:
        """取得某日所有快取的股價，返回 {ticker: PriceData}"""
        rows = (
            self.session.query(PriceHistory)
            .filter(PriceHistory.date == trade_date)
            .all()
        )
        result: dict[str, PriceData] = {}
        for row in rows:
            result[row.ticker] = PriceData(
                ticker=row.ticker,
                name="",          # PriceHistory 不儲存股票名稱
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
        return result

    def upsert_batch(self, price_list: list[PriceData]) -> int:
        """
        批次寫入股價快取（upsert，以 ticker+date 為 unique key）

        Returns:
            寫入筆數
        """
        if not price_list:
            return 0

        now = datetime.now(timezone.utc)
        rows = [
            {
                "ticker": p.ticker,
                "date": p.trade_date,
                "open": p.open,
                "high": p.high,
                "low": p.low,
                "close": p.close,
                "volume": p.volume,
                "source": p.source,
                "fetched_at": now,
            }
            for p in price_list
        ]

        stmt = sqlite_insert(PriceHistory).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "date"],
            set_={
                "close": stmt.excluded.close,
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "volume": stmt.excluded.volume,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
        self.session.execute(stmt)
        self.session.flush()
        logger.debug(f"[PriceHistoryRepo] upsert {len(rows)} 筆股價快取")
        return len(rows)

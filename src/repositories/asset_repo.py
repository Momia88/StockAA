"""
Asset Repository — 持倉資料存取層
"""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from ..models.asset import Asset
from ..models.enums import AssetType, Exchange
from ..utils.exceptions import AssetAlreadyExistsError, AssetNotFoundError
from ..utils.logger import logger


class AssetRepository:
    """Asset CRUD 操作"""

    def __init__(self, session: Session):
        self.session = session

    def get_by_ticker(self, ticker: str) -> Optional[Asset]:
        """依股票代碼取得持倉"""
        return self.session.query(Asset).filter(Asset.ticker == ticker).first()

    def get_all_active(self) -> list[Asset]:
        """取得所有仍持有（qty > 0）的持倉"""
        return (
            self.session.query(Asset)
            .filter(Asset.quantity > 0)
            .order_by(Asset.ticker)
            .all()
        )

    def get_all(self) -> list[Asset]:
        """取得所有持倉（含已清倉）"""
        return self.session.query(Asset).order_by(Asset.ticker).all()

    def create(
        self,
        ticker: str,
        name: str,
        asset_type: AssetType,
        exchange: Exchange,
    ) -> Asset:
        """
        建立新的持倉記錄（首次買入時呼叫）

        Raises:
            AssetAlreadyExistsError: 若 ticker 已存在
        """
        existing = self.get_by_ticker(ticker)
        if existing is not None:
            raise AssetAlreadyExistsError(ticker)

        asset = Asset(
            ticker=ticker,
            name=name,
            asset_type=asset_type,
            exchange=exchange,
        )
        self.session.add(asset)
        self.session.flush()  # 取得 id 但不 commit
        logger.debug(f"[AssetRepo] 建立持倉：{ticker} {name}")
        return asset

    def get_or_create(
        self,
        ticker: str,
        name: str,
        asset_type: AssetType,
        exchange: Exchange,
    ) -> tuple[Asset, bool]:
        """
        取得或建立持倉（幂等操作）

        Returns:
            (Asset, created: bool)
        """
        existing = self.get_by_ticker(ticker)
        if existing is not None:
            return existing, False

        asset = Asset(
            ticker=ticker,
            name=name,
            asset_type=asset_type,
            exchange=exchange,
        )
        self.session.add(asset)
        self.session.flush()
        return asset, True

    def update_holding(
        self,
        asset: Asset,
        new_quantity: int,
        new_avg_cost: float,
        total_invested_delta: float,
    ) -> Asset:
        """更新持倉數量與成本"""
        asset.quantity = new_quantity
        asset.avg_cost = new_avg_cost
        asset.total_invested += total_invested_delta
        self.session.flush()
        return asset

    def update_realized_pnl(self, asset: Asset, pnl_delta: float) -> Asset:
        """累計已實現損益"""
        asset.realized_pnl += pnl_delta
        self.session.flush()
        return asset

    def update_dividend(self, asset: Asset, dividend_amount: float) -> Asset:
        """累計股利收入"""
        asset.total_dividend += dividend_amount
        self.session.flush()
        return asset

    def set_first_buy_date(self, asset: Asset, trade_date: date) -> None:
        """設定首次買入日期（僅在 first_buy_date 為 None 時更新）"""
        if asset.first_buy_date is None:
            asset.first_buy_date = trade_date
            self.session.flush()

    def delete(self, ticker: str) -> bool:
        """刪除持倉（連同交易記錄，需確認）"""
        asset = self.get_by_ticker(ticker)
        if asset is None:
            return False
        self.session.delete(asset)
        self.session.flush()
        logger.warning(f"[AssetRepo] 刪除持倉：{ticker}")
        return True

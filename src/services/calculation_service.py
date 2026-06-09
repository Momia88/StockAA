"""
Calculation Service — 投資組合損益與績效計算引擎
"""
from dataclasses import dataclass, field
from typing import Optional

from ..models.asset import Asset
from ..data_providers.base import PriceData


@dataclass
class AssetSnapshot:
    """單一持倉的損益快照"""
    ticker: str
    name: str
    asset_type: str
    exchange: str

    # 持倉數量與成本
    quantity: int
    avg_cost: float
    cost_basis: float          # 平均成本 × 持有股數

    # 市值相關
    current_price: Optional[float] = None
    market_value: Optional[float] = None   # 現價 × 持有股數
    is_price_stale: bool = False           # 股價是否為舊資料（休市）

    # 損益
    unrealized_pnl: Optional[float] = None       # 未實現損益
    unrealized_pnl_pct: Optional[float] = None   # 未實現損益率 %
    realized_pnl: float = 0.0                    # 已實現損益
    total_dividend: float = 0.0                  # 累計股利

    # 總損益（含股利）
    @property
    def total_return(self) -> Optional[float]:
        if self.unrealized_pnl is None:
            return self.realized_pnl + self.total_dividend
        return self.unrealized_pnl + self.realized_pnl + self.total_dividend

    @property
    def total_return_pct(self) -> Optional[float]:
        """總報酬率（%）"""
        if self.cost_basis == 0:
            return None
        total = self.total_return
        if total is None:
            return None
        return (total / self.cost_basis) * 100


@dataclass
class PortfolioSummary:
    """整個投資組合的彙總報表"""
    assets: list[AssetSnapshot] = field(default_factory=list)

    @property
    def total_cost_basis(self) -> float:
        """總投入成本"""
        return sum(a.cost_basis for a in self.assets if a.quantity > 0)

    @property
    def total_market_value(self) -> Optional[float]:
        """總市值"""
        values = [a.market_value for a in self.assets if a.market_value is not None]
        if not values:
            return None
        return sum(values)

    @property
    def total_unrealized_pnl(self) -> Optional[float]:
        """總未實現損益"""
        pnls = [a.unrealized_pnl for a in self.assets if a.unrealized_pnl is not None]
        if not pnls:
            return None
        return sum(pnls)

    @property
    def total_realized_pnl(self) -> float:
        """總已實現損益"""
        return sum(a.realized_pnl for a in self.assets)

    @property
    def total_dividend(self) -> float:
        """總股利收入"""
        return sum(a.total_dividend for a in self.assets)

    @property
    def total_return_pct(self) -> Optional[float]:
        """整體報酬率（%）"""
        if self.total_cost_basis == 0:
            return None
        unrealized = self.total_unrealized_pnl or 0.0
        total = unrealized + self.total_realized_pnl + self.total_dividend
        return (total / self.total_cost_basis) * 100

    @property
    def active_count(self) -> int:
        """仍持有的股票數量"""
        return sum(1 for a in self.assets if a.quantity > 0)


class CalculationService:
    """
    計算服務 — 整合持倉資料與即時股價，產出損益報告
    """

    def build_asset_snapshot(
        self,
        asset: Asset,
        price_data: Optional[PriceData],
    ) -> AssetSnapshot:
        """
        建立單一持倉的損益快照

        Args:
            asset: 持倉資料（來自 DB）
            price_data: 即時股價（來自 API 或快取，可為 None）
        """
        cost_basis = asset.avg_cost * asset.quantity

        # 計算市值與未實現損益
        current_price = None
        market_value = None
        unrealized_pnl = None
        unrealized_pnl_pct = None
        is_stale = False

        if price_data is not None:
            current_price = price_data.close
            is_stale = price_data.is_cached

            if asset.quantity > 0:
                market_value = current_price * asset.quantity
                unrealized_pnl = market_value - cost_basis
                if cost_basis > 0:
                    unrealized_pnl_pct = (unrealized_pnl / cost_basis) * 100

        return AssetSnapshot(
            ticker=asset.ticker,
            name=asset.name,
            asset_type=asset.asset_type.label,
            exchange=asset.exchange.value,
            quantity=asset.quantity,
            avg_cost=asset.avg_cost,
            cost_basis=cost_basis,
            current_price=current_price,
            market_value=market_value,
            is_price_stale=is_stale,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct,
            realized_pnl=asset.realized_pnl,
            total_dividend=asset.total_dividend,
        )

    def build_portfolio_summary(
        self,
        assets: list[Asset],
        prices: dict[str, Optional[PriceData]],
        active_only: bool = True,
    ) -> PortfolioSummary:
        """
        建立整體投資組合彙總

        Args:
            assets: 所有持倉資料
            prices: {ticker: PriceData or None}
            active_only: 是否只顯示仍持有的持倉
        """
        snapshots = []
        for asset in assets:
            if active_only and asset.quantity == 0:
                continue
            price_data = prices.get(asset.ticker)
            snapshot = self.build_asset_snapshot(asset, price_data)
            snapshots.append(snapshot)

        # 依資產類型排序：個股 → 股票ETF → 債券ETF
        type_order = {"個股": 0, "股票ETF": 1, "債券ETF": 2}
        snapshots.sort(key=lambda s: (type_order.get(s.asset_type, 9), s.ticker))

        return PortfolioSummary(assets=snapshots)

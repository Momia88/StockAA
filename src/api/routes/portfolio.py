"""
API 路由：投資組合查詢
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...repositories.asset_repo import AssetRepository
from ...services.calculation_service import CalculationService
from ...data_providers.price_manager import PriceManager
from ...utils.config import get_settings
from ..deps import get_session, get_sf
from ..schemas import AssetOut, PortfolioSummaryOut

router = APIRouter(prefix="/portfolio", tags=["投資組合"])


def _snap_to_out(snap) -> AssetOut:
    return AssetOut(
        ticker=snap.ticker,
        name=snap.name,
        asset_type=snap.asset_type,
        exchange=snap.exchange,
        quantity=snap.quantity,
        avg_cost=snap.avg_cost,
        cost_basis=snap.cost_basis,
        current_price=snap.current_price,
        market_value=snap.market_value,
        unrealized_pnl=snap.unrealized_pnl,
        unrealized_pnl_pct=snap.unrealized_pnl_pct,
        realized_pnl=snap.realized_pnl,
        total_dividend=snap.total_dividend,
        total_return=snap.total_return,
        is_price_stale=snap.is_price_stale,
    )


@router.get("/summary", response_model=PortfolioSummaryOut)
def get_portfolio_summary(
    include_closed: bool = False,
    no_price: bool = False,
    session: Session = Depends(get_session),
    sf=Depends(get_sf),
):
    """取得完整投資組合彙總（含即時股價）"""
    asset_repo = AssetRepository(session)
    assets = asset_repo.get_all() if include_closed else asset_repo.get_all_active()

    prices = {}
    if not no_price and assets:
        settings = get_settings()
        mgr = PriceManager(timeout=settings.api_timeout, session_factory=sf)
        tickers = [a.ticker for a in assets]
        prices = mgr.get_prices_batch(tickers)

    calc = CalculationService()
    summary = calc.build_portfolio_summary(assets, prices, active_only=not include_closed)

    return PortfolioSummaryOut(
        assets=[_snap_to_out(s) for s in summary.assets],
        total_cost_basis=summary.total_cost_basis,
        total_market_value=summary.total_market_value,
        total_unrealized_pnl=summary.total_unrealized_pnl,
        total_realized_pnl=summary.total_realized_pnl,
        total_dividend=summary.total_dividend,
        total_return_pct=summary.total_return_pct,
        active_count=summary.active_count,
    )

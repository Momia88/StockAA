"""
API 路由：股價查詢
"""
from fastapi import APIRouter, Depends, HTTPException

from ...data_providers.price_manager import PriceManager
from ...utils.config import get_settings
from ...utils.exceptions import PriceFetchError
from ..deps import get_sf
from ..schemas import PriceOut

router = APIRouter(prefix="/prices", tags=["股價"])


@router.get("/{ticker}", response_model=PriceOut)
def get_price(ticker: str, sf=Depends(get_sf)):
    """查詢單一股票即時股價"""
    settings = get_settings()
    mgr = PriceManager(timeout=settings.api_timeout, session_factory=sf)
    try:
        p = mgr.get_price(ticker)
        return PriceOut(
            ticker=p.ticker, name=p.name, close=p.close,
            open=p.open, high=p.high, low=p.low,
            volume=p.volume, trade_date=p.trade_date, source=p.source,
        )
    except PriceFetchError as e:
        raise HTTPException(404, str(e))

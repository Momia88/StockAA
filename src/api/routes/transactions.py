"""
API 路由：交易記錄操作
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...models.enums import AssetType, Exchange
from ...repositories.asset_repo import AssetRepository
from ...repositories.transaction_repo import TransactionRepository
from ...services.portfolio_service import PortfolioService
from ...utils.config import get_settings
from ...utils.exceptions import (
    AssetNotFoundError,
    InsufficientHoldingsError,
    InvalidTransactionError,
)
from ..deps import get_session
from ..schemas import (
    BuyRequest, SellRequest, DividendRequest,
    StockDividendRequest, SplitRequest,
    TransactionOut, MessageOut,
)

router = APIRouter(prefix="/transactions", tags=["交易記錄"])


def _tx_to_out(tx) -> TransactionOut:
    return TransactionOut(
        id=tx.id,
        ticker=tx.ticker,
        action=tx.action.value,
        price=tx.price,
        quantity=tx.quantity,
        fee=tx.fee,
        tax=tx.tax,
        net_amount=tx.net_amount,
        realized_pnl=tx.realized_pnl,
        avg_cost_at_tx=tx.avg_cost_at_tx,
        trade_date=tx.trade_date,
        note=tx.note,
    )


def _get_svc(session: Session, discount: Optional[float] = None) -> PortfolioService:
    settings = get_settings()
    d = discount if discount is not None else settings.brokerage_discount
    return PortfolioService(session, brokerage_discount=d)


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    ticker: Optional[str] = None,
    limit: int = 50,
    session: Session = Depends(get_session),
):
    """查詢交易記錄"""
    tx_repo = TransactionRepository(session)
    if ticker:
        txs = tx_repo.get_by_ticker(ticker, limit=limit)
    else:
        txs = tx_repo.get_all()[:limit]
    return [_tx_to_out(t) for t in txs]


@router.post("/buy", response_model=TransactionOut)
def buy(req: BuyRequest, session: Session = Depends(get_session)):
    """買入股票"""
    try:
        atype = AssetType(req.asset_type.upper())
        exch = Exchange(req.exchange.upper())
    except ValueError as e:
        raise HTTPException(400, str(e))

    svc = _get_svc(session, req.discount)
    try:
        _, tx = svc.buy(
            ticker=req.ticker, name=req.name,
            asset_type=atype, exchange=exch,
            price=req.price, quantity=req.quantity,
            trade_date=req.trade_date, note=req.note,
        )
        return _tx_to_out(tx)
    except InvalidTransactionError as e:
        raise HTTPException(400, str(e))


@router.post("/sell", response_model=TransactionOut)
def sell(req: SellRequest, session: Session = Depends(get_session)):
    """賣出股票"""
    svc = _get_svc(session, req.discount)
    try:
        _, tx = svc.sell(
            ticker=req.ticker, price=req.price,
            quantity=req.quantity, trade_date=req.trade_date,
            note=req.note,
        )
        return _tx_to_out(tx)
    except AssetNotFoundError as e:
        raise HTTPException(404, str(e))
    except (InsufficientHoldingsError, InvalidTransactionError) as e:
        raise HTTPException(400, str(e))


@router.post("/dividend", response_model=TransactionOut)
def dividend(req: DividendRequest, session: Session = Depends(get_session)):
    """記錄現金股利"""
    svc = _get_svc(session)
    qty = req.quantity
    if qty is None:
        asset = AssetRepository(session).get_by_ticker(req.ticker)
        if asset is None:
            raise HTTPException(404, f"找不到 {req.ticker} 的持倉")
        qty = asset.quantity
    try:
        _, tx = svc.add_dividend(
            ticker=req.ticker,
            dividend_per_share=req.dividend_per_share,
            quantity=qty,
            trade_date=req.trade_date,
            note=req.note,
        )
        return _tx_to_out(tx)
    except AssetNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/stock-dividend", response_model=TransactionOut)
def stock_dividend(req: StockDividendRequest, session: Session = Depends(get_session)):
    """記錄股票股利"""
    svc = _get_svc(session)
    try:
        _, tx = svc.add_stock_dividend(
            ticker=req.ticker, bonus_shares=req.bonus_shares,
            trade_date=req.trade_date, note=req.note,
        )
        return _tx_to_out(tx)
    except AssetNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/split", response_model=TransactionOut)
def split(req: SplitRequest, session: Session = Depends(get_session)):
    """記錄股票分割/合併"""
    svc = _get_svc(session)
    try:
        _, tx = svc.add_split(
            ticker=req.ticker, split_ratio=req.split_ratio,
            trade_date=req.trade_date, note=req.note,
        )
        return _tx_to_out(tx)
    except (AssetNotFoundError, InvalidTransactionError) as e:
        raise HTTPException(400, str(e))


@router.delete("/{tx_id}", response_model=MessageOut)
def delete_transaction(tx_id: str, session: Session = Depends(get_session)):
    """刪除交易記錄"""
    tx_repo = TransactionRepository(session)
    deleted = tx_repo.delete(tx_id)
    if not deleted:
        raise HTTPException(404, f"找不到交易記錄 {tx_id}")
    return MessageOut(message=f"已刪除 {tx_id}")

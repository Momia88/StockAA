"""
Transaction Repository — 交易記錄資料存取層
"""
from datetime import date
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..models.transaction import Transaction
from ..models.enums import TxAction
from ..utils.logger import logger


class TransactionRepository:
    """Transaction CRUD 操作"""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, tx_id: str) -> Optional[Transaction]:
        return self.session.query(Transaction).filter(Transaction.id == tx_id).first()

    def get_by_ticker(self, ticker: str, limit: Optional[int] = None) -> list[Transaction]:
        """取得指定股票的所有交易記錄（依日期降序）"""
        q = (
            self.session.query(Transaction)
            .filter(Transaction.ticker == ticker)
            .order_by(desc(Transaction.trade_date), desc(Transaction.created_at))
        )
        if limit:
            q = q.limit(limit)
        return q.all()

    def get_all(
        self,
        action: Optional[TxAction] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[Transaction]:
        """取得所有交易記錄，支援篩選"""
        q = self.session.query(Transaction).order_by(
            desc(Transaction.trade_date), desc(Transaction.created_at)
        )
        if action:
            q = q.filter(Transaction.action == action)
        if start_date:
            q = q.filter(Transaction.trade_date >= start_date)
        if end_date:
            q = q.filter(Transaction.trade_date <= end_date)
        return q.all()

    def create(
        self,
        asset_id: str,
        ticker: str,
        action: TxAction,
        price: float,
        quantity: int,
        fee: float,
        tax: float,
        net_amount: float,
        trade_date: date,
        realized_pnl: float = 0.0,
        avg_cost_at_tx: float = 0.0,
        settlement_date: Optional[date] = None,
        note: Optional[str] = None,
    ) -> Transaction:
        """建立新交易記錄"""
        tx = Transaction(
            asset_id=asset_id,
            ticker=ticker,
            action=action,
            price=price,
            quantity=quantity,
            fee=fee,
            tax=tax,
            net_amount=net_amount,
            trade_date=trade_date,
            realized_pnl=realized_pnl,
            avg_cost_at_tx=avg_cost_at_tx,
            settlement_date=settlement_date,
            note=note,
        )
        self.session.add(tx)
        self.session.flush()
        logger.debug(f"[TxRepo] 新增交易：{action.value} {ticker} {quantity}股 @{price}")
        return tx

    def delete(self, tx_id: str) -> bool:
        """刪除交易記錄（危險操作，須重新計算持倉）"""
        tx = self.get_by_id(tx_id)
        if tx is None:
            return False
        self.session.delete(tx)
        self.session.flush()
        logger.warning(f"[TxRepo] 刪除交易記錄：{tx_id}")
        return True

    def get_total_invested(self, ticker: str) -> float:
        """計算指定股票的總投入金額"""
        txs = self.get_by_ticker(ticker)
        total = 0.0
        for tx in txs:
            if tx.action == TxAction.BUY:
                total += tx.net_amount
        return total

    def get_total_dividend(self, ticker: str) -> float:
        """計算指定股票的累計股利"""
        txs = self.get_by_ticker(ticker)
        return sum(
            tx.price * tx.quantity
            for tx in txs
            if tx.action == TxAction.DIVIDEND
        )

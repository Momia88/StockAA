"""
Portfolio Service — 投資組合管理業務邏輯
處理買入、賣出、股利等交易，維護持倉狀態
"""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from ..models.asset import Asset
from ..models.enums import AssetType, Exchange, TxAction
from ..models.transaction import Transaction
from ..repositories.asset_repo import AssetRepository
from ..repositories.transaction_repo import TransactionRepository
from ..utils.exceptions import (
    AssetNotFoundError,
    InsufficientHoldingsError,
    InvalidTransactionError,
)
from ..utils.logger import logger
from ..utils.tw_fees import (
    calc_buy_net_amount,
    calc_new_avg_cost,
    calc_realized_pnl,
    calc_sell_net_amount,
)


class PortfolioService:
    """
    投資組合管理服務
    處理所有交易邏輯並維護持倉的一致性
    """

    def __init__(self, session: Session, brokerage_discount: float = 0.6):
        self.session = session
        self.asset_repo = AssetRepository(session)
        self.tx_repo = TransactionRepository(session)
        self.discount = brokerage_discount

    # ──────────────────────────────────────────
    # 買入
    # ──────────────────────────────────────────
    def buy(
        self,
        ticker: str,
        name: str,
        asset_type: AssetType,
        exchange: Exchange,
        price: float,
        quantity: int,
        trade_date: date,
        note: Optional[str] = None,
    ) -> tuple[Asset, Transaction]:
        """
        執行買入操作

        Args:
            ticker: 股票代碼
            name: 股票名稱
            asset_type: 資產類型
            exchange: 交易所
            price: 買入單價（元/股）
            quantity: 買入股數（必須 > 0）
            trade_date: 交易日期
            note: 備註

        Returns:
            (更新後的 Asset, 新增的 Transaction)
        """
        if quantity <= 0:
            raise InvalidTransactionError(f"買入股數必須大於 0，收到：{quantity}")
        if price <= 0:
            raise InvalidTransactionError(f"買入單價必須大於 0，收到：{price}")

        # 取得或建立持倉
        asset, created = self.asset_repo.get_or_create(
            ticker=ticker,
            name=name,
            asset_type=asset_type,
            exchange=exchange,
        )

        # 計算費用
        net_amount, fee, tax = calc_buy_net_amount(price, quantity, self.discount)

        # 計算新平均成本
        new_avg_cost = calc_new_avg_cost(
            old_qty=asset.quantity,
            old_avg_cost=asset.avg_cost,
            buy_qty=quantity,
            buy_price=price,
            buy_fee=fee,
        )

        # 更新持倉
        new_qty = asset.quantity + quantity
        self.asset_repo.update_holding(
            asset=asset,
            new_quantity=new_qty,
            new_avg_cost=new_avg_cost,
            total_invested_delta=net_amount,
        )
        self.asset_repo.set_first_buy_date(asset, trade_date)

        # 記錄交易
        tx = self.tx_repo.create(
            asset_id=asset.id,
            ticker=ticker,
            action=TxAction.BUY,
            price=price,
            quantity=quantity,
            fee=fee,
            tax=tax,
            net_amount=net_amount,
            trade_date=trade_date,
            avg_cost_at_tx=new_avg_cost,
            note=note,
        )

        logger.info(
            f"[Portfolio] 買入 {ticker} {quantity}股 @{price:.2f} "
            f"費:{fee:.0f} 均成本→{new_avg_cost:.4f}"
        )
        return asset, tx

    # ──────────────────────────────────────────
    # 賣出
    # ──────────────────────────────────────────
    def sell(
        self,
        ticker: str,
        price: float,
        quantity: int,
        trade_date: date,
        note: Optional[str] = None,
    ) -> tuple[Asset, Transaction]:
        """
        執行賣出操作

        Raises:
            AssetNotFoundError: 找不到持倉
            InsufficientHoldingsError: 賣出股數超過持有量
        """
        if quantity <= 0:
            raise InvalidTransactionError(f"賣出股數必須大於 0，收到：{quantity}")
        if price <= 0:
            raise InvalidTransactionError(f"賣出單價必須大於 0，收到：{price}")

        asset = self.asset_repo.get_by_ticker(ticker)
        if asset is None:
            raise AssetNotFoundError(ticker)
        if asset.quantity < quantity:
            raise InsufficientHoldingsError(ticker, asset.quantity, quantity)

        # 計算費用（賣出）
        net_amount, fee, tax = calc_sell_net_amount(
            price, quantity, asset.asset_type, self.discount
        )

        # 計算已實現損益
        pnl = calc_realized_pnl(
            sell_qty=quantity,
            sell_price=price,
            avg_cost=asset.avg_cost,
            fee=fee,
            tax=tax,
        )

        # 更新持倉（avg_cost 不變，平均成本法）
        new_qty = asset.quantity - quantity
        self.asset_repo.update_holding(
            asset=asset,
            new_quantity=new_qty,
            new_avg_cost=asset.avg_cost if new_qty > 0 else 0.0,
            total_invested_delta=net_amount,  # 負數（收入）
        )
        self.asset_repo.update_realized_pnl(asset, pnl)

        # 記錄交易
        tx = self.tx_repo.create(
            asset_id=asset.id,
            ticker=ticker,
            action=TxAction.SELL,
            price=price,
            quantity=quantity,
            fee=fee,
            tax=tax,
            net_amount=net_amount,
            trade_date=trade_date,
            realized_pnl=pnl,
            avg_cost_at_tx=asset.avg_cost,
            note=note,
        )

        logger.info(
            f"[Portfolio] 賣出 {ticker} {quantity}股 @{price:.2f} "
            f"費:{fee:.0f} 稅:{tax:.0f} 損益:{pnl:+.2f}"
        )
        return asset, tx

    # ──────────────────────────────────────────
    # 現金股利
    # ──────────────────────────────────────────
    def add_dividend(
        self,
        ticker: str,
        dividend_per_share: float,
        quantity: int,
        trade_date: date,
        note: Optional[str] = None,
    ) -> tuple[Asset, Transaction]:
        """
        記錄現金股利

        Args:
            dividend_per_share: 每股股利（元）
            quantity: 領息股數（通常等於持有股數）
        """
        asset = self.asset_repo.get_by_ticker(ticker)
        if asset is None:
            raise AssetNotFoundError(ticker)

        total_dividend = dividend_per_share * quantity
        self.asset_repo.update_dividend(asset, total_dividend)

        tx = self.tx_repo.create(
            asset_id=asset.id,
            ticker=ticker,
            action=TxAction.DIVIDEND,
            price=dividend_per_share,
            quantity=quantity,
            fee=0.0,
            tax=0.0,
            net_amount=-total_dividend,  # 負數代表現金流入
            trade_date=trade_date,
            note=note,
        )

        logger.info(f"[Portfolio] 股利 {ticker} 每股{dividend_per_share:.4f} 共{total_dividend:.2f}元")
        return asset, tx

    # ──────────────────────────────────────────
    # 股票股利（無償配股）
    # ──────────────────────────────────────────
    def add_stock_dividend(
        self,
        ticker: str,
        bonus_shares: int,
        trade_date: date,
        note: Optional[str] = None,
    ) -> tuple[Asset, Transaction]:
        """
        記錄股票股利（增加股數，降低平均成本）

        Args:
            bonus_shares: 配發的股數
        """
        asset = self.asset_repo.get_by_ticker(ticker)
        if asset is None:
            raise AssetNotFoundError(ticker)

        old_qty = asset.quantity
        new_qty = old_qty + bonus_shares

        # 股票股利降低平均成本（成本不變，股數增加）
        new_avg_cost = (asset.avg_cost * old_qty) / new_qty if new_qty > 0 else 0.0

        self.asset_repo.update_holding(
            asset=asset,
            new_quantity=new_qty,
            new_avg_cost=round(new_avg_cost, 4),
            total_invested_delta=0.0,
        )

        tx = self.tx_repo.create(
            asset_id=asset.id,
            ticker=ticker,
            action=TxAction.STOCK_DIVIDEND,
            price=0.0,
            quantity=bonus_shares,
            fee=0.0,
            tax=0.0,
            net_amount=0.0,
            trade_date=trade_date,
            avg_cost_at_tx=new_avg_cost,
            note=note,
        )

        logger.info(
            f"[Portfolio] 股票股利 {ticker} +{bonus_shares}股 "
            f"均成本 {asset.avg_cost:.4f}→{new_avg_cost:.4f}"
        )
        return asset, tx

    # ──────────────────────────────────────────
    # 股票分割 / 合併
    # ──────────────────────────────────────────
    def add_split(
        self,
        ticker: str,
        split_ratio: float,
        trade_date: date,
        note: Optional[str] = None,
    ) -> tuple[Asset, Transaction]:
        """
        記錄股票分割或合併（反向分割）

        Args:
            split_ratio: 分割比例（2.0 = 2:1 分割，持股×2、均成本÷2；
                         0.5 = 1:2 反向合併，持股÷2、均成本×2）

        Raises:
            AssetNotFoundError: 找不到持倉
            InvalidTransactionError: ratio <= 0 或持股數為 0
        """
        if split_ratio <= 0:
            raise InvalidTransactionError(f"分割比例必須 > 0，收到：{split_ratio}")

        asset = self.asset_repo.get_by_ticker(ticker)
        if asset is None:
            raise AssetNotFoundError(ticker)
        if asset.quantity == 0:
            raise InvalidTransactionError(f"{ticker} 目前無持倉，無法進行分割/合併")

        old_qty = asset.quantity
        old_avg_cost = asset.avg_cost

        new_qty = round(old_qty * split_ratio)
        share_delta = new_qty - old_qty

        # 成本總額不變，按新股數重算均成本
        new_avg_cost = round(
            (old_avg_cost * old_qty) / new_qty, 4
        ) if new_qty > 0 else 0.0

        self.asset_repo.update_holding(
            asset=asset,
            new_quantity=new_qty,
            new_avg_cost=new_avg_cost,
            total_invested_delta=0.0,  # 分割不改變總投入金額
        )

        tx = self.tx_repo.create(
            asset_id=asset.id,
            ticker=ticker,
            action=TxAction.SPLIT,
            price=0.0,
            quantity=share_delta,      # 正=分割，負=合併
            fee=0.0,
            tax=0.0,
            net_amount=0.0,
            trade_date=trade_date,
            avg_cost_at_tx=new_avg_cost,
            note=note or f"分割比例 {split_ratio}:1",
        )

        logger.info(
            f"[Portfolio] 股票分割 {ticker} 比例 {split_ratio}:1 "
            f"股數 {old_qty}→{new_qty} 均成本 {old_avg_cost:.4f}→{new_avg_cost:.4f}"
        )
        return asset, tx

    # ──────────────────────────────────────────
    # 刪除交易 + 重算持倉
    # ──────────────────────────────────────────
    def delete_transaction(self, tx_id: str) -> str:
        """刪除指定交易並從剩餘交易重建持倉狀態"""
        tx = self.tx_repo.get_by_id(tx_id)
        if tx is None:
            raise InvalidTransactionError(f"找不到交易記錄：{tx_id}")
        ticker = tx.ticker
        self.tx_repo.delete(tx_id)
        self._recalculate_asset(ticker)
        logger.info(f"[Portfolio] 刪除交易 {tx_id}，已重算 {ticker} 持倉")
        return ticker

    def edit_transaction(
        self,
        tx_id: str,
        price: float,
        quantity: int,
        trade_date,
        note: Optional[str] = None,
    ) -> tuple[Asset, Transaction]:
        """修改交易（刪舊記錄→重算持倉→以修正值新增）"""
        tx = self.tx_repo.get_by_id(tx_id)
        if tx is None:
            raise InvalidTransactionError(f"找不到交易記錄：{tx_id}")

        ticker = tx.ticker
        action = tx.action
        asset = self.asset_repo.get_by_ticker(ticker)

        # 先儲存 BUY 需要的欄位（刪除後 asset 還在，但先記住）
        asset_name = asset.name if asset else ticker
        asset_type = asset.asset_type if asset else None
        asset_exchange = asset.exchange if asset else None

        self.tx_repo.delete(tx_id)
        self._recalculate_asset(ticker)

        if action == TxAction.BUY:
            if asset_type is None or asset_exchange is None:
                raise InvalidTransactionError(f"找不到 {ticker} 的持倉資訊，無法重建買入交易")
            return self.buy(
                ticker=ticker, name=asset_name,
                asset_type=asset_type, exchange=asset_exchange,
                price=price, quantity=quantity, trade_date=trade_date, note=note,
            )
        elif action == TxAction.SELL:
            return self.sell(
                ticker=ticker, price=price, quantity=quantity,
                trade_date=trade_date, note=note,
            )
        elif action == TxAction.DIVIDEND:
            return self.add_dividend(
                ticker=ticker, dividend_per_share=price,
                quantity=quantity, trade_date=trade_date, note=note,
            )
        elif action == TxAction.STOCK_DIVIDEND:
            return self.add_stock_dividend(
                ticker=ticker, bonus_shares=quantity,
                trade_date=trade_date, note=note,
            )
        elif action == TxAction.SPLIT:
            # SPLIT 需要 ratio，由 edit_split_transaction 處理
            raise InvalidTransactionError("股票分割請使用「刪除後重新新增」方式修改")
        else:
            raise InvalidTransactionError(f"不支援修改的交易類型：{action}")

    def edit_split_transaction(
        self,
        tx_id: str,
        split_ratio: float,
        trade_date,
        note: Optional[str] = None,
    ) -> tuple[Asset, Transaction]:
        """修改分割交易（刪除→重算→以新比例重建）"""
        tx = self.tx_repo.get_by_id(tx_id)
        if tx is None:
            raise InvalidTransactionError(f"找不到交易記錄：{tx_id}")
        ticker = tx.ticker
        self.tx_repo.delete(tx_id)
        self._recalculate_asset(ticker)
        return self.add_split(ticker, split_ratio, trade_date, note)

    # ──────────────────────────────────────────
    # 內部：從交易記錄重建持倉狀態
    # ──────────────────────────────────────────
    def _recalculate_asset(self, ticker: str) -> None:
        """從所有剩餘交易按時序重播，重建 Asset 的各項數值"""
        asset = self.asset_repo.get_by_ticker(ticker)
        if asset is None:
            return

        txs = sorted(
            self.tx_repo.get_by_ticker(ticker),
            key=lambda t: (t.trade_date, t.created_at),
        )

        qty = 0
        avg_cost = 0.0
        total_invested = 0.0
        realized_pnl = 0.0
        total_dividend = 0.0
        first_buy_date = None

        for tx in txs:
            if tx.action == TxAction.BUY:
                avg_cost = calc_new_avg_cost(qty, avg_cost, tx.quantity, tx.price, tx.fee)
                qty += tx.quantity
                total_invested += tx.net_amount
                tx.avg_cost_at_tx = avg_cost
                if first_buy_date is None or tx.trade_date < first_buy_date:
                    first_buy_date = tx.trade_date

            elif tx.action == TxAction.SELL:
                pnl = calc_realized_pnl(tx.quantity, tx.price, avg_cost, tx.fee, tx.tax)
                tx.realized_pnl = pnl
                tx.avg_cost_at_tx = avg_cost
                realized_pnl += pnl
                qty -= tx.quantity
                total_invested += tx.net_amount  # 負數（收入）

            elif tx.action == TxAction.DIVIDEND:
                total_dividend += tx.price * tx.quantity

            elif tx.action == TxAction.STOCK_DIVIDEND:
                new_qty = qty + tx.quantity
                avg_cost = round((avg_cost * qty) / new_qty, 4) if new_qty > 0 else 0.0
                qty = new_qty
                tx.avg_cost_at_tx = avg_cost

            elif tx.action == TxAction.SPLIT:
                old_qty = qty
                qty = old_qty + tx.quantity  # quantity = share_delta
                avg_cost = round((avg_cost * old_qty) / qty, 4) if qty > 0 else 0.0
                tx.avg_cost_at_tx = avg_cost

        asset.quantity = max(0, qty)
        asset.avg_cost = round(avg_cost, 4) if qty > 0 else 0.0
        asset.total_invested = round(total_invested, 2)
        asset.realized_pnl = round(realized_pnl, 2)
        asset.total_dividend = round(total_dividend, 2)
        asset.first_buy_date = first_buy_date
        self.session.flush()
        logger.info(f"[Portfolio] 重算完成 {ticker}：持股 {asset.quantity} 均成本 {asset.avg_cost:.4f}")

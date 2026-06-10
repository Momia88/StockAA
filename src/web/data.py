"""
Streamlit 資料存取層 — 直接使用 Python service layer（不經過 HTTP）
"""
import sys
from pathlib import Path

# 確保專案根目錄在 sys.path
_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from typing import Optional

from sqlalchemy.orm import sessionmaker as _sessionmaker
from src.models.database import create_all_tables, get_db_session, get_engine
from src.models.enums import AssetType, Exchange
from src.repositories.asset_repo import AssetRepository
from src.repositories.transaction_repo import TransactionRepository
from src.services.calculation_service import CalculationService, PortfolioSummary
from src.services.portfolio_service import PortfolioService
from src.data_providers.price_manager import PriceManager
from src.utils.config import get_settings
from src.utils.exceptions import AssetNotFoundError

import streamlit as st


@st.cache_resource
def _get_session_factory():
    settings = get_settings()
    engine = get_engine(settings.db_path)
    create_all_tables(engine)
    return _sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


def get_portfolio_summary(include_closed: bool = False, no_price: bool = False) -> PortfolioSummary:
    sf = _get_session_factory()
    settings = get_settings()

    with get_db_session(sf) as session:
        repo = AssetRepository(session)
        assets = repo.get_all() if include_closed else repo.get_all_active()

        prices = {}
        if not no_price and assets:
            mgr = PriceManager(timeout=settings.api_timeout, session_factory=sf)
            tickers = [a.ticker for a in assets]
            try:
                prices = mgr.get_prices_batch(tickers)
            except Exception:
                pass

        calc = CalculationService()
        return calc.build_portfolio_summary(assets, prices, active_only=not include_closed)


def get_transactions(ticker: Optional[str] = None, limit: int = 100):
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        repo = TransactionRepository(session)
        if ticker:
            return repo.get_by_ticker(ticker, limit=limit)
        return repo.get_all()[:limit]


def do_buy(ticker, name, asset_type_str, exchange_str, price, quantity, trade_date, note=None):
    sf = _get_session_factory()
    settings = get_settings()
    with get_db_session(sf) as session:
        svc = PortfolioService(session, brokerage_discount=settings.brokerage_discount)
        atype = AssetType(asset_type_str)
        exch = Exchange(exchange_str)
        asset, tx = svc.buy(
            ticker=ticker, name=name, asset_type=atype, exchange=exch,
            price=price, quantity=quantity, trade_date=trade_date, note=note,
        )
        return asset.avg_cost, asset.quantity, tx.fee


def do_sell(ticker, price, quantity, trade_date, note=None):
    sf = _get_session_factory()
    settings = get_settings()
    with get_db_session(sf) as session:
        svc = PortfolioService(session, brokerage_discount=settings.brokerage_discount)
        asset, tx = svc.sell(
            ticker=ticker, price=price, quantity=quantity,
            trade_date=trade_date, note=note,
        )
        return tx.realized_pnl, tx.fee, tx.tax, asset.quantity


def do_dividend(ticker, dividend_per_share, trade_date, quantity=None, note=None):
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        svc = PortfolioService(session)
        if quantity is None:
            repo = AssetRepository(session)
            a = repo.get_by_ticker(ticker)
            if a is None:
                raise AssetNotFoundError(ticker)
            quantity = a.quantity
        asset, tx = svc.add_dividend(
            ticker=ticker, dividend_per_share=dividend_per_share,
            quantity=quantity, trade_date=trade_date, note=note,
        )
        return dividend_per_share * quantity


def do_split(ticker, split_ratio, trade_date, note=None):
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        svc = PortfolioService(session)
        asset, tx = svc.add_split(
            ticker=ticker, split_ratio=split_ratio,
            trade_date=trade_date, note=note,
        )
        return asset.quantity, asset.avg_cost


def get_transaction_detail(tx_id: str) -> Optional[dict]:
    """取得單筆交易的完整資料（含對應 Asset 資訊），以 dict 回傳避免 detached 問題"""
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        tx_repo = TransactionRepository(session)
        asset_repo = AssetRepository(session)
        tx = tx_repo.get_by_id(tx_id)
        if tx is None:
            return None
        asset = asset_repo.get_by_ticker(tx.ticker)
        return {
            "id":           tx.id,
            "ticker":       tx.ticker,
            "action":       tx.action.value,
            "price":        tx.price,
            "quantity":     tx.quantity,
            "fee":          tx.fee,
            "tax":          tx.tax,
            "net_amount":   tx.net_amount,
            "trade_date":   tx.trade_date,
            "note":         tx.note or "",
            "realized_pnl": tx.realized_pnl,
            "asset_name":   asset.name        if asset else "",
            "asset_type":   asset.asset_type.value if asset else "",
            "exchange":     asset.exchange.value   if asset else "",
        }


def do_delete_transaction(tx_id: str) -> str:
    """刪除交易並重算持倉，回傳受影響的 ticker"""
    sf = _get_session_factory()
    settings = get_settings()
    with get_db_session(sf) as session:
        svc = PortfolioService(session, brokerage_discount=settings.brokerage_discount)
        return svc.delete_transaction(tx_id)


def do_edit_transaction(tx_id: str, price: float, quantity: int, trade_date, note: str) -> None:
    """修改買入/賣出/股利交易（刪舊→重算→新增修正版）"""
    sf = _get_session_factory()
    settings = get_settings()
    with get_db_session(sf) as session:
        svc = PortfolioService(session, brokerage_discount=settings.brokerage_discount)
        svc.edit_transaction(tx_id, price=price, quantity=quantity,
                             trade_date=trade_date, note=note or None)


def do_edit_split(tx_id: str, split_ratio: float, trade_date, note: str) -> None:
    """修改分割交易"""
    sf = _get_session_factory()
    settings = get_settings()
    with get_db_session(sf) as session:
        svc = PortfolioService(session, brokerage_discount=settings.brokerage_discount)
        svc.edit_split_transaction(tx_id, split_ratio=split_ratio,
                                   trade_date=trade_date, note=note or None)


def get_asset_tickers() -> list[str]:
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        repo = AssetRepository(session)
        return [a.ticker for a in repo.get_all_active()]


def get_active_assets_brief() -> list[dict]:
    """取得所有在持個股的代碼、名稱與股數，供下拉選單顯示「代碼 名稱」與預設領息股數"""
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        repo = AssetRepository(session)
        return [
            {"ticker": a.ticker, "name": a.name, "quantity": a.quantity}
            for a in repo.get_all_active()
        ]


def get_recent_assets(limit: int = 6) -> list[dict]:
    """取得最近交易過的股票（去重），供買入表單快速帶入"""
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        tx_repo = TransactionRepository(session)
        asset_repo = AssetRepository(session)
        txs = tx_repo.get_all()  # 已依日期降序
        seen = []
        result = []
        for tx in txs:
            if tx.ticker in seen:
                continue
            asset = asset_repo.get_by_ticker(tx.ticker)
            if asset is None:
                continue
            seen.append(tx.ticker)
            result.append({
                "ticker":     asset.ticker,
                "name":       asset.name,
                "asset_type": asset.asset_type.value,
                "exchange":   asset.exchange.value,
            })
            if len(result) >= limit:
                break
        return result


def get_last_trade_date():
    """取得最近一筆交易的日期（無交易則回傳 None）"""
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        tx_repo = TransactionRepository(session)
        txs = tx_repo.get_all()
        return txs[0].trade_date if txs else None


def get_transactions_dataframe_rows(ticker=None, limit=500) -> list[dict]:
    """取得交易記錄的純資料 list[dict]，供 CSV 匯出"""
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        repo = TransactionRepository(session)
        txs = repo.get_by_ticker(ticker, limit=limit) if ticker else repo.get_all()[:limit]
        return [{
            "交易日":     str(t.trade_date),
            "代碼":       t.ticker,
            "類型":       t.action.value,
            "單價":       t.price,
            "股數":       t.quantity,
            "手續費":     t.fee,
            "交易稅":     t.tax,
            "淨金額":     t.net_amount,
            "已實現損益": t.realized_pnl,
            "備註":       t.note or "",
        } for t in txs]

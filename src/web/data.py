"""
Streamlit 資料存取層 — 直接使用 Python service layer（不經過 HTTP）
"""
import sys
import threading
from datetime import date, timedelta
from pathlib import Path

# 確保專案根目錄在 sys.path
_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from typing import Optional

from sqlalchemy.orm import sessionmaker as _sessionmaker
from src.models.database import create_all_tables, get_db_session, get_engine
from src.models.asset import Asset
from src.models.transaction import Transaction
from src.models.enums import AssetType, Exchange
from src.models.liability import LiabilityType
from src.repositories.asset_repo import AssetRepository
from src.repositories.liability_repo import LiabilityRepository, SettingRepository
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


def get_portfolio_summary(
    include_closed: bool = False,
    no_price: bool = False,
    cache_only: bool = False,
) -> PortfolioSummary:
    """取得投資組合摘要。

    cache_only=True 時只讀 SQLite 價格快取、不打網路（前端用來秒開頁面，
    現價之後由背景執行緒補上，見 ensure_prices_async）。
    """
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
                prices = mgr.get_prices_batch(tickers, cache_only=cache_only)
            except Exception:
                pass

        calc = CalculationService()
        return calc.build_portfolio_summary(assets, prices, active_only=not include_closed)


# ─────────────────────────────────────────────────────────
# 背景非同步抓取現價（先載入頁面、再更新價格）
# ─────────────────────────────────────────────────────────
_price_state: dict[str, str] = {}     # 今日 ISO 日期 -> "pending"/"done"
_price_lock = threading.Lock()


def _today_key() -> str:
    return date.today().isoformat()


def ensure_prices_async(tickers: list[str], force: bool = False) -> None:
    """確保今日現價在背景抓取中（不阻塞前端）。

    - 若快取已齊全：直接標記完成，不抓取。
    - 否則啟動一個 daemon 執行緒抓取全市場行情並寫入 SQLite 快取。
    - force=True 一律重抓（供「更新行情」用）。
    """
    if not tickers:
        return
    key = _today_key()
    sf = _get_session_factory()
    settings = get_settings()

    with _price_lock:
        state = _price_state.get(key)
        if not force:
            if state in ("pending", "done"):
                return
            mgr = PriceManager(timeout=settings.api_timeout, session_factory=sf)
            cached = mgr.get_prices_batch(tickers, cache_only=True)
            if all(cached.get(t) is not None for t in tickers):
                _price_state[key] = "done"
                return
        _price_state[key] = "pending"

    def _worker():
        try:
            mgr = PriceManager(timeout=settings.api_timeout, session_factory=sf)
            mgr.get_prices_batch(tickers, force_refresh=force)
        except Exception:
            pass
        finally:
            with _price_lock:
                _price_state[key] = "done"

    threading.Thread(target=_worker, daemon=True).start()


def prices_ready(tickers: list[str]) -> bool:
    """背景抓取是否已完成（完成後前端可重讀快取顯示最新現價）"""
    if not tickers:
        return True
    return _price_state.get(_today_key()) == "done"


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
    """取得交易記錄的純資料 list[dict]，供 CSV 匯出（含名稱/類型/交易所以利重新匯入）"""
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        repo = TransactionRepository(session)
        asset_repo = AssetRepository(session)
        meta = {a.ticker: a for a in asset_repo.get_all()}
        txs = repo.get_by_ticker(ticker, limit=limit) if ticker else repo.get_all()[:limit]
        rows = []
        for t in txs:
            a = meta.get(t.ticker)
            rows.append({
                "交易日":     str(t.trade_date),
                "代碼":       t.ticker,
                "名稱":       a.name if a else "",
                "資產類型":   a.asset_type.value if a else "",
                "交易所":     a.exchange.value if a else "",
                "類型":       t.action.value,
                "單價":       t.price,
                "股數":       t.quantity,
                "手續費":     t.fee,
                "交易稅":     t.tax,
                "淨金額":     t.net_amount,
                "已實現損益": t.realized_pnl,
                "備註":       t.note or "",
            })
        return rows


# ─────────────────────────────────────────────────────────
# CSV 匯入
# ─────────────────────────────────────────────────────────
_ACTION_IMPORT = {
    "BUY": "BUY", "買入": "BUY",
    "SELL": "SELL", "賣出": "SELL",
    "DIVIDEND": "DIVIDEND", "現金股利": "DIVIDEND",
    "STOCK_DIVIDEND": "STOCK_DIVIDEND", "股票股利": "STOCK_DIVIDEND",
    "SPLIT": "SPLIT", "分割/合併": "SPLIT", "分割": "SPLIT",
}
_ATYPE_IMPORT = {
    "STOCK": "STOCK", "個股": "STOCK",
    "STOCK_ETF": "STOCK_ETF", "股票ETF": "STOCK_ETF",
    "BOND_ETF": "BOND_ETF", "債券ETF": "BOND_ETF",
}
_EXCH_IMPORT = {"TWSE": "TWSE", "上市": "TWSE", "TPEx": "TPEx", "上櫃": "TPEx"}


def _infer_asset_type(ticker: str) -> str:
    """缺資產類型時的推斷：B 結尾→債券ETF、00 開頭→股票ETF、其餘→個股"""
    t = ticker.upper()
    if t.endswith("B"):
        return "BOND_ETF"
    if t.startswith("00"):
        return "STOCK_ETF"
    return "STOCK"


def _parse_import_date(raw: str):
    from datetime import date as _date
    s = raw.strip().replace("/", "-")
    try:
        return _date.fromisoformat(s)
    except ValueError:
        raise ValueError(f"日期格式無法解析：{raw}")


def _to_float(s: str) -> float:
    return float(str(s).replace(",", "").strip() or 0)


def _to_int(s: str) -> int:
    return int(round(_to_float(s)))


def _parse_import_row(row: dict) -> dict:
    def g(*keys):
        for k in keys:
            if k in row and str(row[k]).strip() != "":
                return str(row[k]).strip()
        return ""

    raw_date = g("交易日", "日期", "date")
    if not raw_date:
        raise ValueError("缺少交易日")
    ticker = g("代碼", "ticker")
    if not ticker:
        raise ValueError("缺少代碼")
    raw_action = g("類型", "action")
    action = _ACTION_IMPORT.get(raw_action)
    if action is None:
        raise ValueError(f"未知交易類型：{raw_action}")

    return {
        "date": _parse_import_date(raw_date),
        "ticker": ticker,
        "action": action,
        "price": _to_float(g("單價", "price") or "0"),
        "quantity": _to_int(g("股數", "quantity") or "0"),
        "name": g("名稱", "name") or ticker,
        "asset_type": _ATYPE_IMPORT.get(g("資產類型"), "") or _infer_asset_type(ticker),
        "exchange": _EXCH_IMPORT.get(g("交易所"), "") or "TWSE",
        "note": g("備註", "note") or None,
    }


def _apply_import_row(svc: PortfolioService, session, r: dict) -> None:
    a = r["action"]
    if a == "BUY":
        svc.buy(
            ticker=r["ticker"], name=r["name"],
            asset_type=AssetType(r["asset_type"]), exchange=Exchange(r["exchange"]),
            price=r["price"], quantity=r["quantity"],
            trade_date=r["date"], note=r["note"],
        )
    elif a == "SELL":
        svc.sell(ticker=r["ticker"], price=r["price"], quantity=r["quantity"],
                 trade_date=r["date"], note=r["note"])
    elif a == "DIVIDEND":
        svc.add_dividend(ticker=r["ticker"], dividend_per_share=r["price"],
                         quantity=r["quantity"], trade_date=r["date"], note=r["note"])
    elif a == "STOCK_DIVIDEND":
        svc.add_stock_dividend(ticker=r["ticker"], bonus_shares=r["quantity"],
                               trade_date=r["date"], note=r["note"])
    elif a == "SPLIT":
        cur = AssetRepository(session).get_by_ticker(r["ticker"])
        if cur is None or cur.quantity == 0:
            raise ValueError("分割前無持倉，無法重建比例")
        ratio = (cur.quantity + r["quantity"]) / cur.quantity
        svc.add_split(ticker=r["ticker"], split_ratio=ratio,
                      trade_date=r["date"], note=r["note"])


def import_transactions(rows: list[dict], replace: bool = False) -> dict:
    """批次匯入交易。依日期排序逐筆過 service（自動算費用、重算持倉）。

    replace=True 會先清空現有所有交易與持倉。回傳 {success, failed, errors}。
    """
    sf = _get_session_factory()
    settings = get_settings()

    parsed, errors = [], []
    for i, row in enumerate(rows, start=2):  # 第 1 列為標題
        try:
            parsed.append(_parse_import_row(row))
        except Exception as e:
            errors.append(f"第 {i} 列：{e}")

    # 排序策略：結構性交易（買/賣/分割/股票股利）依日期先行，現金股利最後再套用。
    # 因現金股利不影響均成本與股數，最後處理可避免「股利日期早於買入日期」時
    # 持倉尚未建立而失敗；結構性交易維持日期順序以確保均成本/已實現損益正確。
    parsed.sort(key=lambda r: r["date"])
    structural = [r for r in parsed if r["action"] != "DIVIDEND"]
    dividends = [r for r in parsed if r["action"] == "DIVIDEND"]
    ordered = structural + dividends

    success = 0
    with get_db_session(sf) as session:
        if replace:
            session.query(Transaction).delete()
            session.query(Asset).delete()
            session.flush()
        svc = PortfolioService(session, brokerage_discount=settings.brokerage_discount)
        for r in ordered:
            try:
                with session.begin_nested():  # 每列獨立 savepoint，單列失敗不影響其他
                    _apply_import_row(svc, session, r)
                success += 1
            except Exception as e:
                errors.append(f"{r['date']} {r['ticker']} {r['action']}：{e}")

    return {"success": success, "failed": len(errors), "errors": errors}


def clear_all_data() -> None:
    """清空所有交易與持倉（危險操作）"""
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        session.query(Transaction).delete()
        session.query(Asset).delete()


# ─────────────────────────────────────────────────────────
# 負債（貸款／質借）與現金流
# ─────────────────────────────────────────────────────────
_BUDGET_KEYS = ("living_expense", "rent_tuition")  # 生活費、房租學費（月）


def get_liabilities() -> list[dict]:
    """取得所有負債（以 dict 回傳避免 detached）"""
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        repo = LiabilityRepository(session)
        return [{
            "id": l.id,
            "name": l.name,
            "lender": l.lender,
            "kind": l.kind.value,
            "kind_label": l.kind.label,
            "repay_method": l.repay_method.value,
            "repay_label": l.repay_method.label,
            "balance": l.current_balance,
            "annual_rate": l.annual_rate,
            "monthly_principal": l.monthly_principal_due,
            "monthly_interest": l.monthly_interest,
            "monthly_payment": l.monthly_payment,
            "original_principal": l.original_principal,
            "total_periods": l.total_periods,
            "periods_elapsed": l.periods_elapsed,
            "start_date": l.start_date,
            "maturity_date": l.maturity_date,
            "note": l.note or "",
        } for l in repo.get_all()]


def add_liability(name, lender, kind, annual_rate, repay_method="INTEREST_ONLY",
                  balance=0.0, monthly_principal=0.0,
                  original_principal=0.0, total_periods=0, start_date=None,
                  maturity_date=None, note=None) -> None:
    from src.models.liability import RepayMethod
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        LiabilityRepository(session).create(
            name=name, lender=lender, kind=LiabilityType(kind),
            repay_method=RepayMethod(repay_method),
            annual_rate=annual_rate,
            balance=balance, monthly_principal=monthly_principal,
            original_principal=original_principal, total_periods=total_periods,
            start_date=start_date, maturity_date=maturity_date, note=note,
        )


def update_liability(liability_id, **kwargs) -> None:
    if "kind" in kwargs and kwargs["kind"] is not None:
        kwargs["kind"] = LiabilityType(kwargs["kind"])
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        LiabilityRepository(session).update(liability_id, **kwargs)


def delete_liability(liability_id) -> None:
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        LiabilityRepository(session).delete(liability_id)


def get_debt_summary() -> dict:
    """只讀負債的彙總（不重算持倉），供首頁用既有市值計算淨值"""
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        liabs = LiabilityRepository(session).get_all()
        return {
            "total_debt": sum(l.current_balance for l in liabs),
            "pledge_debt": sum(l.current_balance for l in liabs if l.kind.value == "STOCK_PLEDGE"),
            "monthly_interest": sum(l.monthly_interest for l in liabs),
            "count": len(liabs),
        }


def get_budget() -> dict:
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        repo = SettingRepository(session)
        return {k: repo.get_float(f"budget_{k}", 0.0) for k in _BUDGET_KEYS}


def set_budget(**kwargs) -> None:
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        repo = SettingRepository(session)
        for k, v in kwargs.items():
            if k in _BUDGET_KEYS:
                repo.set(f"budget_{k}", str(float(v)))


def get_trailing_annual_dividend() -> float:
    """近 12 個月實際現金股利合計（供月配息估算）"""
    cutoff = date.today() - timedelta(days=365)
    sf = _get_session_factory()
    with get_db_session(sf) as session:
        repo = TransactionRepository(session)
        txs = repo.get_all()
        return sum(
            t.price * t.quantity for t in txs
            if t.action.value == "DIVIDEND" and t.trade_date >= cutoff
        )


def get_leverage_summary() -> dict:
    """彙總槓桿與現金流指標"""
    summary = get_portfolio_summary(no_price=False, cache_only=True)
    market_value = summary.total_market_value or summary.total_cost_basis or 0.0

    liabs = get_liabilities()
    total_debt = sum(l["balance"] for l in liabs)
    pledge_debt = sum(l["balance"] for l in liabs if l["kind"] == "STOCK_PLEDGE")
    monthly_interest = sum(l["monthly_interest"] for l in liabs)
    monthly_principal = sum(l["monthly_principal"] for l in liabs)

    budget = get_budget()
    annual_div = get_trailing_annual_dividend()
    monthly_div = annual_div / 12.0

    monthly_net = (
        monthly_div - monthly_interest - monthly_principal
        - budget["living_expense"] - budget["rent_tuition"]
    )

    return {
        "market_value": market_value,
        "total_debt": total_debt,
        "pledge_debt": pledge_debt,
        "net_worth": market_value - total_debt,
        "ltv": (pledge_debt / market_value) if market_value else 0.0,
        "monthly_interest": monthly_interest,
        "monthly_principal": monthly_principal,
        "annual_dividend": annual_div,
        "monthly_dividend": monthly_div,
        "living_expense": budget["living_expense"],
        "rent_tuition": budget["rent_tuition"],
        "monthly_net": monthly_net,
    }

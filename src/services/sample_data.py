"""
範例投資組合資料 — 提供可重用的播種邏輯

桌面版首次啟動（DB 為空）會自動灌入，讓使用者下載後即看到示範持倉；
scripts/seed_data.py 亦複用此模組以供開發時手動填充。
"""
from datetime import date

from sqlalchemy.orm import Session

from ..models.enums import AssetType, Exchange
from ..repositories.asset_repo import AssetRepository
from ..services.portfolio_service import PortfolioService
from ..utils.logger import logger

# 範例交易（涵蓋個股 / 股票型 ETF / 債券型 ETF 與買入、股利）
SAMPLE_TRADES = [
    # ── 個股 ──────────────────────────────────────────────
    {
        "action": "buy",
        "ticker": "2330", "name": "台積電",
        "asset_type": AssetType.STOCK, "exchange": Exchange.TWSE,
        "price": 580.0, "quantity": 1000, "date": date(2023, 10, 5),
        "note": "長期持有",
    },
    {
        "action": "buy",
        "ticker": "2330", "name": "台積電",
        "asset_type": AssetType.STOCK, "exchange": Exchange.TWSE,
        "price": 620.0, "quantity": 500, "date": date(2024, 1, 20),
        "note": "加碼",
    },
    {
        "action": "dividend",
        "ticker": "2330",
        "amount_per_share": 11.0, "quantity": 1500, "date": date(2024, 7, 18),
        "note": "113年現金股利",
    },
    {
        "action": "buy",
        "ticker": "2454", "name": "聯發科",
        "asset_type": AssetType.STOCK, "exchange": Exchange.TWSE,
        "price": 1050.0, "quantity": 200, "date": date(2024, 3, 10),
    },
    # ── 股票型 ETF ─────────────────────────────────────────
    {
        "action": "buy",
        "ticker": "0050", "name": "元大台灣50",
        "asset_type": AssetType.STOCK_ETF, "exchange": Exchange.TWSE,
        "price": 168.0, "quantity": 3000, "date": date(2023, 8, 15),
    },
    {
        "action": "buy",
        "ticker": "0050", "name": "元大台灣50",
        "asset_type": AssetType.STOCK_ETF, "exchange": Exchange.TWSE,
        "price": 175.0, "quantity": 2000, "date": date(2024, 2, 20),
    },
    {
        "action": "dividend",
        "ticker": "0050",
        "amount_per_share": 3.4, "quantity": 5000, "date": date(2024, 10, 15),
        "note": "0050 配息",
    },
    {
        "action": "buy",
        "ticker": "006208", "name": "富邦台50",
        "asset_type": AssetType.STOCK_ETF, "exchange": Exchange.TWSE,
        "price": 85.0, "quantity": 5000, "date": date(2024, 4, 1),
    },
    # ── 債券型 ETF ─────────────────────────────────────────
    {
        "action": "buy",
        "ticker": "00679B", "name": "元大美債20年",
        "asset_type": AssetType.BOND_ETF, "exchange": Exchange.TWSE,
        "price": 36.5, "quantity": 10000, "date": date(2023, 11, 1),
    },
    {
        "action": "dividend",
        "ticker": "00679B",
        "amount_per_share": 0.12, "quantity": 10000, "date": date(2024, 6, 15),
        "note": "月配息 6月",
    },
    {
        "action": "buy",
        "ticker": "00720B", "name": "元大投資級公司債",
        "asset_type": AssetType.BOND_ETF, "exchange": Exchange.TWSE,
        "price": 44.2, "quantity": 5000, "date": date(2024, 5, 10),
    },
]


def seed_sample_data(session: Session, brokerage_discount: float = 0.6) -> int:
    """將 SAMPLE_TRADES 寫入指定 session，回傳成功筆數（不負責 commit）"""
    svc = PortfolioService(session, brokerage_discount=brokerage_discount)
    count = 0

    for trade in SAMPLE_TRADES:
        action = trade["action"]
        try:
            if action == "buy":
                svc.buy(
                    ticker=trade["ticker"],
                    name=trade["name"],
                    asset_type=trade["asset_type"],
                    exchange=trade["exchange"],
                    price=trade["price"],
                    quantity=trade["quantity"],
                    trade_date=trade["date"],
                    note=trade.get("note"),
                )
            elif action == "sell":
                svc.sell(
                    ticker=trade["ticker"],
                    price=trade["price"],
                    quantity=trade["quantity"],
                    trade_date=trade["date"],
                    note=trade.get("note"),
                )
            elif action == "dividend":
                svc.add_dividend(
                    ticker=trade["ticker"],
                    dividend_per_share=trade["amount_per_share"],
                    quantity=trade["quantity"],
                    trade_date=trade["date"],
                    note=trade.get("note"),
                )
            count += 1
        except Exception as e:  # noqa: BLE001 — 單筆失敗不應中斷整體播種
            logger.warning(f"範例資料寫入失敗 {trade.get('ticker', '?')}：{e}")

    return count


def seed_if_empty(session: Session, brokerage_discount: float = 0.6) -> int:
    """僅當 DB 尚無任何持倉時才播種，回傳寫入筆數（已存在則回傳 0）"""
    if AssetRepository(session).get_all():
        return 0
    return seed_sample_data(session, brokerage_discount=brokerage_discount)

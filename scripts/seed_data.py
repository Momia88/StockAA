"""
範例資料填充腳本 — 快速建立測試用持倉
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import create_all_tables, get_db_session, get_engine, get_session_factory
from src.models.enums import AssetType, Exchange
from src.services.portfolio_service import PortfolioService
from src.utils.config import get_settings

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


def seed():
    settings = get_settings()
    engine = get_engine(settings.db_path)
    create_all_tables(engine)
    session_factory = get_session_factory(engine)

    with get_db_session(session_factory) as session:
        svc = PortfolioService(session, brokerage_discount=0.6)

        for trade in SAMPLE_TRADES:
            action = trade["action"]
            try:
                if action == "buy":
                    asset, tx = svc.buy(
                        ticker=trade["ticker"],
                        name=trade["name"],
                        asset_type=trade["asset_type"],
                        exchange=trade["exchange"],
                        price=trade["price"],
                        quantity=trade["quantity"],
                        trade_date=trade["date"],
                        note=trade.get("note"),
                    )
                    print(f"  ✅ 買入 {trade['ticker']} {trade['quantity']:,}股 @{trade['price']}")

                elif action == "sell":
                    asset, tx = svc.sell(
                        ticker=trade["ticker"],
                        price=trade["price"],
                        quantity=trade["quantity"],
                        trade_date=trade["date"],
                        note=trade.get("note"),
                    )
                    print(f"  ✅ 賣出 {trade['ticker']} {trade['quantity']:,}股 @{trade['price']}")

                elif action == "dividend":
                    asset, tx = svc.add_dividend(
                        ticker=trade["ticker"],
                        dividend_per_share=trade["amount_per_share"],
                        quantity=trade["quantity"],
                        trade_date=trade["date"],
                        note=trade.get("note"),
                    )
                    total = trade["amount_per_share"] * trade["quantity"]
                    print(f"  ✅ 股利 {trade['ticker']} 共 {total:,.2f} 元")

            except Exception as e:
                print(f"  ❌ 失敗 {trade.get('ticker', '?')}：{e}")

    print()
    print("✅ 範例資料填充完成！")
    print("   執行 'stockaa show portfolio' 查看結果")


if __name__ == "__main__":
    print("=" * 50)
    print("  填充範例投資組合資料...")
    print("=" * 50)
    seed()

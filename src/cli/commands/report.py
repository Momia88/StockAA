"""
CLI 命令：查看報表
"""
from typing import Optional

import typer

from ...models.database import create_all_tables, get_db_session, get_engine, get_session_factory
from ...repositories.asset_repo import AssetRepository
from ...repositories.transaction_repo import TransactionRepository
from ...services.calculation_service import CalculationService
from ...data_providers.price_manager import PriceManager
from ...utils.config import get_settings
from ..display import (
    console,
    print_error,
    print_info,
    print_portfolio_table,
    print_transaction_table,
    print_warning,
    print_rule,
)

app = typer.Typer(help="查看報表")


def _setup():
    settings = get_settings()
    engine = get_engine(settings.db_path)
    create_all_tables(engine)
    return get_session_factory(engine), settings


@app.command("portfolio", help="查看持倉總覽與損益")
def show_portfolio(
    all_assets: bool = typer.Option(
        False, "--all", "-a", help="顯示所有持倉（含已清倉）"
    ),
    no_price: bool = typer.Option(
        False, "--no-price", help="不抓取即時股價（僅顯示成本資訊）"
    ),
):
    """顯示完整投資組合報表"""
    session_factory, settings = _setup()

    with get_db_session(session_factory) as session:
        asset_repo = AssetRepository(session)
        assets = asset_repo.get_all() if all_assets else asset_repo.get_all_active()

        if not assets:
            print_info("投資組合是空的！請使用 [bold]stockaa add buy[/bold] 新增持倉")
            return

        # 取得即時股價
        prices = {}
        if not no_price:
            tickers = [a.ticker for a in assets]
            print_info(f"正在取得 {len(tickers)} 支股票的即時行情...")
            try:
                mgr = PriceManager(timeout=settings.api_timeout, session_factory=session_factory)
                prices = mgr.get_prices_batch(tickers)
                fetched = sum(1 for v in prices.values() if v is not None)
                if fetched < len(tickers):
                    missing = [t for t, v in prices.items() if v is None]
                    print_warning(f"以下股票無法取得即時股價：{', '.join(missing)}")
            except Exception as e:
                print_warning(f"股價抓取失敗：{e}，將以成本資訊顯示")
        else:
            print_info("已跳過即時股價抓取")

        # 建立彙總並顯示
        calc_svc = CalculationService()
        summary = calc_svc.build_portfolio_summary(
            assets=assets,
            prices=prices,
            active_only=not all_assets,
        )

        print_portfolio_table(summary, show_all=all_assets)


@app.command("transactions", help="查看交易記錄")
def show_transactions(
    ticker: Optional[str] = typer.Argument(
        None, help="股票代碼（省略則顯示所有）"
    ),
    limit: int = typer.Option(
        20, "--limit", "-n", help="顯示筆數（預設 20）"
    ),
    start: Optional[str] = typer.Option(
        None, "--start", "-s", help="開始日期 YYYY-MM-DD"
    ),
    end: Optional[str] = typer.Option(
        None, "--end", "-e", help="結束日期 YYYY-MM-DD"
    ),
):
    """顯示交易記錄"""
    from datetime import date as dt
    session_factory, _ = _setup()

    start_date = dt.fromisoformat(start) if start else None
    end_date = dt.fromisoformat(end) if end else None

    with get_db_session(session_factory) as session:
        tx_repo = TransactionRepository(session)

        if ticker:
            txs = tx_repo.get_by_ticker(ticker, limit=limit)
        else:
            txs = tx_repo.get_all(start_date=start_date, end_date=end_date)
            txs = txs[:limit]

        if not txs:
            print_info("無交易記錄")
            return

        print_transaction_table(txs, ticker=ticker or "")


@app.command("price", help="查詢單一股票即時股價")
def show_price(
    ticker: str = typer.Argument(..., help="股票代碼"),
):
    """查詢即時股價"""
    from ...utils.exceptions import PriceFetchError
    session_factory, settings = _setup()
    mgr = PriceManager(timeout=settings.api_timeout, session_factory=session_factory)

    try:
        price_data = mgr.get_price(ticker)
        console.print(f"\n[bold cyan]{price_data.ticker}[/bold cyan] {price_data.name}")
        console.print(f"  收盤價：[bold bright_red]{price_data.close:,.2f}[/bold bright_red] 元")
        if price_data.open:
            console.print(f"  開盤：{price_data.open:,.2f}  最高：{price_data.high:,.2f}  最低：{price_data.low:,.2f}")
        if price_data.volume:
            console.print(f"  成交量：{price_data.volume:,} 股")
        console.print(f"  日期：{price_data.trade_date}  來源：{price_data.source}")
        console.print()
    except PriceFetchError as e:
        print_error(str(e))
        raise typer.Exit(1)


@app.command("holdings", help="顯示各資產類型的持倉比例")
def show_holdings():
    """顯示持倉比例（依類型分類）"""
    from rich.table import Table
    from rich import box

    session_factory, settings = _setup()

    with get_db_session(session_factory) as session:
        asset_repo = AssetRepository(session)
        assets = asset_repo.get_all_active()

        if not assets:
            print_info("目前無持倉")
            return

        # 取得所有股價以計算市值比重
        tickers = [a.ticker for a in assets]
        mgr = PriceManager(timeout=settings.api_timeout, session_factory=session_factory)
        prices = {}
        try:
            prices = mgr.get_prices_batch(tickers)
        except Exception:
            print_warning("無法取得即時股價，改以成本比重計算")

        calc_svc = CalculationService()
        summary = calc_svc.build_portfolio_summary(assets, prices)

        # 按資產類型分組
        by_type: dict[str, list] = {}
        for snap in summary.assets:
            by_type.setdefault(snap.asset_type, []).append(snap)

        total_value = summary.total_market_value or summary.total_cost_basis

        print_rule("持倉配置分析")
        for atype, snaps in by_type.items():
            type_value = sum(
                (s.market_value or s.cost_basis) for s in snaps
            )
            pct = (type_value / total_value * 100) if total_value else 0

            table = Table(
                title=f"[bold]{atype}[/bold]  市值：{type_value:,.0f}元  佔比：{pct:.1f}%",
                box=box.SIMPLE,
                header_style="bold",
            )
            table.add_column("代碼", style="cyan")
            table.add_column("名稱")
            table.add_column("持股數", justify="right")
            table.add_column("成本", justify="right")
            table.add_column("市值", justify="right")
            table.add_column("佔比", justify="right")

            for s in snaps:
                v = s.market_value or s.cost_basis
                ratio = (v / total_value * 100) if total_value else 0
                table.add_row(
                    s.ticker, s.name,
                    f"{s.quantity:,}",
                    f"{s.cost_basis:,.0f}",
                    f"{v:,.0f}",
                    f"{ratio:.1f}%",
                )
            console.print(table)

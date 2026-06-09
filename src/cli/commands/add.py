"""
CLI 命令：新增交易（買入、賣出、股利）
"""
from datetime import date
from typing import Optional

import typer
from ...models.enums import AssetType, Exchange
from ...models.database import get_engine, get_session_factory, create_all_tables, get_db_session
from ...services.portfolio_service import PortfolioService
from ...utils.config import get_settings
from ...utils.exceptions import (
    AssetNotFoundError,
    InsufficientHoldingsError,
    InvalidTransactionError,
)
from ..display import console, print_success, print_error

app = typer.Typer(help="新增交易記錄")


def _get_service() -> tuple:
    """取得 DB session 與 PortfolioService"""
    settings = get_settings()
    engine = get_engine(settings.db_path)
    create_all_tables(engine)
    session_factory = get_session_factory(engine)
    return session_factory, settings.brokerage_discount


@app.command("buy", help="新增買入交易")
def add_buy(
    ticker: str = typer.Argument(..., help="股票代碼（如 2330）"),
    price: float = typer.Option(..., "--price", "-p", help="買入單價（元/股）"),
    quantity: int = typer.Option(..., "--qty", "-q", help="買入股數"),
    trade_date: Optional[str] = typer.Option(
        None, "--date", "-d", help="交易日期 YYYY-MM-DD（預設今天）"
    ),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="股票名稱"),
    asset_type: str = typer.Option(
        "STOCK", "--type", "-t",
        help="資產類型：STOCK / STOCK_ETF / BOND_ETF"
    ),
    exchange: str = typer.Option(
        "TWSE", "--exchange", "-e",
        help="交易所：TWSE（上市）/ TPEx（上櫃）"
    ),
    note: Optional[str] = typer.Option(None, "--note", help="備註"),
    discount: Optional[float] = typer.Option(
        None, "--discount", help="手續費折扣（覆蓋設定值）"
    ),
):
    """新增一筆買入記錄"""
    # 日期處理
    tx_date = _parse_date(trade_date)

    # 驗證枚舉
    try:
        atype = AssetType(asset_type.upper())
        exch = Exchange(exchange.upper())
    except ValueError as e:
        print_error(f"無效的參數：{e}")
        raise typer.Exit(1)

    # 確認操作
    stock_name = name or ticker
    console.print(
        f"\n[bold]確認買入：[/bold] {ticker} {stock_name}  "
        f"[bright_red]{price:.2f}元[/bright_red] × "
        f"[cyan]{quantity:,}股[/cyan]  "
        f"日期：{tx_date}"
    )

    session_factory, disc = _get_service()
    actual_discount = discount if discount is not None else disc

    try:
        with get_db_session(session_factory) as session:
            # 若未提供名稱，嘗試從 API 取得
            if not name:
                stock_name = _fetch_stock_name(ticker) or ticker

            svc = PortfolioService(session, brokerage_discount=actual_discount)
            asset, tx = svc.buy(
                ticker=ticker,
                name=stock_name,
                asset_type=atype,
                exchange=exch,
                price=price,
                quantity=quantity,
                trade_date=tx_date,
                note=note,
            )

        print_success(
            f"買入成功！{ticker} {quantity:,}股 @{price:.2f}  "
            f"手續費：{tx.fee:.0f}元  "
            f"新均成本：{asset.avg_cost:.4f}元  "
            f"總持倉：{asset.quantity:,}股"
        )
    except InvalidTransactionError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"操作失敗：{e}")
        raise typer.Exit(1)


@app.command("sell", help="新增賣出交易")
def add_sell(
    ticker: str = typer.Argument(..., help="股票代碼"),
    price: float = typer.Option(..., "--price", "-p", help="賣出單價（元/股）"),
    quantity: int = typer.Option(..., "--qty", "-q", help="賣出股數"),
    trade_date: Optional[str] = typer.Option(
        None, "--date", "-d", help="交易日期 YYYY-MM-DD"
    ),
    note: Optional[str] = typer.Option(None, "--note", help="備註"),
    discount: Optional[float] = typer.Option(
        None, "--discount", help="手續費折扣"
    ),
):
    """新增一筆賣出記錄"""
    tx_date = _parse_date(trade_date)
    session_factory, disc = _get_service()
    actual_discount = discount if discount is not None else disc

    try:
        with get_db_session(session_factory) as session:
            svc = PortfolioService(session, brokerage_discount=actual_discount)
            asset, tx = svc.sell(
                ticker=ticker,
                price=price,
                quantity=quantity,
                trade_date=tx_date,
                note=note,
            )

        pnl_sign = "+" if tx.realized_pnl >= 0 else ""
        pnl_color = "bright_red" if tx.realized_pnl >= 0 else "bright_green"
        print_success(
            f"賣出成功！{ticker} {quantity:,}股 @{price:.2f}  "
            f"手續費：{tx.fee:.0f}元  稅：{tx.tax:.0f}元  "
            f"已實現損益：[{pnl_color}]{pnl_sign}{tx.realized_pnl:.2f}元[/{pnl_color}]  "
            f"剩餘：{asset.quantity:,}股"
        )
    except (AssetNotFoundError, InsufficientHoldingsError, InvalidTransactionError) as e:
        print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"操作失敗：{e}")
        raise typer.Exit(1)


@app.command("dividend", help="記錄現金股利")
def add_dividend(
    ticker: str = typer.Argument(..., help="股票代碼"),
    amount: float = typer.Option(..., "--amount", "-a", help="每股現金股利（元）"),
    trade_date: Optional[str] = typer.Option(
        None, "--date", "-d", help="發放日期 YYYY-MM-DD"
    ),
    quantity: Optional[int] = typer.Option(
        None, "--qty", "-q",
        help="領息股數（預設使用當前持股數）"
    ),
    note: Optional[str] = typer.Option(None, "--note", help="備註"),
):
    """記錄一筆現金股利"""
    tx_date = _parse_date(trade_date)
    session_factory, _ = _get_service()

    try:
        with get_db_session(session_factory) as session:
            svc = PortfolioService(session)

            # 若未提供股數，使用目前持倉股數
            if quantity is None:
                from ...repositories.asset_repo import AssetRepository
                repo = AssetRepository(session)
                asset_obj = repo.get_by_ticker(ticker)
                if asset_obj is None:
                    print_error(f"找不到 {ticker} 的持倉")
                    raise typer.Exit(1)
                quantity = asset_obj.quantity

            asset, tx = svc.add_dividend(
                ticker=ticker,
                dividend_per_share=amount,
                quantity=quantity,
                trade_date=tx_date,
                note=note,
            )

        total = amount * quantity
        print_success(
            f"股利記錄完成！{ticker} 每股 {amount:.4f}元 × {quantity:,}股 "
            f"= [bright_yellow]{total:.2f}元[/bright_yellow]  "
            f"累計股利：{asset.total_dividend:.2f}元"
        )
    except AssetNotFoundError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"操作失敗：{e}")
        raise typer.Exit(1)


@app.command("split", help="記錄股票分割或合併（反向分割）")
def add_split(
    ticker: str = typer.Argument(..., help="股票代碼"),
    ratio: float = typer.Option(..., "--ratio", "-r", help="分割比例（2.0=2:1分割，0.5=1:2反向合併）"),
    trade_date: Optional[str] = typer.Option(
        None, "--date", "-d", help="分割日期 YYYY-MM-DD"
    ),
    note: Optional[str] = typer.Option(None, "--note", help="備註"),
):
    """記錄股票分割或合併"""
    tx_date = _parse_date(trade_date)
    session_factory, _ = _get_service()

    try:
        with get_db_session(session_factory) as session:
            svc = PortfolioService(session)
            asset, tx = svc.add_split(
                ticker=ticker,
                split_ratio=ratio,
                trade_date=tx_date,
                note=note,
            )

        action = "分割" if ratio >= 1.0 else "反向合併"
        print_success(
            f"股票{action}記錄完成！{ticker} 比例 {ratio}:1  "
            f"新股數：{asset.quantity:,}股  "
            f"新均成本：{asset.avg_cost:.4f}元"
        )
    except (AssetNotFoundError, InvalidTransactionError) as e:
        print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"操作失敗：{e}")
        raise typer.Exit(1)


@app.command("stock-dividend", help="記錄股票股利（無償配股）")
def add_stock_dividend(
    ticker: str = typer.Argument(..., help="股票代碼"),
    shares: int = typer.Option(..., "--shares", "-s", help="配發股數"),
    trade_date: Optional[str] = typer.Option(
        None, "--date", "-d", help="發放日期 YYYY-MM-DD"
    ),
    note: Optional[str] = typer.Option(None, "--note", help="備註"),
):
    """記錄股票股利（增加股數）"""
    tx_date = _parse_date(trade_date)
    session_factory, _ = _get_service()

    try:
        with get_db_session(session_factory) as session:
            svc = PortfolioService(session)
            asset, tx = svc.add_stock_dividend(
                ticker=ticker,
                bonus_shares=shares,
                trade_date=tx_date,
                note=note,
            )

        print_success(
            f"股票股利記錄完成！{ticker} +{shares:,}股  "
            f"新均成本：{asset.avg_cost:.4f}元  "
            f"總持倉：{asset.quantity:,}股"
        )
    except AssetNotFoundError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"操作失敗：{e}")
        raise typer.Exit(1)


# ──────────────────────────────────────────
# 輔助函數
# ──────────────────────────────────────────

def _parse_date(date_str: Optional[str]) -> date:
    """解析日期字串，預設今日"""
    if date_str is None:
        return date.today()
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        print_error(f"日期格式錯誤：{date_str}，請使用 YYYY-MM-DD")
        raise typer.Exit(1)


def _fetch_stock_name(ticker: str) -> Optional[str]:
    """嘗試從 TWSE/TPEx API 取得股票名稱"""
    try:
        from ...data_providers.price_manager import PriceManager
        mgr = PriceManager(timeout=10)
        price = mgr.get_price(ticker)
        return price.name if price else None
    except Exception:
        return None

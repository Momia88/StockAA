"""
CLI 命令：刪除資料（交易記錄、持倉）
"""
import typer
from rich.prompt import Confirm

from ...models.database import create_all_tables, get_db_session, get_engine, get_session_factory
from ...repositories.asset_repo import AssetRepository
from ...repositories.transaction_repo import TransactionRepository
from ...utils.config import get_settings
from ..display import console, print_success, print_error, print_warning, print_info

app = typer.Typer(help="刪除資料（危險操作，請謹慎使用）")


def _setup():
    settings = get_settings()
    engine = get_engine(settings.db_path)
    create_all_tables(engine)
    return get_session_factory(engine)


@app.command("tx", help="刪除一筆交易記錄（不會重算持倉）")
def delete_transaction(
    tx_id: str = typer.Argument(..., help="交易記錄 ID（從 stockaa show transactions 取得）"),
    yes: bool = typer.Option(False, "--yes", "-y", help="跳過確認提示"),
):
    """
    刪除指定的交易記錄。

    ⚠️  警告：刪除後不會自動重算持倉的均成本與股數。
    若需要修正持倉，請刪除後執行 stockaa rebuild <ticker>。
    """
    session_factory = _setup()

    with get_db_session(session_factory) as session:
        tx_repo = TransactionRepository(session)
        tx = tx_repo.get_by_id(tx_id)

        if tx is None:
            print_error(f"找不到 ID 為 {tx_id} 的交易記錄")
            raise typer.Exit(1)

        console.print(
            f"\n[bold yellow]即將刪除以下交易記錄：[/bold yellow]\n"
            f"  ID：[dim]{tx.id}[/dim]\n"
            f"  股票：[cyan]{tx.ticker}[/cyan]  "
            f"動作：[bold]{tx.action.value}[/bold]  "
            f"股數：{tx.quantity:,}  單價：{tx.price:.2f}  "
            f"日期：{tx.trade_date}\n"
        )
        print_warning("此操作不可逆！刪除後持倉數據可能不一致，請使用 stockaa rebuild 重算。")

        if not yes and not Confirm.ask("確定要刪除嗎？"):
            print_info("已取消")
            raise typer.Exit(0)

        tx_repo.delete(tx_id)

    print_success(f"已刪除交易記錄 {tx_id}")


@app.command("asset", help="刪除持倉及其所有交易記錄（危險）")
def delete_asset(
    ticker: str = typer.Argument(..., help="股票代碼"),
    yes: bool = typer.Option(False, "--yes", "-y", help="跳過確認提示"),
):
    """
    完整刪除一支股票的持倉紀錄及所有交易歷史。

    ⚠️  此操作不可逆，所有相關交易記錄也會一併刪除。
    """
    session_factory = _setup()

    with get_db_session(session_factory) as session:
        asset_repo = AssetRepository(session)
        asset = asset_repo.get_by_ticker(ticker)

        if asset is None:
            print_error(f"找不到股票代碼 {ticker} 的持倉")
            raise typer.Exit(1)

        tx_repo = TransactionRepository(session)
        tx_count = len(tx_repo.get_by_ticker(ticker))

        console.print(
            f"\n[bold red]即將刪除以下持倉及其所有交易記錄：[/bold red]\n"
            f"  股票：[cyan]{ticker}[/cyan] {asset.name}  "
            f"持股：{asset.quantity:,}股  交易筆數：{tx_count} 筆\n"
        )
        print_warning("此操作不可逆！所有交易記錄也會一併刪除。")

        if not yes and not Confirm.ask("確定要刪除嗎？"):
            print_info("已取消")
            raise typer.Exit(0)

        asset_repo.delete(ticker)

    print_success(f"已刪除 {ticker} {asset.name} 的所有持倉與交易記錄")

"""
StockAA CLI 主入口
"""
import typer
from rich.console import Console

from .commands import add, report, delete
from ..utils.config import get_settings
from ..utils.logger import setup_logger

console = Console()

# 建立主 App
app = typer.Typer(
    name="stockaa",
    help=(
        "📈 [bold cyan]StockAA[/bold cyan] — 台灣股市投資組合管理工具\n\n"
        "使用 [bold]stockaa COMMAND --help[/bold] 查看各指令說明"
    ),
    rich_markup_mode="rich",
    no_args_is_help=True,
    add_completion=False,
)

# 掛載子命令群組
app.add_typer(add.app, name="add", help="📥 新增交易記錄（買入/賣出/股利）")
app.add_typer(report.app, name="show", help="📊 查看報表與持倉資訊")
app.add_typer(delete.app, name="delete", help="🗑️  刪除交易記錄或持倉（危險）")


@app.callback()
def main_callback(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="顯示詳細日誌"),
):
    """初始化 logger 與設定"""
    settings = get_settings()
    log_level = "DEBUG" if verbose else settings.log_level
    setup_logger(log_level)


@app.command("init", help="🔧 初始化資料庫（首次使用）")
def init_db():
    """建立資料庫結構"""
    from ..models.database import create_all_tables, get_engine
    settings = get_settings()

    try:
        engine = get_engine(settings.db_path)
        create_all_tables(engine)
        console.print(
            f"[bold green]✅ 資料庫初始化完成！[/bold green]\n"
            f"   路徑：[cyan]{settings.resolved_db_path}[/cyan]"
        )
    except Exception as e:
        console.print(f"[bold red]❌ 初始化失敗：{e}[/bold red]")
        raise typer.Exit(1)


@app.command("version", help="顯示版本資訊")
def show_version():
    console.print("[bold cyan]StockAA[/bold cyan] v0.1.0")
    console.print("台灣股市投資組合管理系統")


if __name__ == "__main__":
    app()

"""
CLI Display — 使用 Rich 美化終端機輸出
"""
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule

from ..services.calculation_service import AssetSnapshot, PortfolioSummary

console = Console()


def _pnl_color(value: Optional[float]) -> str:
    """根據損益正負選擇顏色"""
    if value is None:
        return "dim"
    if value > 0:
        return "bright_red"   # 台股習慣：漲紅跌綠
    if value < 0:
        return "bright_green"
    return "white"


def _fmt_money(value: Optional[float], decimals: int = 0) -> str:
    """格式化金額"""
    if value is None:
        return "[dim]N/A[/dim]"
    fmt = f"{value:,.{decimals}f}"
    return fmt


def _fmt_pct(value: Optional[float]) -> str:
    """格式化百分比（含正負號）"""
    if value is None:
        return "[dim]N/A[/dim]"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def print_portfolio_table(summary: PortfolioSummary, show_all: bool = False) -> None:
    """
    印出持倉彙總表格

    Args:
        summary: 投資組合彙總資料
        show_all: 是否顯示已清倉的持股
    """
    table = Table(
        title="📊 投資組合持倉總覽",
        box=box.ROUNDED,
        border_style="bright_blue",
        header_style="bold bright_white on dark_blue",
        show_lines=True,
        expand=True,
    )

    # 欄位定義
    table.add_column("代碼", style="bold cyan", width=8, justify="center")
    table.add_column("名稱", style="white", width=12)
    table.add_column("類型", style="dim", width=8, justify="center")
    table.add_column("交易所", style="dim", width=6, justify="center")
    table.add_column("持股數", justify="right", width=8)
    table.add_column("均成本", justify="right", width=9)
    table.add_column("現價", justify="right", width=9)
    table.add_column("市值", justify="right", width=12)
    table.add_column("未實現損益", justify="right", width=14)
    table.add_column("報酬率", justify="right", width=9)
    table.add_column("股利", justify="right", width=10)

    assets_to_show = summary.assets
    if not show_all:
        assets_to_show = [a for a in summary.assets if a.quantity > 0]

    for a in assets_to_show:
        pnl_color = _pnl_color(a.unrealized_pnl)
        pnl_pct_color = _pnl_color(a.unrealized_pnl_pct)

        stale_mark = " [yellow]⚠[/yellow]" if a.is_price_stale else ""

        table.add_row(
            a.ticker,
            a.name,
            a.asset_type,
            a.exchange,
            f"{a.quantity:,}",
            f"{a.avg_cost:,.2f}",
            f"[{pnl_color}]{_fmt_money(a.current_price, 2)}[/{pnl_color}]{stale_mark}",
            f"[bold]{_fmt_money(a.market_value)}[/bold]",
            f"[{pnl_color}]{_fmt_money(a.unrealized_pnl)}[/{pnl_color}]",
            f"[{pnl_pct_color}]{_fmt_pct(a.unrealized_pnl_pct)}[/{pnl_pct_color}]",
            f"[bright_yellow]{_fmt_money(a.total_dividend)}[/bright_yellow]",
        )

    console.print()
    console.print(table)
    _print_summary_footer(summary)


def _print_summary_footer(summary: PortfolioSummary) -> None:
    """印出底部彙總數字"""
    total_mv = summary.total_market_value
    total_cost = summary.total_cost_basis
    total_upnl = summary.total_unrealized_pnl
    total_rpnl = summary.total_realized_pnl
    total_div = summary.total_dividend
    total_ret_pct = summary.total_return_pct

    pnl_color = _pnl_color(total_upnl)
    ret_color = _pnl_color(total_ret_pct)

    panels = [
        Panel(
            f"[bold white]{_fmt_money(total_cost)}[/bold white] 元",
            title="[dim]總投入成本[/dim]",
            border_style="blue",
            width=22,
        ),
        Panel(
            f"[bold white]{_fmt_money(total_mv)}[/bold white] 元",
            title="[dim]總市值[/dim]",
            border_style="blue",
            width=22,
        ),
        Panel(
            f"[{pnl_color}]{_fmt_money(total_upnl)}[/{pnl_color}] 元",
            title="[dim]未實現損益[/dim]",
            border_style="blue",
            width=22,
        ),
        Panel(
            f"[{_pnl_color(total_rpnl)}]{_fmt_money(total_rpnl)}[/{_pnl_color(total_rpnl)}] 元",
            title="[dim]已實現損益[/dim]",
            border_style="blue",
            width=22,
        ),
        Panel(
            f"[bright_yellow]{_fmt_money(total_div)}[/bright_yellow] 元",
            title="[dim]累計股利[/dim]",
            border_style="yellow",
            width=22,
        ),
        Panel(
            f"[{ret_color}]{_fmt_pct(total_ret_pct)}[/{ret_color}]",
            title="[dim]整體報酬率[/dim]",
            border_style="magenta",
            width=18,
        ),
    ]
    console.print(Columns(panels, equal=False, expand=False))
    console.print()


def print_transaction_table(transactions: list, ticker: str = "") -> None:
    """印出交易記錄表格"""
    title = f"📋 交易記錄{'— ' + ticker if ticker else ''}"
    table = Table(
        title=title,
        box=box.SIMPLE_HEAD,
        border_style="blue",
        header_style="bold bright_white",
        show_lines=False,
    )

    table.add_column("日期", style="dim", width=12)
    table.add_column("代碼", style="cyan", width=8)
    table.add_column("動作", width=8, justify="center")
    table.add_column("單價", justify="right", width=10)
    table.add_column("股數", justify="right", width=8)
    table.add_column("手續費", justify="right", width=8)
    table.add_column("交易稅", justify="right", width=8)
    table.add_column("淨金額", justify="right", width=12)
    table.add_column("已實損益", justify="right", width=12)
    table.add_column("備註", style="dim", width=15)

    action_styles = {
        "BUY": "[bold red]買入[/bold red]",
        "SELL": "[bold green]賣出[/bold green]",
        "DIVIDEND": "[bold yellow]現金股利[/bold yellow]",
        "STOCK_DIVIDEND": "[bold yellow]股票股利[/bold yellow]",
        "SPLIT": "[bold blue]分割/合併[/bold blue]",
    }

    for tx in transactions:
        pnl_color = _pnl_color(tx.realized_pnl if tx.realized_pnl != 0 else None)
        table.add_row(
            str(tx.trade_date),
            tx.ticker,
            action_styles.get(tx.action.value, tx.action.value),
            f"{tx.price:,.2f}",
            f"{tx.quantity:,}",
            f"{tx.fee:,.0f}",
            f"{tx.tax:,.0f}",
            f"{abs(tx.net_amount):,.0f}",
            f"[{pnl_color}]{_fmt_money(tx.realized_pnl if tx.realized_pnl != 0 else None)}[/{pnl_color}]",
            tx.note or "",
        )

    console.print()
    console.print(table)


def print_success(msg: str) -> None:
    console.print(f"[bold green]✅ {msg}[/bold green]")


def print_error(msg: str) -> None:
    console.print(f"[bold red]❌ {msg}[/bold red]")


def print_warning(msg: str) -> None:
    console.print(f"[bold yellow]⚠️  {msg}[/bold yellow]")


def print_info(msg: str) -> None:
    console.print(f"[bold blue]ℹ️  {msg}[/bold blue]")


def print_rule(title: str = "") -> None:
    console.print(Rule(title, style="bright_blue"))

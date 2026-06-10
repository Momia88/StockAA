"""
損益分析頁面
"""
from datetime import date

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st

from src.web.data import get_portfolio_summary, get_transactions


def _stacked_dividend_bar(df, x_field, x_order, x_fmt, title, height=320):
    """繪製依個股堆疊的股利長條圖，分項顯示金額、各長條頂端標註總計。

    df 需含欄位：x_field、ticker（顯示標籤）、金額
    """
    fig = go.Figure()
    totals = {xv: 0.0 for xv in x_order}
    for tk in sorted(df["ticker"].unique()):
        sub = df[df["ticker"] == tk]
        yvals = []
        for xv in x_order:
            v = float(sub[sub[x_field] == xv]["金額"].sum())
            yvals.append(v)
            totals[xv] += v
        fig.add_trace(go.Bar(
            name=tk,
            x=[x_fmt(xv) for xv in x_order], y=yvals,
            text=[f"{v:,.0f}" if v > 0 else "" for v in yvals],
            textposition="inside",
        ))
    fig.update_layout(
        title=title,
        barmode="stack",
        xaxis=dict(type="category"),
        yaxis_title="金額（元）",
        legend=dict(orientation="h", y=-0.2),
        margin=dict(t=40, b=10),
        height=height,
    )
    # 各長條頂端標註總金額
    for xv in x_order:
        if totals[xv] > 0:
            fig.add_annotation(
                x=x_fmt(xv), y=totals[xv],
                text=f"<b>{totals[xv]:,.0f}</b>",
                showarrow=False, yshift=12,
            )
    return fig


def _category(asset_type, ticker: str = "") -> str:
    """資產分類：債券歸「債券」，其餘（個股/股票型 ETF）歸「股票」。

    判定條件（任一成立即為債券）：
      1. 資產類型為 BOND_ETF
      2. 代碼以 B 結尾（台灣債券 ETF 慣例，如 00679B、00937B）——
         可修正當初新增時資產類型選錯的情況。
    """
    val = getattr(asset_type, "value", asset_type)
    if val == "BOND_ETF" or (ticker or "").upper().endswith("B"):
        return "債券"
    return "股票"


def _pnl_stacked_fig(df_sub, title):
    """各持倉損益的分項堆疊長條圖（未實現/已實現/股利）"""
    fig = go.Figure()
    for col, color in (
        ("未實現損益", "#ef5350"),
        ("已實現損益", "#42a5f5"),
        ("累計股利", "#ffca28"),
    ):
        fig.add_trace(go.Bar(name=col, x=df_sub["ticker"], y=df_sub[col], marker_color=color))
    fig.update_layout(
        title=title,
        barmode="relative",
        xaxis=dict(type="category", categoryorder="total descending"),
        yaxis_title="損益（元）",
        legend=dict(orientation="h", y=-0.2),
        margin=dict(t=40, b=10),
        height=400,
    )
    return fig


def _cost_value_fig(df_sub, title):
    """成本 vs 市值的分組長條圖"""
    fig = go.Figure()
    fig.add_trace(go.Bar(name="持有成本", x=df_sub["股票"], y=df_sub["持有成本"], marker_color="#90a4ae"))
    fig.add_trace(go.Bar(name="目前市值", x=df_sub["股票"], y=df_sub["目前市值"], marker_color="#ef5350"))
    fig.update_layout(
        title=title,
        barmode="group",
        xaxis=dict(type="category"),
        yaxis_title="金額（元）",
        legend=dict(orientation="h", y=-0.2),
        margin=dict(t=40, b=40),
        height=350,
    )
    return fig


def _render_stock_bond(df, make_fig, empty_stock="無股票持倉", empty_bond="無債券持倉"):
    """將圖表依股票/債券拆兩欄並排（窄螢幕 Streamlit 會自動上下堆疊）"""
    stock_df = df[df["分類"] == "股票"]
    bond_df = df[df["分類"] == "債券"]
    col_s, col_b = st.columns(2)
    with col_s:
        if not stock_df.empty:
            st.plotly_chart(make_fig(stock_df, "股票"), use_container_width=True)
        else:
            st.info(empty_stock)
    with col_b:
        if not bond_df.empty:
            st.plotly_chart(make_fig(bond_df, "債券"), use_container_width=True)
        else:
            st.info(empty_bond)


def render():
    st.subheader("損益分析")

    with st.spinner("載入資料..."):
        try:
            summary = get_portfolio_summary(no_price=False)
            all_txs = get_transactions(limit=500)
        except Exception as e:
            st.error(f"讀取資料失敗：{e}")
            return

    if not summary.assets:
        st.info("尚無持倉資料")
        return

    # ── 1. 各股票損益長條圖 ─────────────────────
    st.subheader("各持倉損益一覽")

    snap_data = []
    for a in summary.assets:
        if a.quantity > 0:
            snap_data.append({
                "ticker": f"{a.ticker} {a.name}",
                "分類": _category(a.asset_type, a.ticker),
                "未實現損益": a.unrealized_pnl or 0,
                "已實現損益": a.realized_pnl,
                "累計股利": a.total_dividend,
                "總損益": (a.unrealized_pnl or 0) + a.realized_pnl + a.total_dividend,
            })

    if snap_data:
        # 股票與債券金額級距差異大，分開兩張圖（寬螢幕並排、窄螢幕自動上下）
        _render_stock_bond(pd.DataFrame(snap_data), _pnl_stacked_fig)

    st.divider()

    # ── 2. 買入成本 vs 市值 ─────────────────────
    st.subheader("成本 vs 市值比較")

    cost_val_data = []
    for a in summary.assets:
        if a.quantity > 0:
            cost_val_data.append({
                "股票": a.name,
                "分類": _category(a.asset_type, a.ticker),
                "持有成本": a.cost_basis,
                "目前市值": a.market_value or a.cost_basis,
            })

    if cost_val_data:
        _render_stock_bond(pd.DataFrame(cost_val_data), _cost_value_fig)

    st.divider()

    # ── 3. 買賣累積現金流時序圖 ─────────────────
    st.subheader("累積淨投入金額走勢")

    buy_sell_txs = [t for t in all_txs if t.action.value in ("BUY", "SELL")]
    if buy_sell_txs:
        # 以「月」彙總每月淨投入，再累加為累積淨投入
        df_cf = pd.DataFrame([{
            "ym": f"{t.trade_date.year}-{t.trade_date.month:02d}",
            "amount": t.net_amount,  # 正=買入支出，負=賣出收入
        } for t in buy_sell_txs])
        monthly = df_cf.groupby("ym")["amount"].sum().sort_index()
        cum = monthly.cumsum()

        fig_cf = px.area(
            x=cum.index.tolist(), y=cum.values,
            labels={"x": "月份", "y": "累積淨投入（元）"},
            color_discrete_sequence=["#42a5f5"],
        )
        fig_cf.update_layout(
            xaxis=dict(type="category"),
            yaxis_title="累積淨投入（元）",
            margin=dict(t=10, b=10), height=280,
        )
        st.plotly_chart(fig_cf, use_container_width=True)

    # ── 4. 股利收入記錄（依月／年彙總，依個股堆疊）─────────
    div_txs = [t for t in all_txs if t.action.value == "DIVIDEND"]
    if div_txs:
        st.divider()
        st.subheader("股利收入記錄")

        name_map = {a.ticker: a.name for a in summary.assets}
        df_div = pd.DataFrame([{
            "year": t.trade_date.year,
            "month": t.trade_date.month,
            "ticker": f"{t.ticker} {name_map.get(t.ticker, '')}".strip(),
            "金額": t.price * t.quantity,
        } for t in div_txs])

        cur_year = date.today().year
        months = list(range(1, 13))

        # 每月股息可選近三年（預設今年）
        year_opts = [cur_year, cur_year - 1, cur_year - 2]
        sel_year = st.selectbox("每月股息年度", year_opts, index=0,
                                format_func=lambda y: f"{y} 年")
        ty = df_div[df_div["year"] == sel_year]

        # 4a. 每月股息（堆疊；標題由圖內呈現，避免重複）
        if ty.empty:
            st.info(f"{sel_year} 年尚無股利記錄")
        else:
            fig_month = _stacked_dividend_bar(
                ty, "month", months, lambda m: f"{m}月", f"{sel_year} 年每月股息"
            )
            st.plotly_chart(fig_month, use_container_width=True)

        # 4b. 近三年總股息（堆疊）
        years = [cur_year - 2, cur_year - 1, cur_year]
        recent3 = df_div[df_div["year"].isin(years)]
        if recent3.empty:
            st.info("近三年尚無股利記錄")
        else:
            fig_year = _stacked_dividend_bar(
                recent3, "year", years, lambda y: f"{y} 年", "近三年總股息"
            )
            st.plotly_chart(fig_year, use_container_width=True)

        # 4c. 每月股息明細（完整 12 個月、含合計，用 st.table 完整呈現不捲動）
        if not ty.empty:
            st.markdown(f"**{sel_year} 年每月股息明細**")
            pv = ty.pivot_table(index="month", columns="ticker", values="金額",
                                aggfunc="sum", fill_value=0)
            pv = pv.reindex(months, fill_value=0)
            pv["合計"] = pv.sum(axis=1)
            pv.index = [f"{m}月" for m in pv.index]
            st.table(pv.style.format("{:,.0f}"))

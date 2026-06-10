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
                "未實現損益": a.unrealized_pnl or 0,
                "已實現損益": a.realized_pnl,
                "累計股利": a.total_dividend,
                "總損益": (a.unrealized_pnl or 0) + a.realized_pnl + a.total_dividend,
            })

    if snap_data:
        df_snap = pd.DataFrame(snap_data)

        # 單一堆疊長條（直向）：三個分項（未實現/已實現/股利）疊加，總高度即總損益
        fig_total = go.Figure()
        for col, color in (
            ("未實現損益", "#ef5350"),
            ("已實現損益", "#42a5f5"),
            ("累計股利", "#ffca28"),
        ):
            fig_total.add_trace(go.Bar(
                name=col,
                x=df_snap["ticker"], y=df_snap[col],
                marker_color=color,
            ))
        fig_total.update_layout(
            title="綜合總損益排行（分項堆疊）",
            barmode="relative",  # 支援正負值的堆疊
            xaxis=dict(type="category", categoryorder="total descending"),  # 依總損益排序
            yaxis_title="損益（元）",
            legend=dict(orientation="h", y=-0.15),
            margin=dict(t=40, b=10),
            height=400,
        )
        st.plotly_chart(fig_total, use_container_width=True)

    st.divider()

    # ── 2. 買入成本 vs 市值 ─────────────────────
    st.subheader("成本 vs 市值比較")

    cost_val_data = []
    for a in summary.assets:
        if a.quantity > 0:
            cost_val_data.append({
                "股票": a.name,
                "類型": a.asset_type,
                "持有成本": a.cost_basis,
                "目前市值": a.market_value or a.cost_basis,
            })

    if cost_val_data:
        df_cv = pd.DataFrame(cost_val_data)
        fig_cv = go.Figure()
        fig_cv.add_trace(go.Bar(
            name="持有成本",
            x=df_cv["股票"], y=df_cv["持有成本"],
            marker_color="#90a4ae",
        ))
        fig_cv.add_trace(go.Bar(
            name="目前市值",
            x=df_cv["股票"], y=df_cv["目前市值"],
            marker_color="#ef5350",
        ))
        fig_cv.update_layout(
            barmode="group",
            legend=dict(orientation="h"),
            xaxis=dict(type="category"),  # 強制類別軸，避免名稱被當數字座標
            yaxis_title="金額（元）",
            margin=dict(t=10, b=40),
            height=350,
        )
        st.plotly_chart(fig_cv, use_container_width=True)

    st.divider()

    # ── 3. 買賣累積現金流時序圖 ─────────────────
    st.subheader("累積淨投入金額走勢")

    buy_sell_txs = [t for t in all_txs if t.action.value in ("BUY", "SELL")]
    if buy_sell_txs:
        df_cf = pd.DataFrame([{
            "date": t.trade_date,
            "amount": t.net_amount,  # 正=買入支出，負=賣出收入
        } for t in sorted(buy_sell_txs, key=lambda x: x.trade_date)])

        df_cf["累積淨投入"] = df_cf["amount"].cumsum()

        fig_cf = px.area(
            df_cf, x="date", y="累積淨投入",
            labels={"date": "日期", "累積淨投入": "累積淨投入（元）"},
            color_discrete_sequence=["#42a5f5"],
        )
        fig_cf.update_layout(margin=dict(t=10, b=10), height=280)
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

        # 4a. 本年度每月股息（堆疊）
        st.markdown(f"**{cur_year} 年每月股息**")
        ty = df_div[df_div["year"] == cur_year]
        if ty.empty:
            st.info(f"{cur_year} 年尚無股利記錄")
        else:
            months = list(range(1, 13))
            fig_month = _stacked_dividend_bar(
                ty, "month", months, lambda m: f"{m}月", f"{cur_year} 年每月股息"
            )
            st.plotly_chart(fig_month, use_container_width=True)

            # 每月股息列表（個股 × 月份，含合計）
            pv = ty.pivot_table(index="month", columns="ticker", values="金額",
                                aggfunc="sum", fill_value=0)
            pv = pv.reindex(range(1, 13), fill_value=0)
            pv["合計"] = pv.sum(axis=1)
            pv.index = [f"{m}月" for m in pv.index]
            st.dataframe(
                pv.style.format("{:,.0f}"),
                use_container_width=True,
            )

        # 4b. 近三年總股息（堆疊）
        st.markdown("**近三年總股息**")
        years = [cur_year - 2, cur_year - 1, cur_year]
        recent3 = df_div[df_div["year"].isin(years)]
        if recent3.empty:
            st.info("近三年尚無股利記錄")
        else:
            fig_year = _stacked_dividend_bar(
                recent3, "year", years, lambda y: f"{y} 年", "近三年總股息"
            )
            st.plotly_chart(fig_year, use_container_width=True)

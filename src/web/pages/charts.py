"""
損益分析頁面
"""
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st

from src.web.data import get_portfolio_summary, get_transactions


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

        # 單一堆疊長條：三個分項（未實現/已實現/股利）疊加，總長度即總損益
        fig_total = go.Figure()
        for col, color in (
            ("未實現損益", "#ef5350"),
            ("已實現損益", "#42a5f5"),
            ("累計股利", "#ffca28"),
        ):
            fig_total.add_trace(go.Bar(
                name=col, orientation="h",
                y=df_snap["ticker"], x=df_snap[col],
                marker_color=color,
            ))
        fig_total.update_layout(
            title="綜合總損益排行（分項堆疊）",
            barmode="relative",  # 支援正負值的堆疊
            yaxis=dict(categoryorder="total ascending"),  # 依總損益排序
            xaxis_title="損益（元）",
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

    # ── 4. 股利收入長條圖 ───────────────────────
    div_txs = [t for t in all_txs if t.action.value == "DIVIDEND"]
    if div_txs:
        st.divider()
        st.subheader("股利收入記錄")
        df_div = pd.DataFrame([{
            "date": str(t.trade_date),
            "ticker": t.ticker,
            "股利金額": t.price * t.quantity,
        } for t in div_txs])

        fig_div = px.bar(
            df_div, x="date", y="股利金額", color="ticker",
            labels={"date": "日期", "股利金額": "金額（元）", "ticker": "股票"},
            title="歷次股利收入",
        )
        fig_div.update_layout(margin=dict(t=40, b=10), height=300)
        st.plotly_chart(fig_div, use_container_width=True)

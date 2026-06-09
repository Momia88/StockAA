"""
交易記錄頁面
"""
import pandas as pd
import streamlit as st

from src.web.data import get_asset_tickers, get_transactions


ACTION_LABEL = {
    "BUY": "買入", "SELL": "賣出",
    "DIVIDEND": "現金股利", "STOCK_DIVIDEND": "股票股利", "SPLIT": "分割/合併",
}
ACTION_COLOR = {
    "BUY": "🔴", "SELL": "🟢", "DIVIDEND": "🟡",
    "STOCK_DIVIDEND": "🟡", "SPLIT": "🔵",
}


def render():
    st.subheader("交易記錄")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        tickers = ["全部"] + get_asset_tickers()
        selected = st.selectbox("股票", tickers)
    with col2:
        action_filter = st.selectbox(
            "交易類型",
            ["全部", "買入", "賣出", "現金股利", "股票股利", "分割/合併"],
        )
    with col3:
        limit = st.number_input("顯示筆數", min_value=10, max_value=500, value=50, step=10)

    ticker_arg = None if selected == "全部" else selected
    txs = get_transactions(ticker=ticker_arg, limit=int(limit))

    action_map_rev = {v: k for k, v in ACTION_LABEL.items()}
    if action_filter != "全部":
        action_key = action_map_rev.get(action_filter)
        txs = [t for t in txs if t.action.value == action_key]

    if not txs:
        st.info("沒有符合條件的交易記錄")
        return

    st.caption(f"共 {len(txs)} 筆")

    rows = []
    for tx in txs:
        pnl_str = ""
        if tx.action.value == "SELL" and tx.realized_pnl != 0:
            sign = "+" if tx.realized_pnl > 0 else ""
            pnl_str = f"{sign}{tx.realized_pnl:,.2f}"

        rows.append({
            "日期": str(tx.trade_date),
            "代碼": tx.ticker,
            "類型": f"{ACTION_COLOR.get(tx.action.value, '')} {ACTION_LABEL.get(tx.action.value, tx.action.value)}",
            "單價": f"{tx.price:,.2f}",
            "股數": f"{tx.quantity:,}",
            "手續費": f"{tx.fee:,.0f}",
            "交易稅": f"{tx.tax:,.0f}",
            "淨金額": f"{abs(tx.net_amount):,.0f}",
            "已實現損益": pnl_str,
            "備註": tx.note or "",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True, height=500)

    # 統計摘要
    st.divider()
    buy_txs = [t for t in txs if t.action.value == "BUY"]
    sell_txs = [t for t in txs if t.action.value == "SELL"]
    div_txs = [t for t in txs if t.action.value == "DIVIDEND"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("買入筆數", len(buy_txs))
    c2.metric("賣出筆數", len(sell_txs))
    total_pnl = sum(t.realized_pnl for t in sell_txs)
    c3.metric("已實現損益合計", f"{'+' if total_pnl >= 0 else ''}{total_pnl:,.0f} 元")
    total_div = sum(t.price * t.quantity for t in div_txs)
    c4.metric("現金股利合計", f"{total_div:,.0f} 元")

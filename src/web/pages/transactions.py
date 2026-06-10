"""
交易記錄頁面
"""
import math

import pandas as pd
import streamlit as st

from src.web.data import (
    do_delete_transaction, do_edit_transaction, do_edit_split,
    get_asset_tickers, get_transaction_detail, get_transactions,
    get_transactions_dataframe_rows,
)

ACTION_LABEL = {
    "BUY": "買入", "SELL": "賣出",
    "DIVIDEND": "現金股利", "STOCK_DIVIDEND": "股票股利", "SPLIT": "分割/合併",
}
ACTION_COLOR = {
    "BUY": "🔴", "SELL": "🟢", "DIVIDEND": "🟡",
    "STOCK_DIVIDEND": "🟡", "SPLIT": "🔵",
}


def _clear_selection():
    for key in ("_sel_tx_id", "_tx_mode", "_tbl_ver"):
        st.session_state.pop(key, None)
    st.session_state["_tbl_ver"] = st.session_state.get("_tbl_ver", 0) + 1


def render():
    st.subheader("交易記錄")

    # ── 篩選列 ────────────────────────────────────
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
        page_size = st.selectbox("每頁筆數", [10, 15, 30, 50], index=0)

    ticker_arg = None if selected == "全部" else selected
    all_txs = get_transactions(ticker=ticker_arg, limit=500)

    action_map_rev = {v: k for k, v in ACTION_LABEL.items()}
    if action_filter != "全部":
        action_key = action_map_rev.get(action_filter)
        all_txs = [t for t in all_txs if t.action.value == action_key]

    if not all_txs:
        st.info("沒有符合條件的交易記錄")
        return

    # ── 分頁 ──────────────────────────────────────
    total = len(all_txs)
    total_pages = max(1, math.ceil(total / page_size))

    cap_col, page_col, dl_col = st.columns([3, 2, 1])
    cap_col.caption(f"共 {total} 筆｜點選一列可修改或刪除")
    with page_col:
        page = st.number_input(
            f"頁次（共 {total_pages} 頁）",
            min_value=1, max_value=total_pages, value=1, step=1,
        )
    with dl_col:
        csv_rows = get_transactions_dataframe_rows(ticker=ticker_arg, limit=500)
        csv_bytes = pd.DataFrame(csv_rows).to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 匯出 CSV",
            data=csv_bytes,
            file_name="stockaa_transactions.csv",
            mime="text/csv",
            use_container_width=True,
        )

    start = (int(page) - 1) * page_size
    page_txs = all_txs[start:start + page_size]

    # ── 交易列表（可選取） ────────────────────────
    tx_ids = [tx.id for tx in page_txs]

    rows = []
    for tx in page_txs:
        pnl_str = ""
        if tx.action.value == "SELL" and tx.realized_pnl != 0:
            sign = "+" if tx.realized_pnl > 0 else ""
            pnl_str = f"{sign}{tx.realized_pnl:,.2f}"
        rows.append({
            "日期":       str(tx.trade_date),
            "代碼":       tx.ticker,
            "類型":       f"{ACTION_COLOR.get(tx.action.value, '')} {ACTION_LABEL.get(tx.action.value, tx.action.value)}",
            "單價":       f"{tx.price:,.2f}",
            "股數":       f"{tx.quantity:,}",
            "手續費":     f"{tx.fee:,.0f}",
            "交易稅":     f"{tx.tax:,.0f}",
            "淨金額":     f"{abs(tx.net_amount):,.0f}",
            "已實現損益": pnl_str,
            "備註":       tx.note or "",
        })

    df = pd.DataFrame(rows)
    tbl_key = f"tx_tbl_{st.session_state.get('_tbl_ver', 0)}"

    # 高度依當頁筆數動態調整，剛好容納全部列、不出現捲軸
    table_height = (len(page_txs) + 1) * 35 + 3

    event = st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=table_height,
        on_select="rerun",
        selection_mode="single-row",
        key=tbl_key,
    )

    # ── 選取後的操作面板 ──────────────────────────
    # 用 getattr 避免舊版 Streamlit 型別存根不包含 selection 屬性
    _sel_obj = getattr(event, "selection", None)
    sel = getattr(_sel_obj, "rows", []) if _sel_obj else []
    if sel:
        idx = sel[0]
        if idx < len(tx_ids):
            st.session_state["_sel_tx_id"] = tx_ids[idx]

    sel_id = st.session_state.get("_sel_tx_id")
    mode = st.session_state.get("_tx_mode", "idle")

    if sel_id:
        tx_data = get_transaction_detail(sel_id)
        if tx_data is None:
            _clear_selection()
            st.rerun()

        st.divider()
        action_label = ACTION_LABEL.get(tx_data["action"], tx_data["action"])
        st.markdown(
            f"**選取：** {tx_data['trade_date']} &nbsp; "
            f"`{tx_data['ticker']}` &nbsp; {action_label} &nbsp; "
            f"{tx_data['quantity']:,} 股 @ {tx_data['price']:,.2f} 元"
        )

        if mode == "idle":
            c1, c2, c3 = st.columns([1, 1, 8])
            with c1:
                if st.button("✏️ 修改", use_container_width=True):
                    st.session_state["_tx_mode"] = "editing"
                    st.rerun()
            with c2:
                if st.button("🗑 刪除", use_container_width=True, type="secondary"):
                    st.session_state["_tx_mode"] = "confirm_delete"
                    st.rerun()

        elif mode == "confirm_delete":
            st.warning(
                f"確定刪除此交易？系統將重新計算 **{tx_data['ticker']}** 的持倉。"
            )
            c1, c2, _ = st.columns([1, 1, 8])
            with c1:
                if st.button("確定刪除", type="primary", use_container_width=True):
                    try:
                        ticker = do_delete_transaction(sel_id)
                        st.success(f"已刪除並重算 {ticker} 持倉")
                        _clear_selection()
                        st.rerun()
                    except Exception as e:
                        st.error(f"刪除失敗：{e}")
            with c2:
                if st.button("取消", use_container_width=True):
                    st.session_state["_tx_mode"] = "idle"
                    st.rerun()

        elif mode == "editing":
            _render_edit_form(sel_id, tx_data)

    # ── 統計摘要 ──────────────────────────────────
    st.divider()
    buy_txs  = [t for t in all_txs if t.action.value == "BUY"]
    sell_txs = [t for t in all_txs if t.action.value == "SELL"]
    div_txs  = [t for t in all_txs if t.action.value == "DIVIDEND"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("買入筆數", len(buy_txs))
    c2.metric("賣出筆數", len(sell_txs))
    total_pnl = sum(t.realized_pnl for t in sell_txs)
    c3.metric("已實現損益合計", f"{'+' if total_pnl >= 0 else ''}{total_pnl:,.0f} 元")
    total_div = sum(t.price * t.quantity for t in div_txs)
    c4.metric("現金股利合計", f"{total_div:,.0f} 元")


def _render_edit_form(tx_id: str, tx: dict):
    """依交易類型顯示對應的修改表單"""
    action = tx["action"]

    with st.container(border=True):
        st.markdown(f"**修改交易** — `{tx['ticker']}` {ACTION_LABEL.get(action, action)}")

        if action == "SPLIT":
            # SPLIT 需要 ratio 而非 price/qty，特殊處理
            with st.form("edit_split_form"):
                trade_date = st.date_input("日期", value=tx["trade_date"])
                # 估算舊有 ratio hint（share_delta / (qty - delta)），僅作參考
                ratio_hint = 2.0
                ratio = st.number_input(
                    "分割比例", min_value=0.01, step=0.5, value=ratio_hint, format="%.2f",
                    help="2.0 = 2:1 分割｜0.5 = 1:2 合併",
                )
                note = st.text_input("備註", value=tx["note"])
                submitted = st.form_submit_button("✅ 儲存修改", type="primary", use_container_width=True)

            if submitted:
                try:
                    do_edit_split(tx_id, ratio, trade_date, note)
                    st.success("分割交易已修改並重算持倉")
                    _clear_selection()
                    st.rerun()
                except Exception as e:
                    st.error(f"修改失敗：{e}")
            return

        # BUY / SELL / DIVIDEND / STOCK_DIVIDEND
        with st.form("edit_tx_form"):
            c1, c2 = st.columns(2)
            trade_date = c1.date_input("日期", value=tx["trade_date"])

            if action in ("BUY", "SELL"):
                price = c1.number_input(
                    "單價（元/股）", min_value=0.01, step=0.01,
                    value=float(tx["price"]), format="%.2f",
                )
                quantity = c2.number_input(
                    "股數", min_value=1, step=1, value=int(tx["quantity"]),
                )
            elif action == "DIVIDEND":
                price = c1.number_input(
                    "每股股利（元）", min_value=0.0001, step=0.01,
                    value=float(tx["price"]), format="%.4f",
                )
                quantity = c2.number_input(
                    "領息股數", min_value=1, step=1, value=int(tx["quantity"]),
                )
            else:  # STOCK_DIVIDEND
                price = 0.0
                quantity = c2.number_input(
                    "配股股數", min_value=1, step=1, value=int(tx["quantity"]),
                )

            note = st.text_input("備註", value=tx["note"])
            submitted = st.form_submit_button("✅ 儲存修改", type="primary", use_container_width=True)

        if submitted:
            try:
                do_edit_transaction(
                    tx_id,
                    price=price if action != "STOCK_DIVIDEND" else 0.0,
                    quantity=quantity,
                    trade_date=trade_date,
                    note=note,
                )
                st.success("交易已修改並重算持倉")
                _clear_selection()
                st.rerun()
            except Exception as e:
                st.error(f"修改失敗：{e}")

    c_cancel, _ = st.columns([1, 9])
    with c_cancel:
        if st.button("取消", use_container_width=True):
            st.session_state["_tx_mode"] = "idle"
            st.rerun()

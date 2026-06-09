"""
新增交易頁面
"""
from datetime import date

import streamlit as st

from src.utils.exceptions import (
    AssetNotFoundError, InsufficientHoldingsError, InvalidTransactionError
)
from src.web.data import (
    do_buy, do_sell, do_dividend, do_split,
    get_asset_tickers, get_recent_assets, get_last_trade_date,
)

_TYPE_LABEL = {"STOCK": "個股", "STOCK_ETF": "股票ETF", "BOND_ETF": "債券ETF"}


def _prefill_buy(asset: dict):
    """快速按鈕 callback：將常用股票帶入買入表單"""
    st.session_state["buy_ticker"] = asset["ticker"]
    st.session_state["buy_name"] = asset["name"]
    st.session_state["buy_type"] = asset["asset_type"]
    st.session_state["buy_exchange"] = asset["exchange"]


def render():
    st.subheader("新增交易")

    tab_buy, tab_sell, tab_div, tab_split = st.tabs(["買入", "賣出", "現金股利", "股票分割"])

    default_date = get_last_trade_date() or date.today()

    # ── 買入 ──────────────────────────────────
    with tab_buy:
        st.subheader("📥 買入股票")

        # 常用股票快速帶入
        recent = get_recent_assets(limit=6)
        if recent:
            st.caption("常用股票（點擊快速帶入）")
            cols = st.columns(len(recent))
            for col, a in zip(cols, recent):
                col.button(
                    f"{a['ticker']} {a['name']}",
                    key=f"recent_{a['ticker']}",
                    use_container_width=True,
                    on_click=_prefill_buy,
                    args=(a,),
                )

        with st.form("buy_form"):
            c1, c2 = st.columns(2)
            ticker = c1.text_input("股票代碼 *", placeholder="如：2330、0050、00679B", key="buy_ticker")
            name = c2.text_input("股票名稱 *", placeholder="如：台積電", key="buy_name")

            c3, c4 = st.columns(2)
            asset_type = c3.selectbox("資產類型", ["STOCK", "STOCK_ETF", "BOND_ETF"],
                                       format_func=lambda x: _TYPE_LABEL[x], key="buy_type")
            exchange = c4.selectbox("交易所", ["TWSE", "TPEx"],
                                     format_func=lambda x: {"TWSE": "上市（TWSE）", "TPEx": "上櫃（TPEx）"}[x],
                                     key="buy_exchange")

            c5, c6, c7 = st.columns(3)
            price = c5.number_input("買入單價（元/股）*", min_value=0.01, step=0.01, format="%.2f")
            quantity = c6.number_input("股數 *", min_value=1, step=1)
            trade_date = c7.date_input("交易日期", value=default_date)

            note = st.text_input("備註（選填）")

            submitted = st.form_submit_button("✅ 確認買入", use_container_width=True, type="primary")

        if submitted:
            if not ticker or not name:
                st.error("請填寫股票代碼與名稱")
            elif price <= 0 or quantity <= 0:
                st.error("單價與股數必須大於 0")
            else:
                try:
                    avg_cost, new_qty, fee = do_buy(
                        ticker.strip(), name.strip(), asset_type, exchange,
                        price, int(quantity), trade_date, note or None
                    )
                    st.success(
                        f"買入成功！**{ticker}** {int(quantity):,} 股 @ {price:.2f} 元  "
                        f"｜ 手續費：{fee:.0f} 元  "
                        f"｜ 新均成本：{avg_cost:.4f} 元  "
                        f"｜ 總持股：{new_qty:,} 股"
                    )
                    st.balloons()
                except InvalidTransactionError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"操作失敗：{e}")

    # ── 賣出 ──────────────────────────────────
    with tab_sell:
        st.subheader("📤 賣出股票")
        tickers = get_asset_tickers()

        with st.form("sell_form"):
            c1, c2 = st.columns(2)
            ticker_sell = c1.selectbox("股票代碼 *", tickers if tickers else ["（無持倉）"])
            trade_date_sell = c2.date_input("交易日期", value=default_date, key="sell_date")

            c3, c4 = st.columns(2)
            price_sell = c3.number_input("賣出單價（元/股）*", min_value=0.01, step=0.01, format="%.2f", key="sell_price")
            qty_sell = c4.number_input("股數 *", min_value=1, step=1, key="sell_qty")

            note_sell = st.text_input("備註（選填）", key="sell_note")
            submitted_sell = st.form_submit_button("✅ 確認賣出", use_container_width=True, type="primary")

        if submitted_sell:
            if not tickers:
                st.error("目前無持倉可賣出")
            else:
                try:
                    pnl, fee, tax, remain = do_sell(
                        ticker_sell, price_sell, int(qty_sell),
                        trade_date_sell, note_sell or None
                    )
                    pnl_emoji = "🔴" if pnl >= 0 else "🟢"
                    st.success(
                        f"賣出成功！**{ticker_sell}** {int(qty_sell):,} 股 @ {price_sell:.2f} 元  \n"
                        f"手續費：{fee:.0f} 元 ｜ 交易稅：{tax:.0f} 元  \n"
                        f"已實現損益：{pnl_emoji} **{'+' if pnl >= 0 else ''}{pnl:,.2f} 元**  \n"
                        f"剩餘持股：{remain:,} 股"
                    )
                except AssetNotFoundError as e:
                    st.error(str(e))
                except InsufficientHoldingsError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"操作失敗：{e}")

    # ── 現金股利 ──────────────────────────────
    with tab_div:
        st.subheader("💰 記錄現金股利")
        tickers_div = get_asset_tickers()

        with st.form("div_form"):
            c1, c2 = st.columns(2)
            ticker_div = c1.selectbox("股票代碼 *", tickers_div if tickers_div else ["（無持倉）"])
            trade_date_div = c2.date_input("發放日期", value=default_date, key="div_date")

            c3, c4 = st.columns(2)
            dps = c3.number_input("每股股利（元）*", min_value=0.0001, step=0.01, format="%.4f")
            custom_qty = c4.checkbox("自訂領息股數")
            qty_div = None
            if custom_qty:
                qty_div = st.number_input("領息股數", min_value=1, step=1)

            note_div = st.text_input("備註（選填）", key="div_note")
            submitted_div = st.form_submit_button("✅ 確認記錄", use_container_width=True, type="primary")

        if submitted_div:
            if not tickers_div:
                st.error("目前無持倉")
            else:
                try:
                    total = do_dividend(
                        ticker_div, dps, trade_date_div,
                        int(qty_div) if qty_div else None,
                        note_div or None
                    )
                    st.success(f"股利記錄完成！**{ticker_div}** 每股 {dps:.4f} 元，共 **{total:,.2f} 元**")
                except AssetNotFoundError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"操作失敗：{e}")

    # ── 股票分割 ──────────────────────────────
    with tab_split:
        st.subheader("✂️ 股票分割 / 合併")
        tickers_sp = get_asset_tickers()

        with st.form("split_form"):
            c1, c2 = st.columns(2)
            ticker_sp = c1.selectbox("股票代碼 *", tickers_sp if tickers_sp else ["（無持倉）"])
            trade_date_sp = c2.date_input("分割日期", value=default_date, key="split_date")

            ratio = st.number_input(
                "分割比例 *",
                min_value=0.01, step=0.5, value=2.0, format="%.2f",
                help="2.0 = 2:1 分割（股數加倍）｜0.5 = 1:2 合併（股數減半）"
            )
            note_sp = st.text_input("備註（選填）", key="split_note")
            submitted_sp = st.form_submit_button("✅ 確認記錄", use_container_width=True, type="primary")

        if submitted_sp:
            if not tickers_sp:
                st.error("目前無持倉")
            else:
                try:
                    new_qty, new_avg = do_split(
                        ticker_sp, ratio, trade_date_sp, note_sp or None
                    )
                    action = "分割" if ratio >= 1 else "合併"
                    st.success(
                        f"股票{action}完成！**{ticker_sp}** 比例 {ratio}:1  \n"
                        f"新股數：{new_qty:,} 股 ｜ 新均成本：{new_avg:.4f} 元"
                    )
                except (AssetNotFoundError, InvalidTransactionError) as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"操作失敗：{e}")

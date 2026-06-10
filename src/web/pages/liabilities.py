"""
資產負債 / 槓桿頁面 — 貸款質借、資產淨值、質借比與月現金流
"""
import pandas as pd
import streamlit as st

from src.web.data import (
    add_liability, delete_liability, get_budget, get_leverage_summary,
    get_liabilities, set_budget,
)

_KIND_OPTIONS = ["STOCK_PLEDGE", "CREDIT", "MARGIN", "OTHER"]
_KIND_LABEL = {"STOCK_PLEDGE": "股票質借", "CREDIT": "信貸", "MARGIN": "融資", "OTHER": "其他"}


def _money(v):
    return f"{v:,.0f}"


def render():
    st.subheader("資產負債 / 槓桿")

    s = get_leverage_summary()

    # ── 概覽指標 ──────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("資產淨值", f"{_money(s['net_worth'])} 元",
              help="總持倉市值 − 總負債")
    c2.metric("總持倉市值", f"{_money(s['market_value'])} 元")
    c3.metric("總負債", f"{_money(s['total_debt'])} 元")
    c4.metric("質借比", f"{s['ltv'] * 100:.1f} %",
              help="股票質借總額 ÷ 總持倉市值")

    # ── 月現金流 ──────────────────────────────────
    st.markdown("#### 月現金流")
    net = s["monthly_net"]
    cashflow_rows = [
        ("➕ 月配息（近 12 月估）", s["monthly_dividend"]),
        ("➖ 月貸款利息", -s["monthly_interest"]),
        ("➖ 月還本金", -s["monthly_principal"]),
        ("➖ 生活費", -s["living_expense"]),
        ("➖ 房租學費", -s["rent_tuition"]),
        ("＝ 月淨現金流", net),
    ]
    cf_cols = st.columns(len(cashflow_rows))
    for col, (label, val) in zip(cf_cols, cashflow_rows):
        col.metric(label, f"{val:,.0f}")
    if net >= 0:
        st.success(f"月淨現金流 **+{net:,.0f} 元**：配息足以覆蓋利息與支出。")
    else:
        st.warning(f"月淨現金流 **{net:,.0f} 元**：配息不足以覆蓋利息與支出，需自備差額。")

    st.divider()

    # ── 預算設定 ──────────────────────────────────
    with st.expander("⚙️ 現金流預算設定（生活費 / 房租學費）"):
        b = get_budget()
        with st.form("budget_form"):
            bc1, bc2 = st.columns(2)
            living = bc1.number_input("生活費（月）", min_value=0.0, step=1000.0,
                                      value=float(b["living_expense"]), format="%.0f")
            rent = bc2.number_input("房租學費（月）", min_value=0.0, step=1000.0,
                                    value=float(b["rent_tuition"]), format="%.0f")
            if st.form_submit_button("儲存預算", type="primary"):
                set_budget(living_expense=living, rent_tuition=rent)
                st.success("已儲存")
                st.rerun()

    st.divider()

    # ── 新增負債 ──────────────────────────────────
    st.markdown("#### 新增貸款 / 質借")
    with st.container(border=True):
        a1, a2, a3 = st.columns([2, 2, 2])
        name = a1.text_input("名稱／標的 *", placeholder="如 679B(35)(竹)、信貸", key="liab_name")
        lender = a2.text_input("機構／帳戶 *", placeholder="如 元大證金、永豐、信貸銀行", key="liab_lender")
        kind = a3.selectbox("類型", _KIND_OPTIONS, format_func=lambda k: _KIND_LABEL[k], key="liab_kind")

        a4, a5, a6 = st.columns(3)
        balance = a4.number_input("貸款餘額 *", min_value=0.0, step=10000.0, format="%.0f", key="liab_bal")
        rate_pct = a5.number_input("年利率（%）*", min_value=0.0, step=0.01, format="%.3f", key="liab_rate")
        mprin = a6.number_input("每月還本金", min_value=0.0, step=1000.0, format="%.0f", key="liab_mprin")

        a7, a8 = st.columns([1, 3])
        maturity = a7.date_input("到期日（選填）", value=None, key="liab_mat")
        note = a8.text_input("備註（選填）", key="liab_note")

        if st.button("✅ 新增", type="primary", key="liab_add"):
            if not name or not lender:
                st.error("請填寫名稱與機構")
            elif balance <= 0:
                st.error("貸款餘額必須大於 0")
            else:
                add_liability(
                    name=name.strip(), lender=lender.strip(), kind=kind,
                    balance=balance, annual_rate=rate_pct / 100.0,
                    monthly_principal=mprin, maturity_date=maturity, note=note or None,
                )
                st.success("已新增")
                st.rerun()

    st.divider()

    # ── 負債明細（依機構彙總） ────────────────────
    st.markdown("#### 負債明細")
    liabs = get_liabilities()
    if not liabs:
        st.info("尚無負債記錄")
        return

    # 依機構小計
    by_lender: dict[str, dict] = {}
    for l in liabs:
        g = by_lender.setdefault(l["lender"], {"balance": 0.0, "interest": 0.0})
        g["balance"] += l["balance"]
        g["interest"] += l["monthly_interest"]
    sub_rows = [{
        "機構": k,
        "餘額": _money(v["balance"]),
        "月利息": _money(v["interest"]),
        "加權年利率": f"{(v['interest'] * 12 / v['balance'] * 100) if v['balance'] else 0:.3f}%",
    } for k, v in by_lender.items()]
    st.caption("依機構彙總")
    st.table(pd.DataFrame(sub_rows))

    # 逐筆明細 + 刪除
    st.caption("逐筆明細")
    df = pd.DataFrame([{
        "名稱": l["name"],
        "機構": l["lender"],
        "類型": l["kind_label"],
        "餘額": _money(l["balance"]),
        "年利率": f"{l['annual_rate'] * 100:.3f}%",
        "月利息": _money(l["monthly_interest"]),
        "月還本金": _money(l["monthly_principal"]),
        "到期日": str(l["maturity_date"]) if l["maturity_date"] else "—",
        "備註": l["note"],
    } for l in liabs])
    st.dataframe(df, use_container_width=True, hide_index=True,
                 height=(len(liabs) + 1) * 35 + 3)

    # 刪除
    with st.expander("🗑 刪除單筆負債"):
        opt = {f"{l['lender']}｜{l['name']}｜{_money(l['balance'])}": l["id"] for l in liabs}
        sel = st.selectbox("選擇要刪除的項目", list(opt.keys()))
        if st.button("確定刪除", type="secondary"):
            delete_liability(opt[sel])
            st.success("已刪除")
            st.rerun()

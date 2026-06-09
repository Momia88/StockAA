"""
持倉總覽頁面
"""
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.web.data import get_portfolio_summary


def _color(val):
    if val is None:
        return "gray"
    return "#d32f2f" if val >= 0 else "#388e3c"


def _fmt(val, decimals=0, prefix="", suffix=""):
    if val is None:
        return "—"
    return f"{prefix}{val:,.{decimals}f}{suffix}"


def _pnl_str(val, decimals=0):
    if val is None:
        return "—"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:,.{decimals}f}"


def render():
    st.title("🏠 持倉總覽")

    col_refresh, col_noprice = st.columns([6, 1])
    with col_noprice:
        no_price = st.toggle("略過股價", value=False)
    with col_refresh:
        if st.button("🔄 更新行情", use_container_width=False):
            st.cache_resource.clear()
            st.rerun()

    with st.spinner("載入投資組合資料..."):
        try:
            summary = get_portfolio_summary(no_price=no_price)
        except Exception as e:
            st.error(f"讀取資料失敗：{e}")
            return

    if not summary.assets:
        st.info("投資組合是空的！請至「新增交易」頁面加入第一筆持倉。")
        return

    # ── 關鍵指標卡片 ───────────────────────────
    st.subheader("📊 投資組合概覽")
    c1, c2, c3, c4, c5 = st.columns(5)

    total_cost = summary.total_cost_basis
    total_mv = summary.total_market_value
    upnl = summary.total_unrealized_pnl
    rpnl = summary.total_realized_pnl
    div = summary.total_dividend
    ret_pct = summary.total_return_pct

    c1.metric("總投入成本", f"{_fmt(total_cost)} 元")
    c2.metric("總市值", f"{_fmt(total_mv)} 元",
              delta=_pnl_str(upnl) + " 元" if upnl else None,
              delta_color="normal" if (upnl or 0) >= 0 else "inverse")
    c3.metric("未實現損益", f"{_pnl_str(upnl)} 元")
    c4.metric("已實現損益", f"{_pnl_str(rpnl)} 元")
    c5.metric("整體報酬率", f"{_pnl_str(ret_pct, 2)} %" if ret_pct else "—")

    st.divider()

    # ── 圓餅圖 + 持倉列表 ──────────────────────
    col_pie, col_table = st.columns([2, 3])

    with col_pie:
        st.subheader("持倉配置")
        labels, values, colors_map = [], [], []
        color_set = {
            "個股": "#ef5350", "股票ETF": "#42a5f5", "債券ETF": "#66bb6a"
        }
        for a in summary.assets:
            if a.quantity > 0:
                labels.append(f"{a.ticker}\n{a.name}")
                val = a.market_value if a.market_value else a.cost_basis
                values.append(val)
                colors_map.append(color_set.get(a.asset_type, "#bdbdbd"))

        if values:
            fig = go.Figure(go.Pie(
                labels=labels,
                values=values,
                hole=0.45,
                marker=dict(colors=colors_map),
                textinfo="label+percent",
                hovertemplate="%{label}<br>市值：%{value:,.0f} 元<br>占比：%{percent}<extra></extra>",
            ))
            fig.update_layout(
                showlegend=False,
                margin=dict(t=10, b=10, l=10, r=10),
                height=320,
            )
            st.plotly_chart(fig, use_container_width=True)

            # 依類型小計
            by_type: dict[str, float] = {}
            for a in summary.assets:
                if a.quantity > 0:
                    v = a.market_value if a.market_value else a.cost_basis
                    by_type[a.asset_type] = by_type.get(a.asset_type, 0) + v
            total_v = sum(by_type.values()) or 1
            for atype, v in by_type.items():
                st.write(f"**{atype}** {v/total_v*100:.1f}%  {v:,.0f} 元")

    with col_table:
        st.subheader("持倉明細")
        import pandas as pd

        rows = []
        for a in summary.assets:
            if a.quantity == 0:
                continue
            pnl_color = "🔴" if (a.unrealized_pnl or 0) >= 0 else "🟢"
            rows.append({
                "代碼": a.ticker,
                "名稱": a.name,
                "類型": a.asset_type,
                "股數": f"{a.quantity:,}",
                "均成本": f"{a.avg_cost:,.2f}",
                "現價": f"{a.current_price:,.2f}" if a.current_price else "—",
                "市值": f"{a.market_value:,.0f}" if a.market_value else "—",
                "未實現損益": f"{pnl_color} {_pnl_str(a.unrealized_pnl)}",
                "報酬率": f"{_pnl_str(a.unrealized_pnl_pct, 2)}%" if a.unrealized_pnl_pct else "—",
                "股利": f"{a.total_dividend:,.0f}",
            })

        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True, height=350)

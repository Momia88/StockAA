"""
持倉總覽頁面
"""
import plotly.graph_objects as go
import streamlit as st

from src.web.data import get_portfolio_summary


def _fmt(val, decimals=0):
    if val is None:
        return "—"
    return f"{val:,.{decimals}f}"


def _pnl_str(val, decimals=0):
    if val is None:
        return "—"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:,.{decimals}f}"


def render():
    # ── 操作列 ────────────────────────────────────
    col_btn, col_space, col_toggle = st.columns([2, 7, 2])
    with col_btn:
        if st.button("🔄 更新行情", use_container_width=True):
            st.cache_resource.clear()
            st.rerun()
    with col_toggle:
        no_price = st.toggle("略過股價", value=False)

    with st.spinner("載入投資組合資料..."):
        try:
            summary = get_portfolio_summary(no_price=no_price)
        except Exception as e:
            st.error(f"讀取資料失敗：{e}")
            return

    if not summary.assets:
        st.info("投資組合是空的！請至「新增交易」頁面加入第一筆持倉。")
        return

    # ── 指標卡片 ──────────────────────────────────
    st.subheader("投資組合概覽")
    c1, c2, c3, c4, c5 = st.columns(5)
    upnl = summary.total_unrealized_pnl
    rpnl = summary.total_realized_pnl
    ret_pct = summary.total_return_pct

    c1.metric("總投入成本",   f"{_fmt(summary.total_cost_basis)} 元")
    c2.metric("總市值",       f"{_fmt(summary.total_market_value)} 元",
              delta=f"{_pnl_str(upnl)} 元" if upnl else None,
              delta_color="normal" if (upnl or 0) >= 0 else "inverse")
    c3.metric("未實現損益",   f"{_pnl_str(upnl)} 元")
    c4.metric("已實現損益",   f"{_pnl_str(rpnl)} 元")
    c5.metric("整體報酬率",   f"{_pnl_str(ret_pct, 2)} %" if ret_pct else "—")

    st.divider()

    # ── 持倉明細（全寬） ──────────────────────────
    st.subheader("持倉明細")

    tbody = ""
    for a in summary.assets:
        if a.quantity == 0:
            continue
        pnl = a.unrealized_pnl or 0
        clr = "color:#d32f2f" if pnl >= 0 else "color:#388e3c"
        pct = f"{_pnl_str(a.unrealized_pnl_pct, 2)}%" if a.unrealized_pnl_pct else "—"
        price_str = f"{a.current_price:,.2f}" if a.current_price else "—"
        mv_str    = f"{a.market_value:,.0f}"  if a.market_value  else "—"
        tbody += (
            f"<tr>"
            f"<td>{a.ticker}</td>"
            f"<td>{a.name}</td>"
            f"<td>{a.asset_type}</td>"
            f"<td class='r'>{a.quantity:,}</td>"
            f"<td class='r'>{a.avg_cost:,.2f}</td>"
            f"<td class='r'>{price_str}</td>"
            f"<td class='r'>{mv_str}</td>"
            f"<td class='r' style='{clr}'>{_pnl_str(a.unrealized_pnl)}</td>"
            f"<td class='r' style='{clr}'>{pct}</td>"
            f"<td class='r'>{a.total_dividend:,.0f}</td>"
            f"</tr>"
        )

    if tbody:
        st.markdown(f"""
<style>
.htbl{{width:100%;border-collapse:collapse;font-size:clamp(12px,1.1vw,15px)}}
.htbl th{{
    padding:8px 12px;white-space:nowrap;
    border-bottom:2px solid rgba(128,128,128,.35);
    font-weight:600;text-align:left
}}
.htbl td{{padding:7px 12px;white-space:nowrap;border-bottom:1px solid rgba(128,128,128,.12)}}
.htbl .r{{text-align:right}}
.htbl th:nth-child(n+4){{text-align:right}}
.htbl tr:hover td{{background:rgba(128,128,128,.07)}}
</style>
<div style="overflow-x:auto">
<table class="htbl">
<thead><tr>
  <th>代碼</th><th>名稱</th><th>類型</th>
  <th>股數</th><th>均成本</th><th>現價</th>
  <th>市值</th><th>未實現損益</th><th>報酬率</th><th>股利</th>
</tr></thead>
<tbody>{tbody}</tbody>
</table>
</div>""", unsafe_allow_html=True)

    st.divider()

    # ── 持倉配置（圓餅 + 類型小計） ───────────────
    st.subheader("持倉配置")

    labels, names, values, colors_map = [], [], [], []
    color_set = {"個股": "#ef5350", "股票ETF": "#42a5f5", "債券ETF": "#66bb6a"}

    by_type: dict[str, float] = {}
    for a in summary.assets:
        if a.quantity == 0:
            continue
        v = a.market_value if a.market_value else a.cost_basis
        labels.append(a.ticker)
        names.append(a.name)
        values.append(v)
        colors_map.append(color_set.get(a.asset_type, "#bdbdbd"))
        by_type[a.asset_type] = by_type.get(a.asset_type, 0) + v

    if values:
        col_pie, col_legend = st.columns([3, 2])

        with col_pie:
            fig = go.Figure(go.Pie(
                labels=labels,
                values=values,
                customdata=names,
                hole=0.45,
                marker=dict(colors=colors_map),
                textinfo="label+percent",
                textfont=dict(size=13),
                hovertemplate="%{label} %{customdata}<br>市值：%{value:,.0f} 元<br>占比：%{percent}<extra></extra>",
            ))
            fig.update_layout(
                showlegend=False,
                margin=dict(t=10, b=10, l=10, r=10),
                height=360,
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_legend:
            st.markdown("<br><br>", unsafe_allow_html=True)
            total_v = sum(by_type.values()) or 1
            for atype, v in by_type.items():
                color = color_set.get(atype, "#bdbdbd")
                pct = v / total_v * 100
                st.markdown(
                    f"<div style='margin-bottom:12px'>"
                    f"<span style='display:inline-block;width:14px;height:14px;"
                    f"background:{color};border-radius:3px;vertical-align:middle;margin-right:8px'></span>"
                    f"<b>{atype}</b> &nbsp; {pct:.1f}% &nbsp; {v:,.0f} 元"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # ── 股債配置（純股票 vs 純債券） ──────────
        stock_v = by_type.get("個股", 0) + by_type.get("股票ETF", 0)
        bond_v  = by_type.get("債券ETF", 0)
        total_sb = stock_v + bond_v or 1

        st.markdown("##### 股債配置")
        sb1, sb2 = st.columns(2)
        sb1.metric(
            "📈 股票部位",
            f"{stock_v / total_sb * 100:.1f} %",
            help=f"個股 + 股票ETF 共 {stock_v:,.0f} 元",
        )
        sb2.metric(
            "🛡️ 債券部位",
            f"{bond_v / total_sb * 100:.1f} %",
            help=f"債券ETF 共 {bond_v:,.0f} 元",
        )
        # 比例橫條
        stock_pct = stock_v / total_sb * 100
        bond_pct = bond_v / total_sb * 100
        st.markdown(
            f"<div style='display:flex;height:22px;border-radius:6px;overflow:hidden;"
            f"font-size:12px;color:white;line-height:22px;text-align:center'>"
            f"<div style='width:{stock_pct}%;background:#ef5350'>"
            f"{'股 ' + format(stock_pct, '.0f') + '%' if stock_pct >= 12 else ''}</div>"
            f"<div style='width:{bond_pct}%;background:#66bb6a'>"
            f"{'債 ' + format(bond_pct, '.0f') + '%' if bond_pct >= 12 else ''}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── 集中度警示 ────────────────────────────────
    if values:
        top = max(zip(labels, names, values), key=lambda x: x[2])
        top_pct = top[2] / (sum(values) or 1) * 100
        if top_pct >= 70:
            st.error(
                f"⚠️ 高度集中：**{top[0]} {top[1]}** 占投資組合 **{top_pct:.1f}%**，"
                f"單一持股風險偏高，建議分散配置。"
            )
        elif top_pct >= 50:
            st.warning(
                f"📌 注意集中度：**{top[0]} {top[1]}** 占投資組合 **{top_pct:.1f}%**。"
            )

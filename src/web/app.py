"""
StockAA — Streamlit Web UI 主程式
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

st.set_page_config(
    page_title="StockAA 投資組合",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
/* 隱藏側邊欄與收合按鈕 */
[data-testid="stSidebar"],
[data-testid="collapsedControl"] { display: none !important; }

/* 左右留白、限制最大寬度 */
.block-container {
    max-width: 1320px;
    padding: 1.5rem 4rem 3rem !important;
    margin: 0 auto;
}
</style>
""", unsafe_allow_html=True)

# ── 頂部 Logo ──────────────────────────────────
st.markdown(
    "## 📈 StockAA &emsp;"
    "<span style='font-size:1rem;font-weight:400;color:gray'>台灣股市投資組合管理</span>",
    unsafe_allow_html=True,
)
st.divider()

# ── Tab 導覽 ───────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(
    ["🏠 持倉總覽", "➕ 新增交易", "📋 交易記錄", "📊 損益分析"]
)

with tab1:
    from src.web.pages.dashboard import render
    render()

with tab2:
    from src.web.pages.add_transaction import render as render_add
    render_add()

with tab3:
    from src.web.pages.transactions import render as render_tx
    render_tx()

with tab4:
    from src.web.pages.charts import render as render_charts
    render_charts()

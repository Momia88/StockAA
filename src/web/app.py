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
    initial_sidebar_state="expanded",
)

# ── 側邊欄 ──────────────────────────────────
with st.sidebar:
    st.title("📈 StockAA")
    st.caption("台灣股市投資組合管理")
    st.divider()
    page = st.radio(
        "選擇頁面",
        ["🏠 持倉總覽", "➕ 新增交易", "📋 交易記錄", "📊 損益分析"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("資料來源：TWSE / TPEx Open API")

# ── 頁面路由 ─────────────────────────────────
if page == "🏠 持倉總覽":
    from src.web.pages.dashboard import render
    render()
elif page == "➕ 新增交易":
    from src.web.pages.add_transaction import render
    render()
elif page == "📋 交易記錄":
    from src.web.pages.transactions import render
    render()
elif page == "📊 損益分析":
    from src.web.pages.charts import render
    render()

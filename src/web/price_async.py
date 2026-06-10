"""
前端現價非同步更新元件

頁面先以 SQLite 快取/成本價秒開，背景執行緒抓現價；本元件以 st.fragment
每隔數秒輪詢，待背景完成後觸發整頁重跑，局部換上最新現價。
"""
import streamlit as st

from src.web.data import ensure_prices_async, prices_ready


@st.fragment(run_every=2)
def _price_poller(tickers: list[str]):
    """每 2 秒檢查背景抓價是否完成；完成即重跑整頁顯示最新現價"""
    if prices_ready(tickers):
        st.rerun(scope="app")
    else:
        st.caption("🔄 現價更新中，稍候將自動更新…")


def ensure_live_prices(tickers: list[str], force: bool = False) -> None:
    """啟動背景抓價；尚未完成時顯示輪詢提示，完成後自動刷新整頁"""
    if not tickers:
        return
    ensure_prices_async(tickers, force=force)
    if not prices_ready(tickers):
        _price_poller(tickers)

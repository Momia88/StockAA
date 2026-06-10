"""
StockAA 桌面啟動器
─────────────────────────────────────────────
供 PyInstaller 打包成 macOS / Windows 獨立執行檔。
啟動內嵌的 Streamlit 伺服器，並自動開啟瀏覽器。

資料存放：
  - 預設資料夾為使用者家目錄下的 ~/StockAA/
  - portfolio.db 與 logs/ 會落在此處（避免寫入唯讀的 App 內部）
  - 若該資料夾放有 .env（可指向 Google Drive 路徑），會自動沿用
"""
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

PORT = 8501


def _resource_path(rel: str) -> str:
    """取得打包後資源的絕對路徑（相容 PyInstaller 的 _MEIPASS）"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def _prepare_data_dir() -> Path:
    """建立使用者可寫入的資料夾，存放 portfolio.db 與 logs"""
    data_dir = Path.home() / "StockAA"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(exist_ok=True)
    # 切換工作目錄，讓 ./portfolio.db 與 logs/ 都落在此處；
    # 若此資料夾內有 .env，pydantic-settings 也會自動讀取
    os.chdir(data_dir)
    return data_dir


def _open_browser() -> None:
    time.sleep(3)
    webbrowser.open(f"http://localhost:{PORT}")


def _bundle_hint() -> None:  # pragma: no cover
    """
    僅供 PyInstaller 靜態分析收集相依套件，執行期不需呼叫。
    確保 Streamlit 以 `streamlit run` 動態載入 app.py 時，
    其第三方相依（SQLAlchemy / requests / loguru …）已被凍結進執行檔。
    """
    import sqlalchemy            # noqa: F401
    import sqlalchemy.dialects.sqlite  # noqa: F401
    import requests             # noqa: F401
    import loguru               # noqa: F401
    import pydantic             # noqa: F401
    import pydantic_settings    # noqa: F401
    import urllib3              # noqa: F401
    import pandas               # noqa: F401
    import plotly               # noqa: F401
    import plotly.graph_objects  # noqa: F401
    import plotly.express        # noqa: F401


def main() -> None:
    _prepare_data_dir()

    # 強制關閉開發模式：打包後 streamlit 不在 site-packages，會被誤判為
    # developmentMode=true，導致無法指定 server.port。必須在匯入 streamlit 前設定。
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")

    app_path = _resource_path(os.path.join("src", "web", "app.py"))

    # 背景開啟瀏覽器（伺服器啟動約需 2-3 秒）
    threading.Thread(target=_open_browser, daemon=True).start()

    import streamlit.web.cli as stcli
    sys.argv = [
        "streamlit", "run", app_path,
        "--server.port", str(PORT),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()

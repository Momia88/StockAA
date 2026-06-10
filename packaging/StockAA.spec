# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包設定 — StockAA 桌面版（跨平台：macOS / Windows）

於專案根目錄執行：
    pyinstaller packaging/StockAA.spec --noconfirm

產物：dist/StockAA/  （onedir 模式，整個資料夾即為可攜程式）
"""
import os

from PyInstaller.utils.hooks import collect_all, copy_metadata

# SPECPATH 由 PyInstaller 注入 = 本 spec 檔所在目錄（.../packaging）
ROOT = os.path.dirname(SPECPATH)  # noqa: F821  專案根目錄

datas = []
binaries = []
hiddenimports = []

# ── 完整收集（子模組 + 資料檔 + 二進位）核心相依 ────────────
# 含 pydantic_core / numpy 等帶 C 擴充（.pyd/.so）的套件，避免
# Windows 出現 "No module named 'pydantic_core._pydantic_core'"。
for pkg in (
    "streamlit", "altair", "pyarrow", "plotly", "pandas", "numpy",
    "narwhals", "pydantic", "pydantic_core", "pydantic_settings",
    "sqlalchemy", "loguru", "requests",
):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# ── 套件 metadata ────────────────────────────────────────────
# streamlit / plotly 等在 import 時會用 importlib.metadata 讀自身版本，
# 缺 metadata 會出現 "No package metadata was found for ..." 而崩潰。
# 逐套件 try/except，避免單一缺漏導致整批未收集。
for pkg in (
    "streamlit", "plotly", "pandas", "numpy", "pyarrow", "altair",
    "narwhals", "pydantic", "pydantic_core", "pydantic_settings",
    "sqlalchemy", "requests", "loguru", "tenacity", "packaging",
    "click", "rich", "tornado", "gitpython", "watchdog", "blinker",
):
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

# 另外遞迴收集 streamlit 相依樹的 metadata（補齊上面清單外的相依）
try:
    datas += copy_metadata("streamlit", recursive=True)
except Exception:
    pass

# ── 專案原始碼與 Streamlit 設定 ─────────────────────────────
datas += [
    (os.path.join(ROOT, "src"), "src"),
    (os.path.join(ROOT, ".streamlit"), ".streamlit"),
]

hiddenimports += [
    "sqlalchemy",
    "sqlalchemy.dialects.sqlite",
    "requests",
    "loguru",
    "pydantic",
    "pydantic_settings",
    "pydantic_core",
    "pydantic_core._pydantic_core",
    "urllib3",
]

a = Analysis(
    [os.path.join(SPECPATH, "run_desktop.py")],  # noqa: F821
    pathex=[ROOT],          # 使 import src.* 可解析
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StockAA",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,           # 保留終端機視窗，便於檢視啟動訊息與錯誤
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="StockAA",
)

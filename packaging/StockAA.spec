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

# ── 收集 Streamlit 及其資料密集型相依 ───────────────────────
for pkg in ("streamlit", "altair", "pyarrow", "plotly", "pandas"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# Streamlit 會用 importlib.metadata 查自身與相依套件版本
datas += copy_metadata("streamlit", recursive=True)

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

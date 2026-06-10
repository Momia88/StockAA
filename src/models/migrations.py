"""
輕量資料庫遷移框架 — 方案 A
────────────────────────────────────────────────────────────
目標：程式更新後，自動把舊的 portfolio.db「就地升級」到最新結構，
      過程中先自動備份，使用者完全無感、舊資料不遺失。

機制：
  1. 用 SQLite 內建的 `PRAGMA user_version` 記錄資料庫的 schema 版本。
  2. 啟動時比對 DB 版本與程式的 LATEST_VERSION：
       - 全新 DB（無資料表）→ 直接建表並標記為最新版，不需遷移。
       - 既有 DB 版本落後 → 先備份，再逐版套用 MIGRATIONS，最後更新版本號。
  3. 備份檔放在 DB 同目錄，命名 portfolio.db.bak-YYYYmmdd_HHMMSS，只保留最近數份。

╔══════════════════════════════════════════════════════════╗
║ 如何新增一次 schema 變更（給未來的開發者）                ║
║ 1. 修改 models/*.py（例如 Asset 新增一個欄位）。         ║
║ 2. 把 LATEST_VERSION + 1。                                ║
║ 3. 在 MIGRATIONS 加入 { 新版本號: ["ALTER TABLE ..."] }， ║
║    用「能套用在舊資料上」的 SQL（通常是 ADD COLUMN）。    ║
║ 全新 DB 由 create_all() 直接建出最新結構；舊 DB 則靠這些 ║
║ SQL 補上差異 — 兩條路最終結構一致。                       ║
╚══════════════════════════════════════════════════════════╝
"""
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import inspect, text

from .base import Base

# 目前程式對應的 schema 版本。每次改動資料表結構就 +1。
LATEST_VERSION = 1

# 既有（升級前未受本框架管理）資料庫的基準版本。
# 這類 DB 的 user_version 為 0，但其結構等同第 1 版，故視為 BASELINE_VERSION。
BASELINE_VERSION = 1

# 版本 → 需套用於既有資料庫的 SQL 陳述式清單。
# 範例（未啟用）：
#   2: ["ALTER TABLE assets ADD COLUMN target_weight FLOAT DEFAULT 0.0"],
MIGRATIONS: dict[int, list[str]] = {}

# 備份保留份數
_KEEP_BACKUPS = 5


def _db_file(engine) -> Optional[Path]:
    """從 engine 取得實體 DB 檔路徑；記憶體資料庫回傳 None"""
    db = engine.url.database
    if not db or db == ":memory:":
        return None
    return Path(db)


def _tables_exist(engine) -> bool:
    """資料庫是否已建立核心資料表（用 assets 當代表）"""
    return inspect(engine).has_table("assets")


def _get_user_version(engine) -> int:
    with engine.connect() as conn:
        return int(conn.exec_driver_sql("PRAGMA user_version").scalar() or 0)


def _set_user_version(engine, version: int) -> None:
    # PRAGMA 不支援參數綁定，但 version 為內部 int，無注入風險
    with engine.begin() as conn:
        conn.exec_driver_sql(f"PRAGMA user_version = {int(version)}")


def backup_database(db_path: Path, keep: int = _KEEP_BACKUPS) -> Optional[Path]:
    """升級前備份整個 DB；先 checkpoint WAL 確保含最新已提交資料"""
    if not db_path.exists():
        return None

    # 把 WAL 寫回主檔，避免備份遺漏尚在 -wal 的資料
    try:
        with closing(sqlite3.connect(str(db_path))) as c:
            c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:  # noqa: BLE001 — checkpoint 失敗仍照常備份主檔
        pass

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = db_path.with_name(f"{db_path.name}.bak-{ts}")
    shutil.copy2(db_path, dst)
    _prune_backups(db_path, keep)
    return dst


def _prune_backups(db_path: Path, keep: int) -> None:
    """只保留最近 keep 份備份，其餘刪除"""
    backups = sorted(
        db_path.parent.glob(f"{db_path.name}.bak-*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def run_migrations(engine) -> Optional[Path]:
    """
    建表 + 就地升級舊資料庫。回傳本次若有升級所產生的備份路徑（否則 None）。
    此函式取代原本單純的 Base.metadata.create_all，供所有進入點共用。
    """
    db_path = _db_file(engine)

    # ── 全新資料庫：直接建出最新結構並標記版本 ──────────────
    if not _tables_exist(engine):
        Base.metadata.create_all(engine)
        _set_user_version(engine, LATEST_VERSION)
        return None

    # ── 既有資料庫：判斷是否需要升級 ────────────────────────
    current = _get_user_version(engine)
    effective = current if current >= BASELINE_VERSION else BASELINE_VERSION

    backup: Optional[Path] = None
    if effective < LATEST_VERSION and db_path is not None:
        backup = backup_database(db_path)

    # 先建立新版本可能引入的「全新資料表」（不會更動既有表）
    Base.metadata.create_all(engine)

    # 逐版套用欄位/資料層級的遷移 SQL
    if effective < LATEST_VERSION:
        with engine.begin() as conn:
            for version in range(effective + 1, LATEST_VERSION + 1):
                for stmt in MIGRATIONS.get(version, []):
                    conn.execute(text(stmt))

    # 更新版本戳記（含把舊 DB 的 0 標記為 BASELINE/最新）
    if current != LATEST_VERSION:
        _set_user_version(engine, LATEST_VERSION)

    return backup

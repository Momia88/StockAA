"""
Google Drive 同步設定腳本
自動偵測 Google Drive 路徑，產生 .env 設定檔
"""
import os
import sys
import subprocess
from pathlib import Path


def find_google_drive_path() -> list[Path]:
    """自動偵測 macOS 上的 Google Drive 路徑"""
    home = Path.home()
    candidates = [
        # Google Drive for Desktop（新版）
        home / "Library" / "CloudStorage",
        # 舊版 Google Drive
        home / "Google Drive",
        home / "Google 雲端硬碟",
    ]

    found = []
    for candidate in candidates:
        if candidate.exists():
            if candidate.name == "CloudStorage":
                # 列出 CloudStorage 下的所有 Google Drive 資料夾
                for sub in candidate.iterdir():
                    if sub.name.startswith("GoogleDrive-"):
                        my_drive = sub / "My Drive"
                        if my_drive.exists():
                            found.append(my_drive)
            else:
                found.append(candidate)
    return found


def setup_env(drive_path: Path) -> None:
    """產生 .env 設定檔"""
    db_dir = drive_path / "StockAA"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "portfolio.db"

    env_content = f"""# StockAA 環境設定（由 setup_drive.py 自動產生）
# ===== 資料庫路徑（Google Drive 同步）=====
DB_PATH={db_path}

# ===== API 設定 =====
# 手續費折扣（0.6 = 六折，網路下單常見折扣）
BROKERAGE_DISCOUNT=0.6

# API 請求 timeout（秒）
API_TIMEOUT=15

# 股價快取有效期（秒）
PRICE_CACHE_TTL=300

# ===== 顯示設定 =====
LOG_LEVEL=INFO
"""

    env_file = Path(".env")
    if env_file.exists():
        print(f"⚠️  .env 已存在，備份為 .env.backup")
        env_file.rename(".env.backup")

    env_file.write_text(env_content, encoding="utf-8")
    print(f"✅ .env 設定完成")
    print(f"   資料庫路徑：{db_path}")
    print(f"   Google Drive 資料夾：{db_dir}")


def main():
    print("=" * 60)
    print("  StockAA — Google Drive 同步設定精靈")
    print("=" * 60)
    print()

    drives = find_google_drive_path()

    if not drives:
        print("❌ 找不到 Google Drive 資料夾！")
        print()
        print("請確認：")
        print("  1. 已安裝 Google Drive for Desktop")
        print("  2. 已登入 Google 帳號並同步完成")
        print()
        print("或手動編輯 .env 檔案，設定 DB_PATH 為您的 Google Drive 路徑")
        print("例：DB_PATH=/Users/yourname/Google Drive/My Drive/StockAA/portfolio.db")

        # 提供手動設定選項
        manual = input("\n是否使用預設路徑（./portfolio.db）？[Y/n]: ").strip().lower()
        if manual in ("", "y"):
            import shutil
            shutil.copy(".env.example", ".env")
            print("✅ 已複製 .env.example 為 .env（資料庫存在本機）")
        sys.exit(0)

    if len(drives) == 1:
        selected = drives[0]
        print(f"✅ 找到 Google Drive：{selected}")
    else:
        print("找到多個 Google Drive 路徑，請選擇：")
        for i, drive in enumerate(drives, 1):
            print(f"  {i}. {drive}")
        while True:
            try:
                choice = int(input("\n請輸入數字選擇："))
                if 1 <= choice <= len(drives):
                    selected = drives[choice - 1]
                    break
                print("無效選擇，請重試")
            except ValueError:
                print("請輸入數字")

    setup_env(selected)

    print()
    print("=" * 60)
    print("  設定完成！接下來請執行：")
    print()
    print("  1. 安裝依賴：  poetry install")
    print("  2. 初始化 DB：stockaa init")
    print("  3. 新增買入：  stockaa add buy 2330 --price 600 --qty 1000")
    print("  4. 查看持倉：  stockaa show portfolio")
    print("=" * 60)


if __name__ == "__main__":
    main()

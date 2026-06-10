"""
範例資料填充腳本 — 快速建立測試用持倉

實際的範例資料與播種邏輯集中於 src/services/sample_data.py，
本腳本僅負責建立連線並呼叫之（供開發時手動執行）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import create_all_tables, get_db_session, get_engine, get_session_factory
from src.services.sample_data import seed_sample_data
from src.utils.config import get_settings


def seed():
    settings = get_settings()
    engine = get_engine(settings.db_path)
    create_all_tables(engine)
    session_factory = get_session_factory(engine)

    with get_db_session(session_factory) as session:
        count = seed_sample_data(session, brokerage_discount=settings.brokerage_discount)

    print()
    print(f"✅ 範例資料填充完成！（成功 {count} 筆）")
    print("   執行 'stockaa show portfolio' 查看結果")


if __name__ == "__main__":
    print("=" * 50)
    print("  填充範例投資組合資料...")
    print("=" * 50)
    seed()

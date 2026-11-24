"""研究用の記録（data/mycover.db）を CSV に書き出す。Excel でそのまま開ける（UTF-8 BOM 付き）。

使い方：export_csv.bat をダブルクリック（または py tools/export_csv.py）
出力先：data/export/<日時>/ の中に、表ごとの CSV
"""
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mycover.config import DATA_DIR  # noqa: E402
from mycover.db import DB_PATH, Database  # noqa: E402


def main():
    if not DB_PATH.exists():
        print(f"記録がまだありません：{DB_PATH}")
        return 1
    db = Database()
    out = DATA_DIR / "export" / time.strftime("%Y%m%d_%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    for table in Database.TABLES:
        header, rows = db.rows(table)
        with open(out / f"{table}.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows([tuple(r) for r in rows])
        print(f"{table}: {len(rows)} 件")
    print(f"書き出しました：{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

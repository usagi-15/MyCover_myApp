"""カード用トークンを発行し、印刷用の CSV と QR 画像を作り、Supabase の cards テーブルに登録する。

使い方：make_cards.bat をダブルクリック（または py tools/make_cards.py）
出力：data/cards/cards.csv（カード No.・表示用 No.・トークン・URL）、data/cards/qr/card_0001.png …

★ 一度印刷したカードのトークンは絶対に変えないこと。
  - 何度実行しても、既にあるカードのトークンは作り直さない（data/cards/cards.csv か Supabase から読み込む）
  - Supabase と手元でトークンが食い違う場合は、何も変更せずに止まる
  - data/cards フォルダはバックアップしておく（USB メモリなど）
"""
import argparse
import csv
import secrets
import sys
from pathlib import Path

import qrcode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mycover.config import DATA_DIR, load_config  # noqa: E402
from mycover.supabase import Supabase  # noqa: E402

OUT = DATA_DIR / "cards"
CSV_PATH = OUT / "cards.csv"


def load_local():
    if not CSV_PATH.exists():
        return {}
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        return {int(r["card_no"]): r["card_token"] for r in csv.DictReader(f)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-upload", action="store_true", help="Supabase に登録しない（手元のファイルだけ作る）")
    args = ap.parse_args()

    cfg = load_config()
    n = cfg["numbering"]
    numbers = list(range(n["card_start_no"], n["card_start_no"] + n["card_count"]))
    base = cfg["mobile"]["public_url"]
    digits = n["card_digits"]

    tokens = load_local()
    client = None if args.no_upload else Supabase(cfg)
    if client is not None:
        if not client.enabled:
            print("Supabase の秘密キーが未設定です。先に set_supabase_key.bat を実行してください。")
            print("（手元のファイルだけ作るときは --no-upload を付けて実行）")
            return 1
        remote = {r["card_no"]: r["card_token"]
                  for r in client.select("cards", {"select": "card_no,card_token", "order": "card_no"})}
        conflicts = [no for no in remote if no in tokens and tokens[no] != remote[no]]
        if conflicts:
            print(f"[中止] 手元と Supabase でトークンが違うカードがあります：{conflicts[:10]}")
            print("印刷済みのカードを壊さないよう、何も変更していません。作者に相談してください。")
            return 1
        for no, tok in remote.items():
            tokens.setdefault(no, tok)  # 手元に無いものは Supabase から復元

    created = 0
    for no in numbers:
        if no not in tokens:
            tokens[no] = secrets.token_urlsafe(12)
            created += 1

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "qr").mkdir(exist_ok=True)
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["card_no", "display_no", "card_token", "url", "qr_file"])
        for no in sorted(tokens):
            url = f"{base}?c={tokens[no]}"
            qr_file = f"qr/card_{no:0{digits}d}.png"
            qrcode.make(url, border=2, box_size=10).save(OUT / qr_file)
            w.writerow([no, f"No.{no:0{digits}d}", tokens[no], url, qr_file])
    print(f"カード {len(tokens)} 枚（新しく発行 {created} 枚）→ {CSV_PATH}")

    if client is not None:
        rows = [{"card_no": no, "card_token": tokens[no]} for no in sorted(tokens)]
        client.upsert("cards", rows, on_conflict="card_no")
        print(f"Supabase の cards に登録しました（{len(rows)} 枚）")
    print("★ data/cards フォルダをバックアップしてください（印刷したカードと対応する大事なデータです）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

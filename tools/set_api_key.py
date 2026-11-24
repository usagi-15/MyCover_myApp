"""OpenAI の API キーを config/secrets.json に保存する（Git 管理外のファイル）。

使い方：set_api_key.bat をダブルクリック（または py tools/set_api_key.py）
"""
import getpass
import json
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "config" / "secrets.json"


def main():
    print("OpenAI の API キーを貼り付けて Enter を押してください。")
    print("（右クリックで貼り付けられます。安全のため、貼り付けても画面には何も表示されません）")
    key = getpass.getpass("API キー: ").strip()
    if not key:
        print("何も入力されませんでした。保存していません。")
        return 1
    if not key.startswith("sk-"):
        print("「sk-」で始まっていません。キーをもう一度コピーしてやり直してください。保存していません。")
        return 1
    data = {}
    if PATH.exists():
        with open(PATH, encoding="utf-8") as f:
            data = json.load(f)
    data["openai_api_key"] = key
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"保存しました：{PATH}")
    print(f"（キーの最初と最後：{key[:6]}…{key[-4:]}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

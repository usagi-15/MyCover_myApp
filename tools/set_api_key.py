"""OpenAI の API キーを config/secrets.json に保存する（Git 管理外のファイル）。

使い方：set_api_key.bat をダブルクリック（または py tools/set_api_key.py）
保存の前に、キーが使えるかを OpenAI に確認する（モデル一覧の取得。料金はかからない）。
"""
import getpass
import json
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "config" / "secrets.json"


def check_format(key):
    """形式の確認。問題があればメッセージを返す。"""
    if not key:
        return "何も入力されませんでした。"
    repeats = key.count(key[:8]) if len(key) >= 8 else 1  # 先頭（例 sk-proj-）が何回出てくるか
    if repeats > 1:
        return (f"キーが {repeats} 回つながって入力されています（{len(key)} 文字）。"
                "貼り付けは 1 回だけにしてください。")
    if not key.startswith("sk-"):
        return "「sk-」で始まっていません。キーをもう一度コピーしてください。"
    if any(c.isspace() for c in key):
        return "キーの途中に空白や改行が入っています。キーをもう一度コピーしてください。"
    return None


def check_with_openai(key):
    """キーで OpenAI に問い合わせる。(ok, メッセージ) を返す。"""
    try:
        from openai import APIConnectionError, AuthenticationError, OpenAI, PermissionDeniedError
    except ImportError:
        return True, "（openai ライブラリが無いため、使えるかの確認は省略しました）"
    try:
        OpenAI(api_key=key, timeout=20, max_retries=0).models.list()
    except AuthenticationError:
        return False, "OpenAI に「このキーは正しくない」と言われました。キーをもう一度コピーしてやり直してください。"
    except PermissionDeniedError:
        return True, "キーは有効ですが、権限が制限されています。生成で失敗する場合は、キーの権限（Permissions）を確認してください。"
    except APIConnectionError:
        return True, "OpenAI に接続できず、使えるかの確認はできませんでした（インターネット接続を確認してください）。"
    return True, "OpenAI で使えるキーであることを確認しました。"


def main():
    print("OpenAI の API キーを貼り付けて Enter を押してください。")
    print("・右クリックを【1回だけ】押すと貼り付けられます")
    print("・安全のため、貼り付けても画面には何も表示されません。1回貼ったら、そのまま Enter を押してください")
    key = getpass.getpass("API キー: ").strip()
    problem = check_format(key)
    if problem:
        print("\n[保存していません] " + problem)
        print("もう一度 set_api_key.bat を実行してください。")
        return 1
    print(f"\n受け取りました（{len(key)} 文字：{key[:8]}…{key[-4:]}）。OpenAI に確認しています…")
    ok, message = check_with_openai(key)
    print(message)
    if not ok:
        print("[保存していません] もう一度 set_api_key.bat を実行してください。")
        return 1
    data = {}
    if PATH.exists():
        with open(PATH, encoding="utf-8") as f:
            data = json.load(f)
    data["openai_api_key"] = key
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"保存しました：{PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

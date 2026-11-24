"""Supabase の秘密キー（secret / service_role）を config/secrets.json に保存し、接続を確認する。

使い方：set_supabase_key.bat をダブルクリック（または py tools/set_supabase_key.py）
確認内容：cards テーブルを読めるか（秘密キーでしか読めない）、Storage に画像を置いて消せるか。
"""
import base64
import getpass
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mycover.config import CONFIG_DIR, load_config  # noqa: E402
from mycover.supabase import Supabase, SupabaseError, load_secret_key  # noqa: E402

PATH = CONFIG_DIR / "secrets.json"


def check_format(key):
    if not key:
        return "何も入力されませんでした。"
    if len(key) >= 12 and key.count(key[:10]) > 1:
        return f"キーが {key.count(key[:10])} 回つながって入力されています。貼り付けは 1 回だけにしてください。"
    if any(c.isspace() for c in key):
        return "キーの途中に空白や改行が入っています。"
    if key.startswith("sb_publishable_"):
        return "これは公開キー（publishable）です。秘密キー（sb_secret_ で始まるもの）を貼り付けてください。"
    if key.startswith("eyJ"):
        try:
            payload = key.split(".")[1]
            role = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))).get("role")
        except Exception:  # noqa: BLE001
            role = None
        if role != "service_role":
            return f"これは {role or '不明'} のキーです。service_role のキーを貼り付けてください。"
        return None
    if not key.startswith("sb_secret_"):
        return "「sb_secret_」で始まっていません。Supabase の API Keys 画面の Secret keys からコピーしてください。"
    return None


def verify(key):
    client = Supabase(load_config(), key=key)
    client.select("cards", {"select": "card_no", "limit": "1"})
    print("・データベース：OK（秘密キーで cards を読めました）")
    url = client.upload_image("_connection_test.jpg", b"\xff\xd8\xff\xd9")
    client.delete_image("_connection_test.jpg")
    print(f"・Storage：OK（covers バケットに置いて消せました）")
    return url


def main():
    if "--check" in sys.argv:  # 保存済みのキーで確認だけ
        key = load_secret_key()
        if not key:
            print("秘密キーが保存されていません。")
            return 1
    else:
        print("Supabase の秘密キー（Secret keys の sb_secret_... ）を貼り付けて Enter を押してください。")
        print("・右クリックを【1回だけ】押すと貼り付けられます")
        print("・安全のため、貼り付けても画面には何も表示されません")
        key = getpass.getpass("秘密キー: ").strip()
        problem = check_format(key)
        if problem:
            print("\n[保存していません] " + problem)
            return 1
        print(f"\n受け取りました（{len(key)} 文字：{key[:12]}…{key[-4:]}）。Supabase に確認しています…")
    try:
        verify(key)
    except SupabaseError as e:
        print(f"[確認に失敗しました] {e}")
        print("キーが正しいか、supabase/schema.sql を実行済みか確認してください。")
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"[Supabase に接続できませんでした] {e}")
        return 1
    if "--check" not in sys.argv:
        data = {}
        if PATH.exists():
            with open(PATH, encoding="utf-8") as f:
                data = json.load(f)
        data["supabase_secret_key"] = key
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"保存しました：{PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

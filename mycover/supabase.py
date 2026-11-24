"""Supabase への送信（展示PC → Supabase）。REST API を httpx で直接呼ぶ（追加ライブラリなし）。

- 秘密キー（secret / service_role）は config/secrets.json の "supabase_secret_key" か
  環境変数 SUPABASE_SECRET_KEY から読む。コードや GitHub には書かない。
- 送信に失敗しても展示は止めない。ローカル SQLite の synced フラグで管理し、バックグラウンドで再送する。
"""
import json
import logging
import os
import threading

import httpx

from .config import CONFIG_DIR

log = logging.getLogger("mycover.supabase")


def load_secret_key():
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if key:
        return key.strip()
    path = CONFIG_DIR / "secrets.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return (json.load(f).get("supabase_secret_key") or "").strip() or None
    return None


class SupabaseError(Exception):
    pass


class Supabase:
    def __init__(self, cfg, key=None):
        self.url = cfg["supabase"]["url"].rstrip("/")
        self.bucket = cfg["supabase"].get("bucket", "covers")
        self.key = key or load_secret_key()
        self.timeout = cfg["supabase"].get("timeout_sec", 20)

    @property
    def enabled(self):
        return bool(self.key)

    def _headers(self, extra=None):
        h = {"apikey": self.key}
        # 旧形式（JWT）の service_role キーは Authorization にも入れる。新形式（sb_secret_）は apikey だけで通る
        if self.key and self.key.startswith("eyJ"):
            h["Authorization"] = f"Bearer {self.key}"
        if extra:
            h.update(extra)
        return h

    def _check(self, res, what):
        if res.status_code >= 300:
            raise SupabaseError(f"{what}: HTTP {res.status_code} {res.text[:300]}")
        return res

    def public_url(self, name):
        return f"{self.url}/storage/v1/object/public/{self.bucket}/{name}"

    # ------------------------------------------------------------ Storage
    def upload_image(self, name, data, content_type="image/jpeg"):
        res = httpx.post(f"{self.url}/storage/v1/object/{self.bucket}/{name}", content=data,
                         headers=self._headers({"Content-Type": content_type, "x-upsert": "true",
                                                "Cache-Control": "max-age=31536000"}),
                         timeout=self.timeout)
        self._check(res, "画像のアップロード")
        return self.public_url(name)

    def delete_image(self, name):
        res = httpx.request("DELETE", f"{self.url}/storage/v1/object/{self.bucket}",
                            json={"prefixes": [name]}, headers=self._headers(), timeout=self.timeout)
        self._check(res, "画像の削除")

    # ------------------------------------------------------------ DB（PostgREST）
    def upsert(self, table, rows, on_conflict):
        res = httpx.post(f"{self.url}/rest/v1/{table}?on_conflict={on_conflict}", json=rows,
                         headers=self._headers({"Prefer": "resolution=merge-duplicates,return=minimal"}),
                         timeout=self.timeout)
        self._check(res, f"{table} への書き込み")

    def update(self, table, filters, values):
        res = httpx.patch(f"{self.url}/rest/v1/{table}", params=filters, json=values,
                          headers=self._headers({"Prefer": "return=representation"}), timeout=self.timeout)
        self._check(res, f"{table} の更新")
        return res.json()

    def select(self, table, params):
        res = httpx.get(f"{self.url}/rest/v1/{table}", params=params, headers=self._headers(),
                        timeout=self.timeout)
        self._check(res, f"{table} の読み取り")
        return res.json()


class SyncWorker:
    """確定済みジャケットとカードのひも付けを Supabase に送る。失敗したら一定間隔で再送する。"""

    def __init__(self, cfg, db, lock, images_dir, client=None):
        self.cfg = cfg
        self.db = db
        self.lock = lock
        self.images_dir = images_dir
        self.client = client or Supabase(cfg)
        self.interval = cfg["supabase"].get("retry_interval_sec", 30)
        self.wake = threading.Event()
        self.last_error = None
        self._thread = None

    def start(self):
        if not self.client.enabled:
            log.warning("Supabase の秘密キーが未設定のため、クラウドへの送信は行いません（展示PC内には記録されます）")
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def kick(self):
        """確定・持ち帰り方法の選択の直後に呼ぶ（すぐ送る）。"""
        self.wake.set()

    def _loop(self):
        while True:
            self.wake.clear()
            try:
                self.sync_once()
                self.last_error = None
            except Exception as e:  # noqa: BLE001 - 回線断などは次の周期で再送
                if str(e) != self.last_error:
                    log.warning("Supabase への送信に失敗（%d 秒ごとに再送します）：%s", self.interval, e)
                self.last_error = str(e)
            self.wake.wait(self.interval)

    def sync_once(self):
        with self.lock:
            covers = self.db.unsynced_covers()
            cards = self.db.unsynced_card_links()
        for c in covers:
            path = self.images_dir / c["image_file"]
            name = f"{c['token']}.jpg"  # 推測されにくい名前
            url = self.client.upload_image(name, path.read_bytes())
            self.client.upsert("covers", [{
                "jacket_no": c["jacket_no"], "token": c["token"], "image_url": url,
                "prompt": c["prompt"], "confirmed_at": c["confirmed_at"], "hidden": bool(c["hidden"]),
            }], on_conflict="jacket_no")
            with self.lock:
                self.db.mark_cover_synced(c["jacket_no"], url)
            log.info("Supabase に送信しました：No.%s", c["jacket_no"])
        with self.lock:
            cards = self.db.unsynced_card_links()  # 上でジャケットを送ったあとに読み直す
        for c in cards:
            rows = self.client.update("cards", {"card_no": f"eq.{c['card_no']}"},
                                      {"jacket_no": c["jacket_no"], "linked_at": c["confirmed_at"]})
            if not rows:
                raise SupabaseError(f"カード No.{c['card_no']} が Supabase に登録されていません（make_cards を実行してください）")
            with self.lock:
                self.db.mark_card_synced(c["jacket_no"])
            log.info("カード No.%s とジャケット No.%s をひも付けました", c["card_no"], c["jacket_no"])

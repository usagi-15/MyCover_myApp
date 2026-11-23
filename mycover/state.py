"""展示の状態を一元管理する（/desk と /display はポーリングでこの状態を取得する）。

フェーズ1では確定済みジャケットはメモリ上のみ（再起動で消える）。フェーズ3で SQLite に保存する。
"""
import secrets
import threading
import time
import uuid

from . import generator

# 体験途中（未確定）の画面。ここで HOME を押すと中止確認（D8）を出す
MAKING_SCREENS = {"D3", "D4", "D5"}


class ActionError(Exception):
    pass


class Exhibit:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.RLock()
        self.covers = []          # 確定済みジャケット（新しいものが末尾）
        self.covers_rev = 0
        self.next_jacket_no = 1
        self.next_card_no = cfg["numbering"]["card_start_no"]
        self.gen_times = []       # 直近の生成時間（秒）
        self._reset_desk()
        self.audio = self._audio_idle()
        self.display = {"screen": "S1", "cover": None, "mode": None}

    # ------------------------------------------------------------------ 内部
    def _reset_desk(self):
        self.desk = {"screen": "D1", "modal": None}
        self.session = None
        self.result = None  # 確定後の情報（D6/D7 で使う）

    @staticmethod
    def _audio_idle():
        return {"owner": None, "playing": False, "position": 0.0, "duration": None,
                "seek_seq": 0, "seek_to": 0.0, "range_end": None}

    def _stop_audio(self):
        """音を止める。seek_seq は単調増加のまま保つ（画面側の取りこぼし防止）。"""
        seq = self.audio["seek_seq"] + 1
        self.audio = self._audio_idle()
        self.audio["seek_seq"] = seq

    def _set_audio(self, owner, start=0.0, playing=False, range_end=None):
        a = self.audio
        a["owner"] = owner
        a["playing"] = playing
        a["position"] = start
        a["seek_to"] = start
        a["seek_seq"] += 1
        a["range_end"] = range_end

    def _chorus(self):
        t = self.cfg["track"]
        start = t.get("chorus_start_sec")
        end = t.get("chorus_end_sec")
        if start is None:
            return 0.0, float(t["s2_fallback_seconds"])
        return float(start), (float(end) if end is not None else None)

    def _estimate(self):
        g = self.cfg["generation"]
        recent = self.gen_times[-g["estimate_window"]:]
        if not recent:
            return float(g["initial_estimate_sec"])
        return sum(recent) / len(recent)

    def _discard_session(self):
        """中止：入力・生成画像・状態を完全に消去する。"""
        if self.session:
            for att in self.session["attempts"]:
                if att.get("image"):
                    generator.delete_image(att["image"])
            self.session["discarded"] = True
        self.session = None

    def _show_s1(self):
        self.display = {"screen": "S1", "cover": None, "mode": None}
        if self.audio["owner"] == "display":
            self._stop_audio()

    def _find_cover(self, jacket_no):
        for c in self.covers:
            if c["jacket_no"] == jacket_no and not c.get("hidden"):
                return c
        raise ActionError("cover not found")

    # ------------------------------------------------------------------ 公開
    def snapshot(self):
        with self.lock:
            s = self.session
            session = None
            if s:
                current = s["attempts"][-1] if s["attempts"] else None
                session = {
                    "input": s["input"],
                    "status": s["status"],          # idle / generating / done / error
                    "error": s.get("error"),
                    "gen_started_at": s.get("gen_started_at"),
                    "estimate_sec": s.get("estimate_sec"),
                    "image_url": f"/media/images/{current['image']}" if current and current.get("image") else None,
                    "image_input": current["input"] if current else None,
                    "attempts": len(s["attempts"]),
                }
            return {
                "now": time.time(),
                "desk": dict(self.desk),
                "session": session,
                "result": self.result,
                "audio": dict(self.audio),
                "display": dict(self.display),
                "covers_rev": self.covers_rev,
                "next_card_no": self.next_card_no,
            }

    def public_covers(self):
        with self.lock:
            return [
                {k: c[k] for k in ("jacket_no", "image_url", "input", "confirmed_at", "favorite_sec")}
                for c in reversed(self.covers) if not c.get("hidden")
            ]

    def report(self, client, position, duration, playing, ended):
        """音を鳴らしている画面が再生位置を報告する。"""
        with self.lock:
            a = self.audio
            if a["owner"] != client:
                return
            if position is not None:
                a["position"] = float(position)
            if duration:
                a["duration"] = float(duration)
            if ended:
                a["playing"] = False
                if client == "display" and self.display["mode"] == "confirm":
                    self._show_s1()
                elif client == "display" and self.display["mode"] == "gallery":
                    a["position"] = 0.0

    def audio_action(self, action, value=None):
        with self.lock:
            a = self.audio
            if a["owner"] is None:
                raise ActionError("no audio owner")
            if action == "play":
                a["playing"] = True
            elif action == "pause":
                a["playing"] = False
            elif action in ("seek", "skip"):
                target = float(value) if action == "seek" else a["position"] + float(value)
                if a["duration"]:
                    target = min(target, a["duration"] - 0.1)
                target = max(0.0, target)
                a["position"] = a["seek_to"] = target
                a["seek_seq"] += 1
            elif action == "from_start":
                a["position"] = a["seek_to"] = 0.0
                a["seek_seq"] += 1
                a["playing"] = True
            elif action == "from_favorite":
                cover = self.display.get("cover")
                fav = cover.get("favorite_sec") if cover else None
                if fav is None:
                    raise ActionError("no favorite point")
                a["position"] = a["seek_to"] = float(fav)
                a["seek_seq"] += 1
                a["playing"] = True
            else:
                raise ActionError(f"unknown audio action: {action}")

    def desk_action(self, action, data):
        with self.lock:
            handler = getattr(self, f"_act_{action}", None)
            if handler is None:
                raise ActionError(f"unknown action: {action}")
            handler(data or {})

    # ------------------------------------------------------------ 画面操作
    def _require(self, *screens):
        if self.desk["screen"] not in screens:
            raise ActionError(f"not allowed on {self.desk['screen']}")

    # メニューは待機中（ホーム・About・Gallery一覧）でのみ開ける。体験の途中では出さない
    IDLE_SCREENS = ("D1", "D2", "D9")

    def _act_menu_open(self, _):
        self._require(*self.IDLE_SCREENS)
        self.desk["modal"] = "menu"

    def _act_menu_close(self, _):
        if self.desk["modal"] == "menu":
            self.desk["modal"] = None

    def _act_start(self, _):
        self._require(*self.IDLE_SCREENS)
        self.session = {"id": uuid.uuid4().hex, "input": "", "attempts": [], "status": "idle",
                        "started_at": time.time(), "favorite_sec": None}
        self.desk = {"screen": "D3", "modal": None}
        if self.display["mode"] == "confirm":  # 前の人のサビ再生が残っていれば止める
            self._show_s1()
        self._set_audio("desk")

    def _act_about(self, _):
        self._require(*self.IDLE_SCREENS)
        self.desk = {"screen": "D2", "modal": None}

    def _act_gallery(self, _):
        self._require(*self.IDLE_SCREENS, "D10")
        if self.desk["screen"] == "D10":
            self._show_s1()
        self.desk = {"screen": "D9", "modal": None}

    def _act_home(self, _):
        screen = self.desk["screen"]
        if screen in MAKING_SCREENS:
            self.desk["modal"] = "abort"
            return
        if screen == "D10":
            self._show_s1()
        if screen in ("D6", "D7a", "D7b"):
            self._finish()
            return
        self._reset_desk()
        if self.audio["owner"] == "desk":
            self._stop_audio()

    def _act_abort_yes(self, _):
        if self.desk["modal"] != "abort":
            raise ActionError("no abort dialog")
        self._discard_session()
        self._reset_desk()
        self._stop_audio()

    def _act_abort_no(self, _):
        if self.desk["modal"] == "abort":
            self.desk["modal"] = None

    def _act_generate(self, data):
        self._require("D3", "D5", "D4")
        s = self.session
        text = (data.get("input") if "input" in data else s["input"]) or ""
        text = text.strip()
        if not text:
            raise ActionError("入力が空です")
        if len(text) > self.cfg["input"]["max_chars"]:
            raise ActionError("文字数が上限を超えています")
        if s["status"] == "generating":
            return
        s["input"] = text
        if data.get("position") is not None:
            # TODO: 「お気に入りポイント」の定義は未確認。仮に「これで生成する」を押した時点の再生位置を記録する
            s["favorite_sec"] = float(data["position"])
        s["status"] = "generating"
        s["error"] = None
        s["gen_started_at"] = time.time()
        s["estimate_sec"] = self._estimate()
        self.desk = {"screen": "D4", "modal": None}
        threading.Thread(target=self._run_generation, args=(s, text), daemon=True).start()

    def _run_generation(self, s, text):
        try:
            image, sec = generator.generate(self.cfg, text, len(s["attempts"]))
            error = None
        except Exception as e:  # noqa: BLE001 - 失敗は画面で再試行を促す
            image, sec, error = None, None, str(e)
        with self.lock:
            if s.get("discarded") or self.session is not s:
                if image:
                    generator.delete_image(image)
                return
            if error:
                s["status"] = "error"
                s["error"] = error
                return
            self.gen_times.append(sec)
            s["attempts"].append({"input": text, "image": image, "gen_sec": sec})
            s["status"] = "done"
            if self.desk["screen"] == "D4":
                self.desk["screen"] = "D5"

    def _act_edit(self, _):
        """言葉を変えて作り直す（入力は残す）。"""
        self._require("D5", "D4")
        if self.session["status"] == "generating":
            raise ActionError("生成中です")
        self.session["status"] = "idle" if not self.session["attempts"] else "done"
        self.desk = {"screen": "D3", "modal": None}

    def _act_retry(self, _):
        """同じ言葉でもう一度試行。"""
        self._require("D5", "D4")
        self._act_generate({})

    def _act_confirm(self, _):
        self._require("D5")
        s = self.session
        if not s["attempts"]:
            raise ActionError("画像がありません")
        last = s["attempts"][-1]
        cover = {
            "jacket_no": self.next_jacket_no,
            "image_url": f"/media/images/{last['image']}",
            "image": last["image"],
            "input": last["input"],
            "confirmed_at": time.time(),
            "favorite_sec": s.get("favorite_sec"),
            "attempts": [{"input": a["input"], "gen_sec": a["gen_sec"]} for a in s["attempts"]],
            "token": secrets.token_urlsafe(16),
            "takeaway": None,
            "card_no": None,
        }
        # 確定しなかった画像は消す
        for a in s["attempts"][:-1]:
            generator.delete_image(a["image"])
        self.next_jacket_no += 1
        self.covers.append(cover)
        self.covers_rev += 1
        self.session = None
        self.result = {"jacket_no": cover["jacket_no"], "token": cover["token"], "card_no": None,
                       "mobile_url": self.cfg["mobile"]["base_url"] + "?t=" + cover["token"]}
        self.desk = {"screen": "D6", "modal": None}
        self._play_on_display(cover, mode="confirm")

    def _play_on_display(self, cover, mode, start=None):
        public = {k: cover[k] for k in ("jacket_no", "image_url", "input", "favorite_sec")}
        self.display = {"screen": "S2", "cover": public, "mode": mode}
        if mode == "confirm":
            chorus_start, chorus_end = self._chorus()
            self._set_audio("display", chorus_start, playing=True, range_end=chorus_end)
        else:
            self._set_audio("display", start or 0.0, playing=True)

    def _act_get_it_now(self, _):
        self._require("D6")
        self._cover_by_no(self.result["jacket_no"])["takeaway"] = "get_it_now"
        self.desk["screen"] = "D7a"

    def _act_take_it_home(self, _):
        self._require("D6")
        cover = self._cover_by_no(self.result["jacket_no"])
        cover["takeaway"] = "take_it_home"
        cover["card_no"] = self.next_card_no
        self.result["card_no"] = self.next_card_no
        self.next_card_no += 1
        self.desk["screen"] = "D7b"

    def _cover_by_no(self, no):
        for c in self.covers:
            if c["jacket_no"] == no:
                return c
        raise ActionError("cover not found")

    def _act_finish(self, _):
        self._require("D6", "D7a", "D7b")
        self._finish()

    def _finish(self):
        # 大型モニターの再生（サビ）はそのまま続け、終わったら S1 に戻る
        self._reset_desk()

    def _act_gallery_select(self, data):
        self._require("D9", "D10")
        cover = self._find_cover(int(data["jacket_no"]))
        self.desk = {"screen": "D10", "modal": None, "jacket_no": cover["jacket_no"]}
        self._play_on_display(cover, mode="gallery")

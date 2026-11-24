"""ローカル SQLite（data/mycover.db）。確定済みジャケットと研究用の記録を保存する。

実装指示書 7章：
- covers         ：jacket_no、確定日時、入力文（確定版）、作り直し回数、持ち帰り方法、card_no、token、予備モードか
- cover_attempts ：各回の入力文と生成時間（確定したジャケットのぶんだけ。中止した回は残さない）
- sessions       ：開始・中止・確定の日時（中止した回は入力文を残さず、事実と時間だけ）
- gallery_plays / gallery_events：ギャラリーで再生されたジャケットと、再生位置・お気に入りポイントの操作
個人を特定する情報（IP アドレスなど）は記録しない。

呼び出し側（Exhibit）のロックの中で使う前提。
"""
import sqlite3
from datetime import datetime

from .config import DATA_DIR

DB_PATH = DATA_DIR / "mycover.db"

SCHEMA = """
create table if not exists covers (
  jacket_no     integer primary key,
  session_id    text    not null,
  confirmed_at  text    not null,            -- ISO 8601（展示PCのローカル時刻）
  image_file    text    not null,            -- data/images/ のファイル名
  prompt        text    not null,            -- 確定版の入力文
  remake_count  integer not null,            -- 作り直し回数（生成回数 - 1）
  favorite_sec  real,                         -- お気に入りポイント（仮：これで生成するを押した時の再生位置）
  takeaway      text check (takeaway in ('get_it_now', 'take_it_home')),
  card_no       integer unique,
  token         text    not null unique,
  backup_mode   integer not null default 0,  -- 予備モードで作ったか（フェーズ5）
  hidden        integer not null default 0,  -- ギャラリーから非表示（/admin、フェーズ5）
  synced        integer not null default 0   -- Supabase に送信済みか（フェーズ4）
);

create table if not exists cover_attempts (
  jacket_no   integer not null references covers (jacket_no),
  attempt_no  integer not null,               -- 1 から
  prompt      text    not null,
  gen_sec     real,
  created_at  text    not null,
  primary key (jacket_no, attempt_no)
);

create table if not exists sessions (
  id          text primary key,
  started_at  text not null,
  ended_at    text,
  outcome     text check (outcome in ('confirmed', 'aborted')),  -- null：途中（サーバー停止など）
  jacket_no   integer,                         -- 確定したときだけ
  generations integer,                         -- 確定したときだけ：成功した生成の回数
  rejections  integer,                         -- 確定したときだけ：書き直しをお願いした回数
  failures    integer                          -- 確定したときだけ：生成に失敗した回数
);

create table if not exists gallery_plays (
  id          integer primary key autoincrement,
  jacket_no   integer not null,
  started_at  text    not null,
  ended_at    text
);

create table if not exists gallery_events (
  id          integer primary key autoincrement,
  play_id     integer not null references gallery_plays (id),
  at          text    not null,
  action      text    not null,                -- select / play / pause / seek / skip / from_start / from_favorite / ended / back
  position    real                             -- 操作した時点（seek は移動先）の再生位置（秒）
);
"""


# 後から足した列（既存の data/mycover.db にも追加する）
MIGRATIONS = [
    ("covers", "takeaway_at", "text"),              # 持ち帰り方法を選んだ日時
    ("covers", "card_synced", "integer not null default 0"),  # カードのひも付けを Supabase に送ったか
    ("covers", "remote_image_url", "text"),         # Supabase Storage の公開URL
]


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def iso_to_epoch(text):
    return datetime.fromisoformat(text).timestamp()


class Database:
    def __init__(self, path=DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("pragma journal_mode = wal")
        self.conn.execute("pragma foreign_keys = on")
        self.conn.executescript(SCHEMA)
        for table, column, decl in MIGRATIONS:
            cols = {r[1] for r in self.conn.execute(f"pragma table_info({table})")}
            if column not in cols:
                self.conn.execute(f"alter table {table} add column {column} {decl}")

    # ------------------------------------------------------------ 読み込み
    def load_covers(self):
        rows = self.conn.execute("select * from covers order by jacket_no").fetchall()
        return [dict(r) for r in rows]

    def max_jacket_no(self):
        return self.conn.execute("select coalesce(max(jacket_no), 0) from covers").fetchone()[0]

    def max_card_no(self):
        return self.conn.execute("select max(card_no) from covers").fetchone()[0]

    # ------------------------------------------------------------ sessions
    def session_started(self, session_id):
        self.conn.execute("insert into sessions (id, started_at) values (?, ?)", (session_id, now_iso()))

    def session_aborted(self, session_id):
        # 中止：入力文や回数は残さず、「中止された」事実と時間だけ
        self.conn.execute("update sessions set ended_at = ?, outcome = 'aborted' where id = ?",
                          (now_iso(), session_id))

    # ------------------------------------------------------------ 確定
    def confirm_cover(self, cover, session):
        """確定：covers・cover_attempts・sessions をまとめて書く。"""
        attempts = session["attempts"]
        with self.conn:
            self.conn.execute("begin")
            self.conn.execute(
                """insert into covers (jacket_no, session_id, confirmed_at, image_file, prompt, remake_count,
                                       favorite_sec, token, backup_mode)
                   values (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (cover["jacket_no"], session["id"], cover["confirmed_iso"], cover["image"], cover["input"],
                 len(attempts) - 1, cover["favorite_sec"], cover["token"], int(cover.get("backup_mode", 0))))
            self.conn.executemany(
                "insert into cover_attempts (jacket_no, attempt_no, prompt, gen_sec, created_at) values (?, ?, ?, ?, ?)",
                [(cover["jacket_no"], i + 1, a["input"], round(a["gen_sec"], 2), a["created_at"]) for i, a in enumerate(attempts)])
            self.conn.execute(
                """update sessions set ended_at = ?, outcome = 'confirmed', jacket_no = ?,
                                       generations = ?, rejections = ?, failures = ?
                   where id = ?""",
                (cover["confirmed_iso"], cover["jacket_no"], len(attempts),
                 session.get("rejections", 0), session.get("failures", 0), session["id"]))

    def set_takeaway(self, jacket_no, takeaway, card_no=None):
        self.conn.execute("update covers set takeaway = ?, card_no = ?, takeaway_at = ? where jacket_no = ?",
                          (takeaway, card_no, now_iso(), jacket_no))

    # ------------------------------------------------------------ Supabase 送信（フェーズ4）
    def unsynced_covers(self):
        return [dict(r) for r in self.conn.execute(
            "select * from covers where synced = 0 order by jacket_no").fetchall()]

    def unsynced_card_links(self):
        # ジャケットを送信済みのものだけ（cards.jacket_no は covers を参照するため）
        return [dict(r) for r in self.conn.execute(
            """select jacket_no, card_no, coalesce(takeaway_at, confirmed_at) as confirmed_at from covers
               where card_no is not null and card_synced = 0 and synced = 1 order by jacket_no""").fetchall()]

    def mark_cover_synced(self, jacket_no, url):
        self.conn.execute("update covers set synced = 1, remote_image_url = ? where jacket_no = ?", (url, jacket_no))

    def mark_card_synced(self, jacket_no):
        self.conn.execute("update covers set card_synced = 1 where jacket_no = ?", (jacket_no,))

    def sync_status(self):
        r = self.conn.execute(
            """select count(*) filter (where synced = 0),
                      count(*) filter (where card_no is not null and card_synced = 0) from covers""").fetchone()
        return {"covers_pending": r[0], "cards_pending": r[1]}

    # ------------------------------------------------------------ ギャラリー
    def gallery_play_started(self, jacket_no):
        cur = self.conn.execute("insert into gallery_plays (jacket_no, started_at) values (?, ?)",
                                (jacket_no, now_iso()))
        return cur.lastrowid

    def gallery_play_ended(self, play_id):
        self.conn.execute("update gallery_plays set ended_at = ? where id = ? and ended_at is null",
                          (now_iso(), play_id))

    def gallery_event(self, play_id, action, position):
        self.conn.execute("insert into gallery_events (play_id, at, action, position) values (?, ?, ?, ?)",
                          (play_id, now_iso(), action, None if position is None else round(float(position), 2)))

    # ------------------------------------------------------------ 書き出し
    TABLES = ("covers", "cover_attempts", "sessions", "gallery_plays", "gallery_events")

    def rows(self, table):
        if table not in self.TABLES:
            raise ValueError(table)
        cur = self.conn.execute(f"select * from {table}")
        return [d[0] for d in cur.description], cur.fetchall()

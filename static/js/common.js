// /desk と /display の共通処理
const CFG = JSON.parse(document.getElementById("config").textContent);

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  let data = null;
  try { data = await res.json(); } catch (_) { /* noop */ }
  return { ok: res.ok, data };
}

// 1´04” 形式
function fmtTime(sec) {
  if (sec == null || !isFinite(sec)) return "-´--”";
  sec = Math.max(0, Math.floor(sec));
  return `${Math.floor(sec / 60)}´${String(sec % 60).padStart(2, "0")}”`;
}

function fmtNo(no, digits) {
  return "No." + String(no).padStart(digits ?? CFG.numbering.jacket_digits, "0");
}

function escapeHTML(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function setSeekPct(el, value, max) {
  el.style.setProperty("--pct", max ? `${(value / max) * 100}%` : "0%");
}

/**
 * 音声の同期。音を鳴らす画面（owner）は1つだけ。
 * - owner の画面：サーバーの playing / seek_seq に合わせて <audio> を操作し、再生位置を報告する
 * - それ以外の画面：鳴らさない
 */
class AudioSync {
  constructor(me) {
    this.me = me;
    this.el = new Audio(CFG.track.audio_url);
    this.el.preload = "auto";
    this.lastSeek = null;
    this.ended = false;
    this.holdUntil = 0; // 手元で操作した直後は、古いポーリング結果で上書きしない
    this.el.addEventListener("ended", () => { this.ended = true; });
  }

  isOwner(state) { return state.audio.owner === this.me; }

  apply(state) {
    const a = state.audio;
    if (a.owner !== this.me) {
      if (!this.el.paused) this.el.pause();
      this.lastSeek = a.seek_seq;
      return;
    }
    if (Date.now() < this.holdUntil) return;
    if (this.lastSeek !== a.seek_seq) {
      this.lastSeek = a.seek_seq;
      this.seekLocal(a.seek_to);
    }
    if (a.range_end != null && this.el.currentTime >= a.range_end) this.ended = true;
    if (a.playing && this.el.paused && !this.ended) this.el.play().catch(() => {});
    if (!a.playing && !this.el.paused) this.el.pause();
  }

  seekLocal(t) {
    try { this.el.currentTime = t; } catch (_) { /* メタデータ未読込 */ }
    this.ended = false;
  }

  // ポーリングで送る報告
  report(state) {
    if (!state || state.audio.owner !== this.me) return {};
    const r = {
      position: this.el.currentTime,
      duration: isFinite(this.el.duration) ? this.el.duration : null,
      playing: !this.el.paused,
      ended: this.ended,
    };
    if (this.ended) { this.ended = false; this.el.pause(); }
    return r;
  }

  duration(state) {
    if (isFinite(this.el.duration)) return this.el.duration;
    return state?.audio.duration ?? null;
  }

  position(state) {
    return this.isOwner(state) ? this.el.currentTime : state.audio.position;
  }

  // 操作（owner が自分なら即時に反映してからサーバーへ）
  async command(state, action, value) {
    if (state && this.isOwner(state)) {
      this.holdUntil = Date.now() + 800;
      if (action === "play") this.el.play().catch(() => {});
      if (action === "pause") this.el.pause();
      if (action === "seek") this.seekLocal(value);
      if (action === "skip") this.seekLocal(this.el.currentTime + value);
    }
    const res = await postJSON(`/api/audio/${action}`, { value });
    if (res.data?.state) this.lastSeek = res.data.state.audio.seek_seq;
    return res;
  }
}

// ポーリングループ
function startPolling(client, audio, onState) {
  let state = null;
  async function tick() {
    try {
      const res = await postJSON("/api/poll", { client, ...audio.report(state) });
      if (res.ok) {
        state = res.data;
        audio.apply(state);
        onState(state);
      }
    } catch (_) { /* サーバー再起動中など。次の周期で再試行 */ }
    setTimeout(tick, CFG.poll_interval_ms);
  }
  tick();
  return () => state;
}

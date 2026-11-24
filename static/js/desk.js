// 机のモニター（/desk）
const audio = new AudioSync("desk");
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

let current = null;         // 最新の状態
let stateAt = 0;            // current を受け取った時刻（ms）
let lastScreen = null;
let coversRev = -1;
let covers = [];
let exIndex = 0;
let dragging = null;        // ドラッグ中の再生バー

$$(".track-title").forEach((el) => (el.textContent = CFG.track.title));

// ------------------------------------------------------------ 操作
async function act(action, body) {
  const res = await postJSON(`/api/desk/${action}`, body);
  if (res.data?.state) applyState(res.data.state);
  return res;
}

document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-action]");
  if (!el || el.disabled) return;
  act(el.dataset.action);
});

$("#btn-generate").addEventListener("click", async () => {
  const text = $("#input").value.trim();
  if (!text) return;
  $("#input-error").textContent = "";
  const res = await act("generate", { input: text, position: audio.el.currentTime });
  if (!res.ok) $("#input-error").textContent = res.data?.state?.session?.notice || "もう一度お試しください。";
});

$("#input").addEventListener("input", updateInputState);
function updateInputState() {
  const len = $("#input").value.trim().length;
  const over = len > CFG.max_chars;
  $("#count").textContent = `${len} / ${CFG.max_chars}`;
  $("#count").classList.toggle("over", over);
  $("#btn-generate").disabled = len === 0 || over;
}

// 作成例カルーセル
function renderExamples() {
  const s = CFG.samples;
  if (!s.length) return;
  const at = (i) => s[(i + s.length) % s.length];
  $(".ex-main").src = at(exIndex).image_url;
  $(".ex-prev").src = at(exIndex - 1).image_url;
  $(".ex-next").src = at(exIndex + 1).image_url;
  $(".ex-text").textContent = at(exIndex).text;
}
$("#ex-prev").addEventListener("click", () => { exIndex--; renderExamples(); });
$("#ex-next").addEventListener("click", () => { exIndex++; renderExamples(); });
renderExamples();

// 再生バー：D3 は机が鳴らす。D10 は大型モニターの再生を操作する
function bindSeek(input) {
  input.addEventListener("input", () => { dragging = input; setSeekPct(input, +input.value, +input.max); });
  input.addEventListener("change", () => {
    audio.command(current, "seek", +input.value);
    dragging = null;
  });
}
bindSeek($("#d3-player .seek"));
bindSeek($("#np-seek"));

$("#d3-player .play-btn").addEventListener("click", () => {
  audio.command(current, audio.el.paused ? "play" : "pause");
});
$("#np-play").addEventListener("click", () => {
  audio.command(current, current?.audio.playing ? "pause" : "play");
});
$$("[data-skip]").forEach((b) => b.addEventListener("click", () => audio.command(current, "skip", +b.dataset.skip)));
$$("[data-audio]").forEach((b) => b.addEventListener("click", () => audio.command(current, b.dataset.audio)));

// ------------------------------------------------------------ 描画
function screenGroup(screen) {
  if (screen === "D1" || screen === "D2") return screen;
  if (screen === "D9" || screen === "D10") return "gallery";
  return "make";
}

function applyState(state) {
  current = state;
  stateAt = performance.now();
  render(state);
}

function render(state) {
  const screen = state.desk.screen;
  const modal = state.desk.modal;
  const changed = screen !== lastScreen;

  $$(".screen").forEach((el) => el.classList.toggle("active", el.id === screenGroup(screen)));
  $$(".step").forEach((el) => el.classList.toggle("active", el.id === screen));
  const tab = screen.startsWith("D6") || screen.startsWith("D7") ? "D6" : screen;
  $$(".tab").forEach((el) => el.classList.toggle("active", el.dataset.tab === tab));
  $(".d3-only").classList.toggle("hidden", screen !== "D3");
  $(".home-link").classList.toggle("hidden", screen === "D7a" || screen === "D7b");

  const idle = ["D1", "D2", "D9"].includes(screen);
  $("#hamburger").classList.toggle("show", idle && modal !== "menu");
  $("#menu").classList.toggle("hidden", modal !== "menu");
  $("#menu-home").classList.toggle("hidden", screen === "D1");
  $("#abort").classList.toggle("hidden", modal !== "abort");

  const s = state.session;
  if (changed && screen === "D3") {
    $("#input").value = s?.input || "";
    $("#input-error").textContent = s?.notice || "";
    updateInputState();
    setTimeout(() => $("#input").focus(), 50);
  }
  if (screen === "D4" && s) {
    $("#D4 .session-input").textContent = s.input;
    const err = s.status === "error";
    $("#gen-error").classList.toggle("hidden", !err);
    $("#countdown").classList.toggle("hidden", err);
    $(".pressing").classList.toggle("failed", err);
  }
  if (screen === "D5" && s) {
    if ($("#d5-img").getAttribute("src") !== s.image_url) $("#d5-img").src = s.image_url;
    $("#d5-input").textContent = s.image_input;
  }
  if (screen === "D6") {
    const none = state.cards_left <= 0;
    $("#choice-card").disabled = none;
    $("#choice-card .sold-out").classList.toggle("hidden", !none);
  }
  if (changed && screen === "D7a" && state.result) {
    $("#qr").src = "/api/qr?data=" + encodeURIComponent(state.result.mobile_url);
  }
  if (screen === "D7b" && state.result?.card_no != null) {
    const no = fmtNo(state.result.card_no, CFG.numbering.card_digits);
    $("#card-no-head").textContent = no;
    $("#card-no-figure").textContent = no;
  }
  if ((screen === "D9" || screen === "D10") && state.covers_rev !== coversRev) {
    coversRev = state.covers_rev;
    loadCovers();
  }
  $("#D10").classList.toggle("hidden", screen !== "D10");
  if (screen === "D10" && state.display.cover) {
    const c = state.display.cover;
    if ($("#np-img").getAttribute("src") !== c.image_url) $("#np-img").src = c.image_url;
    $("#np-input").textContent = c.input;
    $("#np-no").textContent = fmtNo(c.jacket_no);
    $("#np-fav").disabled = c.favorite_sec == null;
  }
  lastScreen = screen;
}

async function loadCovers() {
  const res = await fetch("/api/covers");
  covers = await res.json();
  const grid = $("#gallery-grid");
  grid.innerHTML = covers.map((c) => `
    <button class="g-item" data-jacket="${c.jacket_no}">
      <img class="g-img cover" src="${escapeHTML(c.image_url)}" alt="" loading="lazy">
      <span class="g-no">${fmtNo(c.jacket_no)}</span>
    </button>`).join("");
  $("#gallery-empty").classList.toggle("hidden", covers.length > 0);
}
$("#gallery-grid").addEventListener("click", (e) => {
  const item = e.target.closest("[data-jacket]");
  if (item) act("gallery_select", { jacket_no: +item.dataset.jacket });
});

// 毎フレーム：再生バーとカウントダウン
function frame() {
  const st = current;
  if (st) {
    const screen = st.desk.screen;
    if (screen === "D3") {
      const dur = audio.duration(st);
      const pos = audio.el.currentTime;
      const seek = $("#d3-player .seek");
      seek.max = dur || 0;
      if (dragging !== seek) { seek.value = pos; setSeekPct(seek, pos, dur); }
      $("#d3-player .pos").textContent = fmtTime(dragging === seek ? +seek.value : pos);
      $("#d3-player .dur").textContent = fmtTime(dur);
      $("#d3-player .play-btn").classList.toggle("playing", !audio.el.paused);
    }
    if (screen === "D10") {
      const a = st.audio;
      const dur = audio.duration(st);
      // 大型モニターからの報告（0.5秒ごと）の間を補間する
      let pos = a.position + (a.playing ? (performance.now() - stateAt) / 1000 : 0);
      if (dur) pos = Math.min(pos, dur);
      const seek = $("#np-seek");
      seek.max = dur || 0;
      if (dragging !== seek) { seek.value = pos; setSeekPct(seek, pos, dur); }
      $("#np-pos").textContent = fmtTime(dragging === seek ? +seek.value : pos);
      $("#np-dur").textContent = fmtTime(dur);
      $("#np-play").classList.toggle("playing", a.playing);
    }
    if (screen === "D4" && st.session?.status === "generating") {
      const s = st.session;
      const elapsed = st.now - s.gen_started_at + (performance.now() - stateAt) / 1000;
      const remain = Math.max(0, Math.ceil(s.estimate_sec - elapsed));
      $("#remain").textContent = String(remain).padStart(2, "0");
    }
  }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

startPolling("desk", audio, (state) => {
  // ポーリング結果は、操作直後の応答より古いことがあるため時刻で判断せず常に反映する
  applyState(state);
});

// 大型モニター（/display）
const audio = new AudioSync("display");
const $ = (sel) => document.querySelector(sel);
document.querySelectorAll(".track-title").forEach((el) => (el.textContent = CFG.track.title));

let current = null;
let stateAt = 0;
let coversRev = -1;
let s2Image = null;

// 自動再生が拒否されたとき（キオスクの --autoplay-policy 指定漏れなど）の保険
audio.el.addEventListener("play", () => $("#unlock").classList.add("hidden"));
$("#unlock").addEventListener("click", () => { audio.el.play().catch(() => {}); });

function render(state) {
  const screen = state.display.screen;
  $("#S1").classList.toggle("active", screen === "S1");
  $("#S2").classList.toggle("active", screen === "S2");
  if (screen === "S1" && state.covers_rev !== coversRev) {
    coversRev = state.covers_rev;
    loadCovers();
  }
  if (screen === "S2" && state.display.cover) {
    const c = state.display.cover;
    if (s2Image !== c.image_url) {
      s2Image = c.image_url;
      $("#s2-img").src = c.image_url;
      $("#cd-label").style.backgroundImage = `url("${c.image_url}")`;
    }
    $("#s2-no").textContent = fmtNo(c.jacket_no);
  }
  const wantsPlay = state.audio.owner === "display" && state.audio.playing;
  $("#unlock").classList.toggle("hidden", !(wantsPlay && audio.el.paused && audio.el.readyState >= 2));
}

async function loadCovers() {
  const res = await fetch("/api/covers");
  const covers = await res.json(); // 新しい順
  $("#empty").classList.toggle("hidden", covers.length > 0);
  const now = Date.now() / 1000;
  const isNew = (c) => now - c.confirmed_at < CFG.highlight_new_sec;
  const fresh = covers.filter(isNew);

  // 2段に振り分け。新しいジャケットは各段に何度も入れて目立たせる
  const rows = [[], []];
  covers.forEach((c, i) => rows[i % 2].push(c));
  const build = (list) => {
    if (!list.length) list = covers.slice();
    if (!list.length) return [];
    let seq = [];
    list.forEach((c, i) => {
      seq.push(c);
      if (fresh.length && i % 3 === 2) seq.push(fresh[(i / 3 | 0) % fresh.length]);
    });
    if (fresh.length) seq.unshift(fresh[0]);
    while (seq.length < 6) seq = seq.concat(seq); // 画面幅を埋める
    return seq;
  };
  [rows[0], rows[1]].forEach((list, r) => {
    const seq = build(list);
    const html = seq.map((c) => `
      <div class="tile${isNew(c) ? " new" : ""}">
        <img src="${escapeHTML(c.image_url)}" alt="">
        <span class="t-no">${fmtNo(c.jacket_no)}</span>
      </div>`).join("");
    const track = $(r === 0 ? "#row1" : "#row2");
    track.innerHTML = html + html; // 2回並べて継ぎ目なくループ
    track.style.animationDuration = `${Math.max(seq.length, 6) * (r === 0 ? 9 : 11)}s`;
  });
}

function frame() {
  const st = current;
  if (st && st.display.screen === "S2") {
    const dur = audio.duration(st);
    const pos = audio.isOwner(st) ? audio.el.currentTime : st.audio.position;
    const pct = dur ? Math.min(100, (pos / dur) * 100) : 0;
    $("#bar-fill").style.width = pct + "%";
    $("#bar-knob").style.left = pct + "%";
    $("#s2-pos").textContent = fmtTime(pos);
    $("#s2-dur").textContent = fmtTime(dur);
    const playing = !audio.el.paused;
    $("#s2-play").classList.toggle("playing", playing);
    $("#cd").classList.toggle("spinning", playing);
  }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

startPolling("display", audio, (state) => {
  current = state;
  stateAt = performance.now();
  render(state);
});

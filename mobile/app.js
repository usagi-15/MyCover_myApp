// スマホ用ページ：?t=<token>（Get It Now）／ ?c=<card_token>（カード）で表示を切り替える
(function () {
  const C = window.MYCOVER;
  const $ = (id) => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const token = params.get("t");
  const cardToken = params.get("c");

  const show = (id) => {
    ["loading", "m1", "m2", "error"].forEach((s) => $(s).classList.toggle("hidden", s !== id));
  };
  const pad = (n, d) => String(n).padStart(d, "0");
  const fmt = (sec) => {
    if (sec == null || !isFinite(sec)) return "-´--”";
    sec = Math.max(0, Math.floor(sec));
    return `${Math.floor(sec / 60)}´${pad(sec % 60, 2)}”`;
  };
  const headers = { apikey: C.publishableKey, "Content-Type": "application/json" };

  async function rpc(name, args) {
    const res = await fetch(`${C.supabaseUrl}/rest/v1/rpc/${name}`, {
      method: "POST", headers, body: JSON.stringify(args),
    });
    if (!res.ok) throw new Error(`rpc ${name}: ${res.status}`);
    return res.json();
  }

  // アクセスの記録（再訪の分析用）。個人を特定する情報は送らない。失敗しても表示は続ける
  function logView(kind) {
    const body = kind === "card" ? { kind, card_token: cardToken } : { kind, token };
    fetch(`${C.supabaseUrl}/rest/v1/page_views`, {
      method: "POST", headers: { ...headers, Prefer: "return=minimal" }, body: JSON.stringify(body), keepalive: true,
    }).catch(() => {});
  }

  function fillInfo(el) {
    el.innerHTML = "";
    C.exhibition.forEach((line) => {
      const div = document.createElement("div");
      div.textContent = line;
      el.appendChild(div);
    });
  }

  function showError(message) {
    $("error-msg").textContent = message;
    fillInfo($("info-error"));
    show("error");
  }

  function showCover(cover) {
    $("no").textContent = "No." + pad(cover.jacket_no, C.jacketDigits);
    $("jacket").src = cover.image_url;
    $("prompt").textContent = cover.prompt;
    $("track-title").textContent = C.track.title;
    $("artist").textContent = C.track.artist;
    setupPlayer();
    show("m1");
  }

  function showUnlinkedCard(card) {
    $("no").textContent = "Card No." + pad(card.card_no, C.cardDigits);
    fillInfo($("info"));
    show("m2");
  }

  function setupPlayer() {
    const audio = new Audio(C.track.mp3);
    audio.preload = "metadata";
    const seek = $("seek");
    const dl = $("download");
    dl.href = C.track.mp3;
    dl.setAttribute("download", `${C.track.title}.mp3`);
    let dragging = false;
    const update = () => {
      const d = audio.duration;
      seek.max = isFinite(d) ? d : 0;
      if (!dragging) seek.value = audio.currentTime;
      seek.style.setProperty("--pct", isFinite(d) && d ? `${(seek.value / d) * 100}%` : "0%");
      $("pos").textContent = fmt(+seek.value);
      $("dur").textContent = fmt(d);
      $("play").classList.toggle("playing", !audio.paused);
    };
    ["timeupdate", "loadedmetadata", "play", "pause", "ended"].forEach((ev) => audio.addEventListener(ev, update));
    audio.addEventListener("error", () => {
      // TODO: MP3 を置くまでは「準備中」
      $("dur").textContent = "準備中";
      $("play").disabled = true;
      dl.classList.add("disabled");
      dl.textContent = "Download (MP3)（準備中）";
    });
    $("play").addEventListener("click", () => (audio.paused ? audio.play() : audio.pause()));
    seek.addEventListener("input", () => { dragging = true; update(); });
    seek.addEventListener("change", () => { audio.currentTime = +seek.value; dragging = false; update(); });
    update();
  }

  async function loadByToken() {
    logView("get_it_now");
    // 確定直後は展示PCからの送信が届いていないことがあるので、少し待って何度か試す
    for (let i = 0; i < 12; i++) {
      const rows = await rpc("get_cover_by_token", { p_token: token });
      if (rows.length) return showCover(rows[0]);
      $("loading-msg").textContent = "ジャケットを準備しています…\nそのまましばらくお待ちください。";
      await new Promise((r) => setTimeout(r, 3000));
    }
    showError("ジャケットが見つかりませんでした。\n時間をおいてから、もう一度読み込んでください。");
  }

  async function loadByCard() {
    logView("card");
    const rows = await rpc("get_card", { p_card_token: cardToken });
    if (!rows.length) return showError("このカードは見つかりませんでした。\nURL をもう一度確認してください。");
    const card = rows[0];
    if (!card.linked) return showUnlinkedCard(card);
    showCover(card);
  }

  if (C.authorUrl) {
    $("author").href = C.authorUrl;
    $("author").classList.remove("hidden");
  }
  $("loading-msg").style.whiteSpace = "pre-line";
  $("error-msg").style.whiteSpace = "pre-line";

  const run = token ? loadByToken : cardToken ? loadByCard : null;
  if (!run) {
    showError("『My Cover』は、デザイン情報学科３年ゼミ展で展示している作品です。\n会場の QR コードやカードからアクセスしてください。");
    return;
  }
  run().catch(() => showError("読み込みに失敗しました。\n電波の良いところで、もう一度読み込んでください。"));
})();

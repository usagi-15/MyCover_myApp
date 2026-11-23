// 1920×1080 の画面をウィンドウサイズに合わせて拡大縮小する
(function () {
  const stage = document.getElementById("stage");
  function fit() {
    const s = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    stage.style.transform = `translate(-50%, -50%) scale(${s})`;
  }
  window.addEventListener("resize", fit);
  fit();
})();

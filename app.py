"""『My Cover』展示アプリ（Flask サーバー）。起動：python app.py"""
import io
import json
import logging

import qrcode
from flask import Flask, abort, jsonify, render_template, request, send_from_directory

from mycover.config import DATA_DIR, ROOT, STATIC_DIR, load_config, load_samples
from mycover.dummy_assets import ensure_dummy_assets
from mycover.generator import resolve_backend
from mycover.state import ActionError, Exhibit

cfg = load_config()
dummy = ensure_dummy_assets()
exhibit = Exhibit(cfg)

app = Flask(__name__)


def client_config():
    """画面側に渡す設定（秘密情報は含めない）。"""
    track = dict(cfg["track"])
    audio_path = STATIC_DIR / track["audio_url"].removeprefix("/static/")
    if not audio_path.exists():
        track["audio_url"] = dummy["audio_url"]
        track["is_dummy_audio"] = True
    samples = [
        {"image_url": "/static/" + s["image"], "text": s["text"]} for s in load_samples()
    ] or dummy["samples"]
    return {
        "track": track,
        "poll_interval_ms": cfg["poll_interval_ms"],
        "numbering": cfg["numbering"],
        "max_chars": cfg["input"]["max_chars"],
        "highlight_new_sec": cfg["display"]["highlight_new_sec"],
        "samples": samples,
    }


@app.route("/")
def index():
    return '<p><a href="/desk">/desk</a>（机のモニター） / <a href="/display">/display</a>（大型モニター）</p>'


@app.route("/desk")
def desk():
    return render_template("desk.html", config_json=json.dumps(client_config(), ensure_ascii=False))


@app.route("/display")
def display():
    return render_template("display.html", config_json=json.dumps(client_config(), ensure_ascii=False))


MOBILE_DIR = ROOT / "mobile"


@app.route("/m/")
@app.route("/m/<path:filename>")
def mobile(filename="index.html"):
    """スマホ用ページ（GitHub Pages に置くものと同じ mobile/）を開発中に PC からも配信する。"""
    if filename == cfg["track"].get("mobile_mp3", "B7F.mp3") and not (MOBILE_DIR / filename).exists():
        return send_from_directory(STATIC_DIR / "audio", filename)
    return send_from_directory(MOBILE_DIR, filename)


@app.route("/media/<path:filename>")
def media(filename):
    return send_from_directory(DATA_DIR, filename)


@app.post("/api/poll")
def api_poll():
    body = request.get_json(silent=True) or {}
    client = body.get("client")
    if client in ("desk", "display") and "position" in body:
        exhibit.report(client, body.get("position"), body.get("duration"),
                       body.get("playing"), body.get("ended", False))
    return jsonify(exhibit.snapshot())


@app.get("/api/covers")
def api_covers():
    return jsonify(exhibit.public_covers())


@app.post("/api/desk/<action>")
def api_desk(action):
    try:
        exhibit.desk_action(action, request.get_json(silent=True))
    except ActionError as e:
        return jsonify({"ok": False, "error": str(e), "state": exhibit.snapshot()}), 409
    return jsonify({"ok": True, "state": exhibit.snapshot()})


@app.post("/api/audio/<action>")
def api_audio(action):
    body = request.get_json(silent=True) or {}
    try:
        exhibit.audio_action(action, body.get("value"))
    except ActionError as e:
        return jsonify({"ok": False, "error": str(e)}), 409
    return jsonify({"ok": True, "state": exhibit.snapshot()})


@app.get("/api/qr")
def api_qr():
    data = request.args.get("data", "")
    if not data or len(data) > 500:
        abort(400)
    img = qrcode.make(data, border=2)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue(), 200, {"Content-Type": "image/png", "Cache-Control": "no-store"}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # 0.5秒ごとのポーリングで窓が埋まらないよう、リクエストごとのログは出さない（エラーは出る）
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    backend = resolve_backend(cfg)
    print(f"[My Cover] 画像生成：{backend}"
          + (f"（モデル {cfg['openai']['model']} / 品質 {cfg['openai']['quality']}）" if backend == "openai"
             else "（ダミー。OpenAI を使うには API キーを設定）"))
    exhibit.sync.start()
    print("[My Cover] クラウド（Supabase）への送信：" + ("有効" if exhibit.sync.client.enabled else "未設定（set_supabase_key.bat で設定）"))
    print(f"[My Cover] 起動しました：http://{cfg['server']['host']}:{cfg['server']['port']}/desk と /display を開いてください")
    print("[My Cover] この窓を閉じるとサーバーが止まります。生成の結果はここに表示されます")
    app.run(host=cfg["server"]["host"], port=cfg["server"]["port"], threaded=True, debug=False)

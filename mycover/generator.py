"""画像生成と入力チェック。

- backend "openai"：OpenAI の画像生成API（GPT Image）＋ モデレーションAPI
- backend "dummy" ：Pillow で仮画像を作る（API キーが無い開発時用）
- backend "auto"  ：API キーがあれば openai、無ければ dummy

送るプロンプト = 固定プロンプト（prompts/base_prompt.txt）
              ＋ タイトルの指示（title_mode が "ai" のときだけ prompts/title_ai.txt）
              ＋ 鑑賞者の入力
"""
import base64
import io
import json
import logging
import os
import time
import unicodedata
import uuid

from PIL import Image, ImageDraw, ImageFont

from .config import CONFIG_DIR, DATA_DIR, ROOT
from .dummy_assets import make_cover_image

IMAGES_DIR = DATA_DIR / "images"
PROMPTS_DIR = ROOT / "prompts"
log = logging.getLogger("mycover.generator")


class GenerationError(Exception):
    """API障害・回線断など。D4 で「もう一度試す／言葉を変える」を出す。"""


class InputRejected(Exception):
    """入力が NGワード・モデレーションに引っかかった。D3 に戻して書き直してもらう。"""


REJECT_MESSAGE = "ごめんなさい、その言葉ではジャケットをつくれませんでした。別の言い方で書きなおしてみてください。"


# ------------------------------------------------------------------ 設定・秘密情報
def load_api_key():
    """環境変数 OPENAI_API_KEY か、Git管理外の config/secrets.json から読む。"""
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key.strip()
    path = CONFIG_DIR / "secrets.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return (json.load(f).get("openai_api_key") or "").strip() or None
    return None


def resolve_backend(cfg):
    backend = cfg["generation"]["backend"]
    if backend == "auto":
        return "openai" if load_api_key() else "dummy"
    return backend


_client = None


def _openai_client(cfg):
    global _client
    if _client is None:
        from openai import OpenAI  # 起動時に API キーが無くても動くよう遅延読み込み

        key = load_api_key()
        if not key:
            raise GenerationError("OpenAI API キーが設定されていません")
        o = cfg["openai"]
        _client = OpenAI(api_key=key, timeout=o["timeout_sec"], max_retries=o["max_retries"])
    return _client


# ------------------------------------------------------------------ 入力チェック
def _normalize(text):
    return unicodedata.normalize("NFKC", text).lower()


def load_ng_words():
    path = CONFIG_DIR / "ng_words.txt"
    if not path.exists():
        return []
    words = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                words.append(_normalize(line))
    return words


def check_input_local(cfg, text):
    """すぐに判定できるチェック（文字数・NGワード）。問題があればメッセージを返す。"""
    if not text:
        return "言葉を入力してください。"
    if len(text) > cfg["input"]["max_chars"]:
        return f"{cfg['input']['max_chars']}文字以内で入力してください。"
    norm = _normalize(text)
    if any(w in norm for w in load_ng_words()):
        return REJECT_MESSAGE
    return None


def moderate(cfg, text):
    """OpenAI のモデレーションAPI。引っかかったら InputRejected。"""
    if resolve_backend(cfg) != "openai" or not cfg["openai"]["use_moderation"]:
        return
    try:
        res = _openai_client(cfg).moderations.create(model=cfg["openai"]["moderation_model"], input=text)
    except Exception as e:  # noqa: BLE001
        raise GenerationError(f"moderation failed: {e}") from e
    if any(r.flagged for r in res.results):
        raise InputRejected(REJECT_MESSAGE)


# ------------------------------------------------------------------ プロンプト
def _read_prompt(name):
    path = PROMPTS_DIR / name
    if not path.exists():
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def build_prompt(cfg, text):
    parts = [_read_prompt("base_prompt.txt")]
    if cfg["generation"]["title_mode"] == "ai":
        parts.append(_read_prompt("title_ai.txt").replace("{title}", cfg["track"]["title"]))
    parts.append("鑑賞者の言葉：\n" + text)
    return "\n\n".join(p for p in parts if p)


# ------------------------------------------------------------------ 生成
def generate(cfg, text, attempt_index):
    """画像ファイルを作り、(ファイル名, 生成秒数) を返す。

    失敗時：InputRejected（書き直してもらう）／ GenerationError（もう一度試す）
    """
    started = time.monotonic()
    name = f"{uuid.uuid4().hex}.jpg"
    backend = resolve_backend(cfg)

    if backend == "dummy":
        time.sleep(cfg["generation"]["dummy_delay_sec"])
        if text.strip().lower() == "#fail":  # 失敗時の画面確認用
            raise GenerationError("dummy failure")
        if text.strip().lower() == "#ng":  # 書き直しのお願いの画面確認用
            raise InputRejected(REJECT_MESSAGE)
        ai_title = cfg["track"]["title"] if cfg["generation"]["title_mode"] == "ai" else None
        img = make_cover_image(None, text, seed=hash(text) % 1000 + attempt_index, title=ai_title)
    elif backend == "openai":
        moderate(cfg, text)
        img = _generate_openai(cfg, text)
    else:
        raise GenerationError(f"未対応のバックエンド: {backend}")

    if cfg["generation"]["title_mode"] == "overlay":
        img = overlay_title(cfg, img)
    _save_jpeg(img, IMAGES_DIR / name)
    return name, time.monotonic() - started


def _generate_openai(cfg, text):
    from openai import APIConnectionError, APIStatusError, APITimeoutError, BadRequestError

    o = cfg["openai"]
    params = {
        "model": o["model"],
        "prompt": build_prompt(cfg, text),
        "size": o["size"],
        "quality": o["quality"],
        "output_format": "jpeg",
        "output_compression": o["output_compression"],
        "n": 1,
    }
    try:
        res = _openai_client(cfg).images.generate(**params)
    except BadRequestError as e:
        # 安全上の理由で生成を断られた場合は、言葉を変えてもらう
        code = (getattr(e, "code", None) or "")
        body = str(e).lower()
        if code in ("moderation_blocked", "content_policy_violation") or "safety" in body or "moderation" in body:
            log.info("image request rejected by safety system: %s", code)
            raise InputRejected(REJECT_MESSAGE) from e
        log.error("image request failed: %s", e)
        raise GenerationError(f"bad request: {e}") from e
    except (APIConnectionError, APITimeoutError) as e:
        log.warning("network error: %s", e)
        raise GenerationError(f"network: {e}") from e
    except APIStatusError as e:
        log.warning("api error %s: %s", e.status_code, e)
        raise GenerationError(f"api {e.status_code}") from e

    data = res.data[0] if res.data else None
    if not data or not data.b64_json:
        raise GenerationError("画像が返ってきませんでした")
    return Image.open(io.BytesIO(base64.b64decode(data.b64_json))).convert("RGB")


def _save_jpeg(img, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "JPEG", quality=92)


# ------------------------------------------------------------------ タイトル（overlay モード）
def overlay_title(cfg, img):
    """title_mode が "overlay" のとき、曲名を固定位置に重ねる。"""
    t = cfg["generation"]["title_overlay"]
    w, h = img.size
    size = max(12, int(h * t["size_ratio"]))
    font = None
    if t.get("font_file"):
        try:
            font = ImageFont.truetype(str(ROOT / t["font_file"]), size)
        except OSError:
            log.warning("title font not found: %s", t["font_file"])
    if font is None:
        for name in ("YuMincho.ttc", "yumin.ttf", "DejaVuSerif.ttf"):
            try:
                font = ImageFont.truetype(name, size)
                break
            except OSError:
                continue
    if font is None:
        font = ImageFont.load_default()
    img = img.copy()
    draw = ImageDraw.Draw(img)
    title = cfg["track"]["title"]
    left, top, right, bottom = draw.textbbox((0, 0), title, font=font)
    tw, th = right - left, bottom - top
    x = int(w * t["x_ratio"] - tw * t["anchor_x"]) - left
    y = int(h * t["y_ratio"] - th * t["anchor_y"]) - top
    draw.text((x, y), title, font=font, fill=tuple(t["color"]))
    return img


def delete_image(name):
    try:
        (IMAGES_DIR / name).unlink()
    except FileNotFoundError:
        pass

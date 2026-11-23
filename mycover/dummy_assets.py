"""開発用のダミー素材（作例ジャケット・音源・生成画像）を作る。本番素材が揃うまでの代用。"""
import math
import struct
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import DATA_DIR

DUMMY_DIR = DATA_DIR / "dummy"

_PALETTES = [
    ((20, 30, 90), (220, 120, 160)),
    ((10, 70, 60), (240, 210, 120)),
    ((60, 20, 70), (120, 200, 230)),
    ((90, 40, 20), (250, 240, 220)),
    ((15, 15, 25), (180, 60, 60)),
]


def _font(size):
    for name in ("YuMincho.ttc", "yumin.ttf", "msmincho.ttc",
                 "NotoSerifCJK-Regular.ttc", "DejaVuSerif.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_cover_image(path: Path, text: str, seed: int, title: str = "B7F", size: int = 1024):
    """入力文と曲名を載せたグラデーション画像（ダミー生成結果）。"""
    top, bottom = _PALETTES[seed % len(_PALETTES)]
    img = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(img)
    for y in range(size):
        t = y / size
        draw.line([(0, y), (size, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    for i in range(6):
        r = (seed * 97 + i * 131) % (size // 3) + 40
        cx = (seed * 53 + i * 211) % size
        cy = (seed * 71 + i * 157) % size
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255), width=2)
    draw.text((60, 60), title, font=_font(140), fill=(255, 255, 255))
    body = (text or "")[:60]
    lines = [body[i:i + 15] for i in range(0, len(body), 15)]
    draw.multiline_text((60, size - 80 - 50 * len(lines)), "\n".join(lines), font=_font(40), fill=(255, 255, 255))
    draw.text((size - 330, size - 50), "DUMMY IMAGE", font=_font(28), fill=(255, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")


def _make_tone(path: Path, seconds: int = 90, rate: int = 22050):
    """開発用の小さな音（実際の曲ではない）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    notes = [261.6, 329.6, 392.0, 523.3]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for n in range(seconds * rate):
            t = n / rate
            freq = notes[int(t // 0.5) % len(notes)]
            env = 1 - (t % 0.5) / 0.5
            frames += struct.pack("<h", int(3000 * env * math.sin(2 * math.pi * freq * t)))
        w.writeframes(bytes(frames))


def ensure_dummy_assets():
    samples = []
    for i in range(3):
        p = DUMMY_DIR / f"sample_{i + 1}.png"
        text = f"（ダミー作例 {i + 1}）TODO: 作例の入力文"
        if not p.exists():
            make_cover_image(p, text, seed=i + 10, size=512)
        samples.append({"image_url": f"/media/dummy/{p.name}", "text": text})
    tone = DUMMY_DIR / "dummy_track.wav"
    if not tone.exists():
        _make_tone(tone)
    return {"samples": samples, "audio_url": "/media/dummy/dummy_track.wav"}

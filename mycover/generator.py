"""画像生成。フェーズ1はダミー（Pillowで画像を作り、待ち時間を再現する）。"""
import time
import uuid

from .config import DATA_DIR
from .dummy_assets import make_cover_image

IMAGES_DIR = DATA_DIR / "images"


class GenerationError(Exception):
    pass


def generate(cfg, text: str, attempt_index: int):
    """画像ファイルを作り、(ファイル名, 生成秒数) を返す。"""
    backend = cfg["generation"]["backend"]
    started = time.monotonic()
    name = f"{uuid.uuid4().hex}.png"
    if backend == "dummy":
        time.sleep(cfg["generation"]["dummy_delay_sec"])
        if text.strip().lower() == "#fail":  # 失敗時の画面確認用
            raise GenerationError("dummy failure")
        make_cover_image(IMAGES_DIR / name, text, seed=hash(text) % 1000 + attempt_index,
                         title=cfg["track"]["title"])
    else:
        raise GenerationError(f"未実装のバックエンド: {backend}（フェーズ2で実装）")
    return name, time.monotonic() - started


def delete_image(name: str):
    try:
        (IMAGES_DIR / name).unlink()
    except FileNotFoundError:
        pass

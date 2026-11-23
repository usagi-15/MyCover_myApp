"""設定の読み込み。config/config.json を config/config.local.json で上書きする。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
STATIC_DIR = ROOT / "static"


def _merge(base, override):
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def load_config():
    with open(CONFIG_DIR / "config.json", encoding="utf-8") as f:
        cfg = json.load(f)
    local = CONFIG_DIR / "config.local.json"
    if local.exists():
        with open(local, encoding="utf-8") as f:
            _merge(cfg, json.load(f))
    return cfg


def load_samples():
    with open(CONFIG_DIR / "samples.json", encoding="utf-8") as f:
        return json.load(f).get("samples", [])

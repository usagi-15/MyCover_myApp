"""画像生成の動作確認・モデル比較用（展示PCや開発PCで実行する）。

使い方（プロジェクトのフォルダで）:
  test_models.bat をダブルクリック（下の --compare と同じ）
  py tools/test_generate.py --compare
  py tools/test_generate.py "深い海の底。一筋の光がさしている。"
  py tools/test_generate.py "深い海の底" --model gpt-image-2.5-flare --quality low
  py tools/test_generate.py "深い海の底" --models gpt-image-2 gpt-image-2.5-sunburst gpt-image-2.5-flare
  py tools/test_generate.py "確認したい言葉" --moderation-only

結果は data/test/ に保存され、かかった時間が表示される。API の利用料金がかかる点に注意。
"""
import argparse
import copy
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mycover import generator  # noqa: E402
from mycover.config import DATA_DIR, load_config  # noqa: E402

DEFAULT_TEXT = "深い海の底。一筋の光がさしている。"
# 比較の候補（openai ライブラリに記載のあるモデルから。使えるかどうかは実行して確認する）
COMPARE_MODELS = ["gpt-image-2", "gpt-image-2.5-sunburst", "gpt-image-2.5-flare"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="?", default=DEFAULT_TEXT, help="鑑賞者の入力を想定した言葉")
    ap.add_argument("--compare", action="store_true", help=f"候補のモデル {COMPARE_MODELS} を順に試す")
    ap.add_argument("--model", help="config の openai.model の代わりに使うモデル")
    ap.add_argument("--models", nargs="+", help="複数のモデルを順に試す")
    ap.add_argument("--quality", help="low / medium / high など")
    ap.add_argument("--title-mode", choices=["ai", "overlay"])
    ap.add_argument("--moderation-only", action="store_true", help="入力チェックだけ行う")
    args = ap.parse_args()

    cfg = load_config()
    cfg["generation"]["backend"] = "openai"
    if not generator.load_api_key():
        print("OpenAI API キーがありません。環境変数 OPENAI_API_KEY か config/secrets.json を設定してください。")
        return 1

    problem = generator.check_input_local(cfg, args.text)
    if problem:
        print("ローカルのチェックで止まりました：", problem)
        return 0
    if args.moderation_only:
        try:
            generator.moderate(cfg, args.text)
            print("モデレーション：問題なし")
        except generator.InputRejected:
            print("モデレーション：引っかかりました（D3 で書き直しをお願いする対象）")
        return 0

    if args.title_mode:
        cfg["generation"]["title_mode"] = args.title_mode
    print("---- 送るプロンプト ----")
    print(generator.build_prompt(cfg, args.text))
    print("------------------------")

    out_dir = DATA_DIR / "test"
    out_dir.mkdir(parents=True, exist_ok=True)
    generator.IMAGES_DIR = out_dir
    models = COMPARE_MODELS if args.compare else (args.models or [args.model or cfg["openai"]["model"]])
    results = []
    for model in models:
        print(f"{model} で生成中…（1〜2分かかることがあります）", flush=True)
        c = copy.deepcopy(cfg)
        c["openai"]["model"] = model
        if args.quality:
            c["openai"]["quality"] = args.quality
        started = time.monotonic()
        try:
            name, sec = generator.generate(c, args.text, 0)
            stamped = out_dir / f"{time.strftime('%H%M%S')}_{model}_{c['openai']['quality']}.jpg"
            (out_dir / name).rename(stamped)
            line = f"[OK]   {model} / {c['openai']['quality']}: {sec:.1f} 秒 → {stamped.name}"
        except generator.InputRejected as e:
            line = f"[書き直し] {model}: {e}"
        except generator.GenerationError as e:
            line = f"[失敗] {model}: {e}（{time.monotonic() - started:.1f} 秒）"
        print(line, flush=True)
        results.append(line)
        if "API キーが正しくありません" in line:
            print("API キーの問題のため、残りのモデルは試さずに終了します。")
            break
    print()
    print("===== 結果のまとめ（この部分をコピーして共有してください。API キーは含まれません） =====")
    for line in results:
        print(line)
    print(f"画像の保存先：{out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

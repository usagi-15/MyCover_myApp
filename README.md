# 『My Cover』展示アプリ

音楽コンテンツにおけるオーディエンス・ジャーニーの設計（武蔵野美術大学 デザイン情報学科3年 大石ゼミ／池田うさぎ）の展示用アプリ。
仕様は `notes/実装指示書.md`・`notes/仕様.md`、進捗は `notes/進捗.md` を参照。

## 必要なもの

- Windows 11 / Python 3（python.org版）/ Google Chrome
- Python ライブラリ：`openai`, `Pillow`, `qrcode`, `Flask`（これ以外は使わない）

```bat
py -m pip install -r requirements.txt
```

## 開発中の起動（フェーズ1）

```bat
py app.py
```

Chrome で次の2つを開く（1台のモニターで試すときは別ウィンドウで並べる）。

- 机のモニター：http://127.0.0.1:5000/desk
- 大型モニター：http://127.0.0.1:5000/display

自動再生を許可するため、確認用の Chrome は次のように起動すると楽です（本番用の起動 `.bat` はフェーズ5で用意）。

```bat
"C:\Program Files\Google\Chrome\Application\chrome.exe" --autoplay-policy=no-user-gesture-required --user-data-dir=%TEMP%\mycover-chrome http://127.0.0.1:5000/display
```

## フォルダ構成

```
app.py                 Flask サーバー（入口）
mycover/               サーバー側の処理（状態管理・生成・設定）
templates/             /desk /display の HTML
static/css, static/js  画面のスタイルと動き
static/audio/B7F.mp3   楽曲（未配置。無い間は開発用ダミー音源）
static/fonts/          フォントファイル（未配置）
config/config.json     設定（展示PC固有の値は config/config.local.json で上書き。Git管理外）
config/samples.json    作成例カルーセル
config/ng_words.txt    NGワード
prompts/base_prompt.txt 固定プロンプト
data/                  生成画像などの実行時データ（Git管理外）
notes/                 仕様・進捗
```

## 開発用メモ

- 入力欄に `#fail` と入れて生成すると、生成失敗時の画面（D4）を確認できる（ダミー生成時のみ）。
- 確定したジャケットはフェーズ1ではメモリ上だけに保存されるため、サーバーを再起動すると消える（フェーズ3で SQLite に保存）。

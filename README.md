# 『My Cover』展示アプリ

音楽コンテンツにおけるオーディエンス・ジャーニーの設計（武蔵野美術大学 デザイン情報学科3年 大石ゼミ／池田うさぎ）の展示用アプリ。
仕様は `notes/実装指示書.md`・`notes/仕様.md`、進捗は `notes/進捗.md` を参照。

## 必要なもの

- Windows 11 / Python 3（python.org版。インストール時に「Add python.exe to PATH」にチェック）/ Google Chrome
- Python ライブラリ：`openai`, `Pillow`, `qrcode`, `Flask`（これ以外は使わない）

## 開発中の起動（フェーズ1）

**サーバー（`app.py`）は、画面を開くPC自身で動かす必要があります。**
`http://127.0.0.1:5000` は「このPC」を指すアドレスなので、サーバーを起動していないPCの Chrome では開けません。

### 1. コードを PC に取ってくる

どちらかの方法で。

- **ZIP で取る（簡単）**：GitHub のリポジトリページで、ブランチを `claude/create-claude-docs-evzn33` に切り替え →「Code」→「Download ZIP」→ 展開
- **git で取る**：

```bat
git clone -b claude/create-claude-docs-evzn33 https://github.com/usagi-15/MyCover_myApp.git
```

### 2. 起動する

展開したフォルダの **`start_dev.bat` をダブルクリック**。
ライブラリのインストール → サーバー起動（「MyCover server」という黒い窓が開く）→ Chrome で `/desk` と `/display` が開きます。
止めるときは「MyCover server」の窓を閉じます。

手動で起動する場合：

```bat
py -m pip install -r requirements.txt
py app.py
```

「Running on http://127.0.0.1:5000」と表示されたら、Chrome で次の2つを開きます。

- 机のモニター：http://127.0.0.1:5000/desk
- 大型モニター：http://127.0.0.1:5000/display

### 開けないとき

| 症状 | 確認すること |
| --- | --- |
| 「このサイトにアクセスできません」 | サーバーの窓が開いていて「Running on ...」と出ているか。窓を閉じると止まる |
| `py` が見つからない | python.org 版の Python をインストールしたか |
| `No module named flask` など | `py -m pip install -r requirements.txt` を実行したか |
| サーバーの窓に赤いエラー | エラー文の最後の数行を共有してください |
| 音が出ない | `start_dev.bat` から開いたか（自動再生を許可するオプション付きで Chrome を開く）。または一度画面をクリックする |

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
supabase/schema.sql    Supabase のテーブル・RLS（notes/クラウド構成手順.md 参照）
start_dev.bat          開発用の起動ファイル
notes/                 仕様・進捗・クラウド構成手順
```

## 開発用メモ

- 入力欄に `#fail` と入れて生成すると、生成失敗時の画面（D4）を確認できる（ダミー生成時のみ）。
- 確定したジャケットはフェーズ1ではメモリ上だけに保存されるため、サーバーを再起動すると消える（フェーズ3で SQLite に保存）。

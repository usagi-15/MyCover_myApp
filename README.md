# 『My Cover』展示アプリ

音楽コンテンツにおけるオーディエンス・ジャーニーの設計（武蔵野美術大学 デザイン情報学科3年 大石ゼミ／池田うさぎ）の展示用アプリ。
仕様は `notes/実装指示書.md`・`notes/仕様.md`、進捗は `notes/進捗.md` を参照。
**自分で編集するとき・別の端末で開くときは `notes/編集ガイド.md` を参照。**

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

## 展示当日の起動（本番）

1. 展示PCに机のモニターと大型モニターをつなぎ、Windows の「設定」→「システム」→「ディスプレイ」で2画面の並びを確認する。
2. **`start_exhibit.bat`** をダブルクリック。サーバーが最小化した窓で起動し、Chrome が2つ全画面（キオスク）で開く。
   - 机のモニターに `/desk`、大型モニターに `/display`。
   - 開く位置は `start_exhibit.bat` の上の方の `DESK_X` `DISPLAY_X` などで変える（大型モニターが机のモニターの右にあり、どちらも 1920×1080 なら `DISPLAY_X=1920`）。
3. キオスクの画面を閉じるときは、その画面をクリックして **Alt + F4**。もう一度開くときは `start_exhibit.bat` を実行（サーバーが動いていれば、画面だけ開き直す）。
4. PC の電源を入れたら自動で起動したいとき：`Win + R` →「`shell:startup`」→ 開いたフォルダに `start_exhibit.bat` のショートカットを置く。

### スタッフ用ページ（/admin）

展示PCの Chrome で **http://127.0.0.1:5000/admin** を開く（キオスクとは別のウィンドウで。展示PC以外からは開けない）。

- 今日の体験数・確定・中止・持ち帰り方法、カード残数、次の No.、クラウドへの送信状況
- **状態のリセット**：画面が止まったときに。体験中の人がいれば中止扱いにして、机をホーム・大型モニターをギャラリーに戻す（記録は消えない）
- **予備モード**：OpenAI の障害や回線断が続くときにオン。生成せず `static/backup/` の作例ジャケットで体験を続ける（記録に残る）
- **非表示**：ジャケットをギャラリーとスマホ用ページから隠す／戻す

### 無操作タイムアウト

操作が **60秒** ないと、D2・D6・D7・D9・D10 はホームへ戻る。D3〜D5 は「まだ続けますか？」を出し、**20秒** 答えがなければ中止してホームへ（`config/config.json` の `timeouts`）。

## 画像生成（OpenAI）の設定（フェーズ2）

API キーが無い間はダミー画像で動きます（起動時に「画像生成：dummy」と表示）。OpenAI を使うには、次のどちらかで API キーを渡します。**キーはコードや GitHub、チャットに書かないこと。**

- **かんたん**：`set_api_key.bat` をダブルクリックし、キーを貼り付けて Enter（`config/secrets.json` に保存される）
- **設定ファイル**：`config/secrets.example.json` をコピーして `config/secrets.json` という名前にし、`openai_api_key` にキーを書く（`secrets.json` は Git 管理外）
- **環境変数**：`OPENAI_API_KEY` に設定する

```bat
setx OPENAI_API_KEY "sk-..."
```
（`setx` のあとは、コマンドプロンプトを開き直すと有効になります）

起動時に「画像生成：openai（モデル … / 品質 …）」と出れば OpenAI を使っています。

### モデル・品質の比較

使うモデルは `config/config.json` の `openai.model`（`gpt-image-2.6-sunburst`）。
`test_models.bat` をダブルクリックすると、候補のモデルで順に生成して秒数を表示し、画像のフォルダ（`data\test`）を開きます。
コマンドで実行する場合は、次のスクリプトで、生成にかかる時間と仕上がりを比べられます（API 利用料金がかかります）。結果の画像は `data/test/` に保存されます。

```bat
py tools/test_generate.py "深い海の底。一筋の光がさしている。" --models gpt-image-2.6-sunburst gpt-image-2.6-flare
```
```bat
py tools/test_generate.py "深い海の底。一筋の光がさしている。" --model gpt-image-2 --quality low
```

展示PC固有の値（モデル・品質など）は `config/config.local.json` に書くと `config.json` を上書きできます。

```json
{ "openai": { "model": "gpt-image-2", "quality": "low" } }
```

## クラウド（Supabase・スマホ用ページ・カード）の設定（フェーズ4）

手順は `notes/クラウド構成手順.md` の 6章。

1. `set_supabase_key.bat`：Supabase の秘密キーを保存して接続を確認
2. `make_cards.bat`：カード100枚のトークン・CSV・QR 画像を作り、Supabase に登録（`data\cards`。**バックアップ必須**）
3. `mobile` フォルダの中身を GitHub Pages 用リポジトリ `usagi-15/mycover` に置く（楽曲 `B7F.mp3` も）

起動時に「クラウド（Supabase）への送信：有効」と出れば、確定したジャケットが Supabase に送られます。

## 記録（研究データ）とコードの更新時の注意

確定したジャケットと研究用の記録は **`data/` フォルダ**（`data/mycover.db` と `data/images/`）に保存されます。

- **新しいコードを ZIP で取り直すときは、古いフォルダの `data` フォルダと `config/secrets.json` を新しいフォルダにコピーしてください。** コピーしないと、ギャラリーと記録が空になります（古いフォルダを消すと記録も消えます）。
- 記録を Excel で見るには **`export_csv.bat`** をダブルクリック。`data/export/<日時>/` に表ごとの CSV ができます。

| 表 | 内容 |
| --- | --- |
| covers | 確定したジャケット（No.、確定日時、入力文、作り直し回数、持ち帰り方法、カード No. など） |
| cover_attempts | 確定したジャケットの各回の入力文と生成時間 |
| sessions | 体験の開始・終了時刻と結果（確定／中止）。中止した回は入力文を残さない |
| gallery_plays / gallery_events | ギャラリーで再生されたジャケットと操作（再生・一時停止・移動など） |

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
config/secrets.json    API キーなどの秘密情報（Git管理外。secrets.example.json を参考に作る）
config/ng_words.txt    NGワード
prompts/base_prompt.txt 固定プロンプト（曲の世界観・画風。作者が書く）
prompts/title_ai.txt   曲名をAIに描かせるための指示（title_mode が ai のとき）
prompts/input_rule.txt 鑑賞者の言葉を文字として書き込まないための指示
tools/test_generate.py 画像生成の動作確認・モデル比較
data/                  記録（mycover.db）と生成画像（Git管理外。消さないこと）
supabase/schema.sql    Supabase のテーブル・RLS（notes/クラウド構成手順.md 参照）
mycover/supabase.py    Supabase への送信（失敗したら再送）
start_exhibit.bat      展示当日の起動（サーバー＋Chrome 2画面のキオスク）
start_dev.bat          開発用の起動ファイル
static/backup/         予備モードで使う作例ジャケット（作者が置く）
templates/admin.html   スタッフ用ページ /admin
set_api_key.bat        OpenAI の API キーを保存する
test_models.bat        画像生成モデルの比較
export_csv.bat         研究用の記録を CSV に書き出す
set_supabase_key.bat   Supabase の秘密キーを保存して接続を確認
make_cards.bat         カードの発行（CSV・QR 画像・Supabase 登録）
mobile/                スマホ用ページ（GitHub Pages 用リポジトリ usagi-15/mycover に置く）
notes/                 仕様・進捗・クラウド構成手順
```

## 開発用メモ

- ダミー生成時のみ：入力欄に `#fail` と入れると生成失敗時の画面（D4）、`#ng` と入れると書き直しのお願い（D3）を確認できる。
- 記録を消して最初からやり直したいとき（テスト後など）は、サーバーを止めてから `data` フォルダを削除する。**展示の本番データは消さないこと。**

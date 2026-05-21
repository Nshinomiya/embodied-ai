---
name: screen-read
description: 孤立PCの画面をWi-Fiカメラで連続撮影しMarkdown化してObsidian Vaultに保存する。ユーザーが「画面を読み取って」「画面のテキストを保存」「screen-read」「OCR」と言ったら起動する。
---

# screen-read

孤立環境PC（ネットワーク未接続）の画面を Tapo C220 で連続撮影し、OpenRouter 経由の Gemini 2.5 Pro で OCR、決定論的に結合して Obsidian Vault の `00_Inbox/clip-YYYYMMDD-HHmm.md` に保存する。

仕様の出典は `docs/要件定義.md`（F-1〜F-16）と `docs/結合アルゴリズム.md`。実装本体は `screen_read/` パッケージ（`merge.py` / `preprocess.py`）にある。

## 前提

- Wi-Fi カメラが正対設置・ピント合わせ済み（位置調整は Tapo アプリで `screen-read` プリセットを上書き保存することで運用）
- 撮影側 PC: VSCode 編集画面、**Word Wrap OFF**、本文 14pt+。ダークテーマでも OK（Gemini 系は色反転を読める。誤字率が高い時のみライトテーマ切替を検討）
- 撮影中の画面は **機密区分「内部」以下**（クラウド OCR に画像送信するため）
- 終了マーカー `---END---` は任意（後述の二重化終了判定でカバー）
- `OPENROUTER_API_KEY` 環境変数が export されていること（OCR は OpenRouter を直接叩く）
- **撮影前に IDE 通知ポップアップ（Copilot Chat の "Pin selection..." 等）を Esc で閉じる**。エディタ本文に重なると OCR がフラグメント化する
- helper の JSON 出力から `.text` を取り出すには `jq -r '.text' <file>` を使う（jq 前提）

## セッション初期化

ユーザーから起動指示を受けたら、まず以下を確認する：

1. **保存先 Vault のパス**（既定: `/mnt/c/Users/SlmbrCat/Documents/obsidian/pkm` — Windows 側 Obsidian Vault の `pkm/` ルート。helper が `00_Inbox/clip-*.md` を自動で付け足す）
2. **想定ページ数**（参考程度。`MAX_PAGES=20` で強制終了）
3. **撮影元の補足**（refs に書く一行メモ。例: 「同僚 PC のメモ画面」）

セッション ID とテンポラリディレクトリを作る：

```bash
SESSION_ID=$(date +%Y%m%d-%H%M%S)
SESSION_DIR=/tmp/screen-read-${SESSION_ID}
mkdir -p "${SESSION_DIR}"
```

カメラを撮影プリセットに移動：

```
mcp__wifi-cam__camera_go_to_preset preset_id="1"   # name: screen-read
```

プリセット位置をチューニングしたい時は Tapo アプリで PTZ 操作 → 同じ名前で上書き保存するだけ。preset_id は変わらないので SKILL.md の変更は不要。

## ページループ

`page=1` から開始し、終了条件まで繰り返す。

### 1. 撮影

`mcp__wifi-cam__see` で 1 枚キャプチャ。返ってくる TextContent に `Captured image at <timestamp> (<W>x<H>)` が入っており、wifi-cam-mcp 側が `/tmp/wifi-cam-mcp/capture_<timestamp>.jpg` に自動保存している。timestamp を抽出してセッション dir にコピー：

```bash
TS="<extracted-timestamp>"   # 例: 20260428_214322
cp "/tmp/wifi-cam-mcp/capture_${TS}.jpg" "${SESSION_DIR}/page-${page}.jpg"
```

### 2. 撮影前処理

```bash
uv run --project screen_read python \
  .claude/skills/screen-read/scripts/screen_read_helper.py \
  preprocess "${SESSION_DIR}/page-${page}.jpg"
```

JSON が返る：
- `blurry: true` → ユーザーに「ピントが甘いので撮り直してください」と提示し、調整後に同じページで再撮影
- `low_contrast: true` → ユーザーに「画面が暗いかコントラストが足りません。照明を明るくしてから撮り直してください」と提示。Vision モデルは暗い画像で **読めないと言わず捏造する** 既知の failure mode があるため、ここで止めるのは必須（feedback_vision_low_contrast_hallucination.md）
- `ok: true` → 続行（EXIF 除去 + 長辺 ≤2000px リサイズ済み）。`brightness_mean` / `brightness_std` / `dark_ratio` が JSON に乗っているので参考値として使える

### 3. クールダウン

```bash
sleep 0.5  # CAPTURE_COOLDOWN_SECONDS
```

### 4. OCR（OpenRouter 直叩き / Gemini Pro 主力）

OCR は `helper ocr` で **OpenRouter API を直接叩く**。`mcp__pal__chat` は使わない（PAL の "engineering thought partner" persona が Anthropic / OpenAI 系 vision モデルに対して画像 OCR を拒否させる現象が判明したため）。

主力モデルは `google/gemini-2.5-pro`（$0.05/page）。Flash は記事末端や行端での誤読が境界検出を壊すケースが実機テストで確認されたため、**疑義時のクロスチェック用**に降格。`--model` 省略時は Pro が呼ばれる。

```bash
$HELPER ocr \
  --image "${SESSION_DIR}/page-${page}.jpg" \
  > "${SESSION_DIR}/page-${page}.ocr.json"

# .text の取り出し
ocr_text=$(jq -r '.text' "${SESSION_DIR}/page-${page}.ocr.json")
```

helper 側で **F-15 のシステム指示**（プロンプトインジェクション耐性 + 行番号 / オーバーレイ / ステータスバー無視 + 返答全体の ```markdown フェンス抑制）が hard-code されている。**F-16 のリトライ**（HTTP 429 / 5xx に最大 3 回、1s → 2s → 4s）と **外側フェンス自動剥がし**（`_strip_outer_fence`）も内蔵。

事前準備として `OPENROUTER_API_KEY` を環境にエクスポートしておくこと。なければ helper は `ok: false` で即終了する。

> **稀な失敗:** OpenRouter から `content: None` が返って `_strip_outer_fence(None)` で AttributeError が出ることがある（helper の F-16 リトライでもカバーしきれないケース）。同じ画像で 1 回だけ手動リトライすると通ることが多いので、まず `ocr` をもう 1 度叩いてから別モデル切替を検討する。

### 5. ページ保存（レジューム用 / F-12）

```bash
echo "<OCR_TEXT>" | uv run --project screen_read python \
  .claude/skills/screen-read/scripts/screen_read_helper.py \
  save-page --session-dir "${SESSION_DIR}" --page "${page}" \
  --image "${SESSION_DIR}/page-${page}.jpg"
```

### 6. プレビューと疑義検知（F-2 / F-8）

OCR 結果をユーザーに提示。以下の疑義シグナルを検知して提示する：
- 括弧 `()`, `[]`, `{}`, バッククォート `` ` `` の不整合
- インデント幅の急変（コードブロック内）
- ASCII / 全角混在の不自然な切り替わり
- 結合不確実マーカー `<!-- MERGE_UNCERTAIN -->` の発生（前ページ結合時）
- **見出しレベルの揺れ**: 同じ階層の見出しが page をまたいで `##` / `###` / `#` のように違うレベルで読まれる（Gemini Pro の既知の癖。文書構造の自然さで補正判断する）
- **強調マーカーの化け**: `**...**` が `・・...・・`（全角中黒）に化ける。インライン強調の周辺で `・・` が連続したら疑う
- **番号付きリストの行欠落**: `1. ... 2. ... ___ 4. ...` のように番号が飛んでいる、あるいは page 境界の前後で番号がリセット／重複する場合

疑義があれば **同じ画像を Flash でクロスチェック**して差分を見る（F-9 改: 標準が Pro になったので、Flash を「別観点」として使う運用へ反転）：

```bash
$HELPER ocr --image "${SESSION_DIR}/page-${page}.jpg" --model google/gemini-2.5-flash
```

両者の差分をユーザーに見せる。Flash で意味が通じる読みが返ってきたなら Pro 側のハルシネーションを疑う。両者が一致しているのに不自然なら撮り直しを促す（F-6）。Anthropic / OpenAI 系の vision モデル（claude-opus-4.1, o3 等）は OpenRouter 直叩きでも persona 拒否や hallucination が確認されたため、当面は Gemini ファミリ内のグレード違いを使う。

### 7. 終了判定（F-7: 二重化）

以下のいずれかで終了：
- OCR 結果に `---END---` が含まれる
- 直前ページとピクセル差が小さい（連続同一ページ）

```bash
if [ "${page}" -gt 1 ]; then
  uv run --project screen_read python \
    .claude/skills/screen-read/scripts/screen_read_helper.py \
    same-page "${SESSION_DIR}/page-$((page-1)).jpg" "${SESSION_DIR}/page-${page}.jpg"
fi
```

`is_same: true` または `---END---` 検出で break。`page > MAX_PAGES (20)` で強制終了（F-11）して警告。

### 8. 次ページ

**毎ページ撮影前に明示的なスクロール指示を出し、ユーザー確認を得てから `see` を呼ぶ**（[[feedback-screen-read-scroll-prompt]]）。テンプレ:

> 撮影元 PC で PgDn を 1 回押してください。前ページ末尾（`<代表行>` あたり）が **3〜5 行** 残る程度に Up キーで微調整。済んだら「次へ」、最終ページなら「END」と。

- **例外（即撮影 OK）**: `page=1` 初回撮影 / ユーザーが「再撮影して」と明示した時
- **Tip**: Up キー戻し量は控えめに。戻しすぎると次ページが前ページを完全包含して overlap 検出が破綻する。前ページ最後の 1-2 行が次ページ先頭で再出する程度
- **「次へ」と言われたが画面が前回と同じ範囲だった場合**: `same-page` の `mean_abs_diff < 5` なら勝手に進めず、「同じ範囲です。PgDn 効かず／最終ページ？」と確認する

## 結合 + 保存

ループ終了後、

```bash
uv run --project screen_read python \
  .claude/skills/screen-read/scripts/screen_read_helper.py \
  merge-save \
  --session-dir "${SESSION_DIR}" \
  --vault "<VAULT_PATH>" \
  --source "<撮影元の補足>"
```

JSON が返る：
- `output`: 書き込んだファイルパス
- `uncertain_boundaries`: `<!-- MERGE_UNCERTAIN -->` の発生数
- `boundaries`: 全境界の配列。各要素に `index`、`uncertain`、`decision`、`prev_image` / `next_image`、`prev_tail` / `next_head`（OCR スニペット末尾／先頭 8 行）

`uncertain_boundaries: 0` でも silent 欠落のリスクあり → 必ず「自己確認」を実施する。

## F-13 救済 UI

`uncertain_boundaries > 0` の境界に対して、各 `boundaries[*]` の `uncertain: true` を順番に処理する：

1. **境界画像を並列提示**: `Read` ツールで `prev_image` と `next_image` を読み込み、ユーザーに表示する。Vision モデル経由ではなく `Read` を使うのは、PAL の persona injection を避けつつユーザー目視で確認するため
2. **OCR スニペットも併記**: `prev_tail` / `next_head` をそのままユーザーに見せ、「この境界をどう繋ぐべきか」聞く
3. **修正案を反映**: ユーザーから受け取ったブリッジテキストを `apply-boundary-fix` で `<!-- MERGE_UNCERTAIN -->` マーカーに置き換える：

```bash
echo "<USER_PROVIDED_BRIDGE>" | $HELPER apply-boundary-fix \
  --output "<MERGED_MD_PATH>" \
  --boundary-index 0
```

   - `--boundary-index` は **マージ済み Markdown 中の N 番目の `<!-- MERGE_UNCERTAIN -->`**（0-based）。`boundaries` 配列の uncertain 要素を順序通り処理すれば自然と一致する
   - `--replacement` を空にすると、マーカーを除去するだけ（前後ページを直接連結）になる
4. **再確認**: `apply-boundary-fix` の戻り値 `remaining_uncertain` が 0 になるまで繰り返す

途中で「もう一度この境界の詳細を見たい」となった場合は `inspect-boundary --boundary-index N` で再取得できる（ページ番号は 0=page1↔page2、1=page2↔page3、…）。

## 自己確認（結合後の整合性チェック）

`merge-save` 完了後、F-13 救済とは別に **Claude 自身が結合済み Markdown を全文 Read して** 以下を点検する（`uncertain_boundaries: 0` でも実施。silent な欠落・誤読の救済）。**通す前に「完了」を宣言しない**。

- **連続性**: 番号付きリスト `1. 2. 3.` が飛んでいないか / 見出しレベルが一貫（page 境界で `##` が `###` `#` に化けていないか）/ 表のカラム数が行ごとに揃っているか
- **記号化け**: `**...**` の `・・...・・` 化け / 全角半角の不自然な切替 / `→` の前後で意図しない改行
- **境界跨ぎ**: 各 `boundaries[*]` の `prev_tail` 末尾 ↔ `next_head` 先頭が結合本文できちんと接合されているか。特に `decision.k ≥ 8` の箇所は一行飛びを重点確認
- **不要要素**: ブラウザタブ／サイドバー／ステータスバー由来の語句（`Copilot へメッセージを送る` 等）混入 / `---` の 3 連以上

問題は `Edit` で直接修正し、最後にユーザーへ「これこれを自己補正した」と一行報告する。

## 既存ファイルへの追記（続編の結合）

既に保存済みの clip-*.md に続編を結合する場合の手順。`merge-save` は単一セッション完結なので、既存ファイルの `--vault` に直接渡すと上書きされる → 必ず tempvault → 手動 Edit。

1. **新セッションで撮影** → `merge-save` の `--vault` に `/tmp/screen-read-tempvault` のような **使い捨てパス** を渡す
2. **既存ファイルを `Read`** し、末尾本文と tempvault 新規 markdown の本文先頭（front matter 後）を照合。一致する overlap 行を見つける
3. **`Edit` で追記**: 既存ファイルの overlap 終端行を `old_string`、`new_string` で `<同じ行>\n\n<差分本文>` を書く。front matter は触らない（`pages` を更新するなら別 Edit）
4. **自己確認**: 上記「自己確認」セクションを必ず実施（境界跨ぎ・見出しレベル）
5. **クリーンアップ**: `SESSION_DIR` と `TEMP_VAULT` を `rm -rf`

## クリーンアップ

セキュリティ要件（処理完了後の画像常時削除）：

```bash
rm -rf "${SESSION_DIR}"
```

ただしユーザーが「画像を残してほしい」と明示した場合のみ保留可。検証用に特定画像を後から見直したい場合は `docs/test-images/` 配下にコピーする運用（`.gitignore` 済み、コミットされない）。

## 失敗時のレジューム

途中中断時は `${SESSION_DIR}/page-*.json` が残る。再開時は同じ `SESSION_ID` を指定し、最後のページ番号 + 1 から再開。`merge-save` は既存の `page-*.json` を全部読むので、最後まで撮り終えていれば撮影ステップを飛ばして結合だけやり直すことも可能。

## 参考

- `screen_read/merge.py` — RapidFuzz ベースのページ結合（`MIN_SCORE=91.0`, `MAX_PAGES=20`）
- `screen_read/preprocess.py` — ブレ検知 / EXIF 除去 / リサイズ / クールダウン
- `docs/要件定義.md` — F-1〜F-16 の機能要件全文
- `docs/アーキテクチャ.md` — シーケンス図とリスク表

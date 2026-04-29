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
- helper の JSON 出力パースに `jq` を使う例があるが、未インストール環境では `python -c` のワンライナーで代替可（後述の早見表参照）

## セッション初期化

ユーザーから起動指示を受けたら、まず以下を確認する：

1. **保存先 Vault のパス**（既定: `~/obsidian-vault` がなければユーザーに尋ねる）
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

# .text の取り出し（jq があれば jq -r '.text' でも可）
ocr_text=$(python -c "import json,sys; print(json.load(open(sys.argv[1]))['text'])" \
  "${SESSION_DIR}/page-${page}.ocr.json")
```

helper 側で **F-15 のシステム指示**（プロンプトインジェクション耐性 + 行番号 / オーバーレイ / ステータスバー無視 + 返答全体の ```markdown フェンス抑制）が hard-code されている。**F-16 のリトライ**（HTTP 429 / 5xx に最大 3 回、1s → 2s → 4s）と **外側フェンス自動剥がし**（`_strip_outer_fence`）も内蔵。

事前準備として `OPENROUTER_API_KEY` を環境にエクスポートしておくこと。なければ helper は `ok: false` で即終了する。

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

ユーザーに「次ページにスクロール（PgDn 1回、前ページ末尾が **3〜5 行** 見える程度に Up キーで微調整）してください」と促し、確認後に `page+=1` で再開。

> **Tip:** Up キー戻し量は控えめに。戻しすぎると「前ページが次ページに完全包含される」状態になり、merge.py の overlap 検出（prev 末尾 K 行 ↔ next 先頭 K 行）が破綻する。前ページの最後の 1-2 行が次ページの先頭で再び見える程度を狙う。

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

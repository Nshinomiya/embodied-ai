# Session Handover

**最終更新:** 2026-04-28 22:35

---

## 前提と目的 (Context & Intent)

screen-read 実装を **机上完成** から **実機通電** に移すセッション。前回までで skill + helper CLI のオーケストレーションが揃っていたので、本セッションは Tapo C220 で実画面（VSCode 日本語・ダークテーマ）を撮影 → Gemini Flash OCR → frontmatter 付き Markdown 保存までエンドツーエンドで通すことを目標にした。

加えて、wifi-cam-mcp `see` の戻り値スキーマが不明だった件、ダークモード可否、`---END---` の必須性、PTZ 自動アイミングの可否といった運用上の疑問を実機で潰した。

---

## 成果と変更箇所 (Outcomes & Changed Files)

### 既コミット（前セッションまで、本セッション開始時の HEAD）

- `77e34ca` docs: update handover and chronicle for screen-read skill session

### 未コミット（本セッションで作業中）

- ` M .claude/skills/screen-read/SKILL.md` — 実機テスト学びを反映
- `?? docs/archive/handover-20260428-2235.md` — 直前 HANDOVER の退避

### SKILL.md 変更点

1. **前提セクション**
   - 「白背景・黒文字推奨」→ 「ダークテーマでも OK（Gemini Flash は色反転を読める）」
   - 「`---END---` は必須」→ 「任意（終了判定二重化でカバー）」
   - プリセット運用方針: 位置調整は Tapo アプリで `screen-read` プリセットを上書き保存 → コード変更不要

2. **セッション初期化** に `mcp__wifi-cam__camera_go_to_preset preset_id="1"` を追加。プリセット token = "1", name = "screen-read"

3. **「1. 撮影」** に実際のファイルパス機構を記載：
   - `see` は `/tmp/wifi-cam-mcp/capture_<timestamp>.jpg` に自動保存
   - timestamp は TextContent `Captured image at <timestamp> (<W>x<H>)` から抽出
   - `cp` でセッション dir にコピーする手順を明示

4. **OCR システム指示** を強化（実害ベースで判明した点）：
   - エディタ左端の行番号を無視
   - カメラオーバーレイ日付（左上 "YYYY-MM-DD HH:MM:SS"）を無視
   - 画面下部 VSCode ステータスバー・ツールバー・デスクトップアイコンを無視
   - 返答全体の ```markdown フェンスを付けない（PAL 経由 Gemini が付ける癖がある）

### 実機テスト結果（1 ページ・ダークモード VSCode 日本語）

- 撮影: variance 2407（鮮鋭、閾値 100 を大幅クリア）/ 1920×1080 / EXIF strip OK / 自動保存 OK
- OCR: Gemini 2.5 Flash で 55 行 Markdown を返却。ダークモード（黒背景・白文字・日本語）でも実用レベル
- save-page → merge-save: `uncertain_boundaries: 0`、frontmatter 正しく付与（`status/seed`, `type/reference`, `source/screen-read`, `created`, `pages`, `refs`）
- 出力ファイル: `/tmp/screen-read-test01/clip.md`

### 観測された OCR 誤認候補

- `github Zenn` ← `github Issues` の可能性
- `Advent Calender` ← `Calendar`（画面通りなら正解）
- 画像左端の見出し的短行（「1day」「github」など）が一部欠落

→ 疑義検知 + Haiku 二次 OCR の価値あり、と判断

---

## 検討と意思決定 (Decisions & Rationale)

- **判断:** PTZ 自動アイミングは MVP に入れず、プリセット運用にする
  - **理由:** Tapo C220 は **光学ズーム非対応**（固定焦点）。auto-aim でセンタリングは可能だがフレーム充填はカメラの物理位置でしか変えられない。一度物理アイミング → プリセット保存 → 以降ノータッチが最小コストで最も安定
  - **代替案:** OpenCV で明るい矩形検出 → look_left/right/up/down で反復補正 → `auto-aim` サブコマンド追加。実装 100 行程度。要件の Out 「PTZ自動追従」に元々書かれていたので将来拡張で十分

- **判断:** プリセット作成は **wifi-cam-mcp ではなく Tapo アプリ**で行う
  - **理由:** wifi-cam-mcp は `get_presets` / `go_to_preset` のみで「保存」ツールを持たない。プリセットは ONVIF 経由でカメラ本体ファームウェアに保存される設計。Tapo アプリから書き、MCP から読む分業
  - **代替案:** wifi-cam-mcp に `create_preset` ツールを追加 → ONVIF `SetPreset` で実装可能だが、Tapo アプリが GUI で完結している今は不要

- **判断:** ダークテーマで運用継続
  - **理由:** 1 ページ実機テストで Gemini Flash が黒背景・白文字・日本語混在を支障なく読めた。要件定義の「白背景推奨」は OCR 工学的セオリーだが現代 vision モデルでは無視可能
  - **代替案:** ライトテーマ強制 → ユーザー作業負荷増。誤字率が許容外になった時のみ切替を提案

- **判断:** OCR システム指示に「`/`返答全体に ```markdown フェンスを付けない」を明記
  - **理由:** 1 ページ実機テストで PAL 経由の Gemini Flash が ` ```markdown\n...\n``` ` で全体を囲んで返してきた。これを skill 側で機械的に剥がすより、システム指示で抑制するほうが確実
  - **代替案:** save-page で先頭 ```markdown と末尾 ``` を strip → 取りこぼしリスクあり、システム指示の方が責任境界が明確

---

## ハマった点・失敗したアプローチ (Friction & Anti-patterns)

- **問題:** 初回 `see` 実行時、カメラが部屋全体（マゼンタの非テキストモニタ + 横のノート PC）を撮影していた
  - **試したこと:** プリセット未保存のまま see を実行
  - **結果:** OCR テストにならず、ユーザーに物理アイミング + プリセット保存を依頼するステップが必要だった
  - **教訓:** 実機テスト前に **必ずプリセット位置確認**。SKILL.md は最初の `camera_go_to_preset` を必須化済み

- **問題:** `wifi-cam-mcp` の `see` 戻り値が ImageContent + TextContent で、base64 を skill から扱う術がなさそうに見えた
  - **試したこと:** ToolSearch で wifi-cam ツール一覧を確認、camera.py を読んだ
  - **結果:** **`save_to_file=True` がデフォルト**で `/tmp/wifi-cam-mcp/capture_<timestamp>.jpg` に自動保存される設計だった。TextContent の timestamp を見れば file path が確定する。ImageContent の base64 を抽出する必要なし
  - **教訓:** MCP ツールの **副作用（disk save 等）** はソースを読まないと分からない。戻り値スキーマだけ見て設計するとブロッカーに見える

- **問題:** PAL 経由 Gemini が返答全体を ` ```markdown ... ``` ` で囲んで返した
  - **試したこと:** 実画像でテスト
  - **結果:** 行 1 に ` ```markdown` が入り、merge アルゴリズムや Obsidian 表示に余計なフェンスが残る恐れ
  - **教訓:** vision モデルは「Markdown を返してください」と言われるとフェンスで囲みがち。**システム指示で明示的に抑制する**

---

## 次にやること (Next Steps)

### 1. 本セッション分のコミット

1. [ ] `git add .claude/skills/screen-read/SKILL.md docs/HANDOVER.md docs/CHRONICLE.md docs/archive/handover-20260428-2235.md` → 2 コミットに分けて push（feat: skill 更新 / docs: handover）

### 2. 2 ページ統合テスト（F-3 / F-7）

2. [ ] 撮影側 PC で `PgDn` 1 回スクロール（前ページ末尾 5 行が次ページ先頭に残るように調整）
3. [ ] `mcp__wifi-cam__see` → preprocess → OCR → save-page (page=2)
4. [ ] `same-page` で page-1.jpg と page-2.jpg を比較し、`is_same: false` を確認
5. [ ] `merge-save` で 2 ページを結合し `uncertain_boundaries`、`decisions` を確認

### 3. F-9 疑義検知 + Haiku 二次 OCR の検証

6. [ ] 1 ページテストで誤認候補が出た（`github Zenn` 等）。同じ画像を `model=anthropic/claude-3.5-haiku` で再 OCR し差分を比較
7. [ ] 疑義検知ヒューリスティック（括弧不整合・インデント揺れ）の実装検討。skill 本文 or helper の新サブコマンドどちらか

### 4. クリーンアップ・運用改善

8. [ ] `wifi-cam-mcp/.env` を削除（認証は `.mcp.json` 集約済み）
9. [ ] ルーターで C220（`192.168.10.118`）の DHCP 固定割り当て設定
10. [ ] 実運用後、memory-mcp を `claude mcp add --scope user` でユーザースコープ昇格を判断

### 5. 拡張（将来）

11. [ ] `auto-aim` サブコマンド検討（OpenCV モニター矩形検出 + look_left/right/up/down 反復）。要件定義の Out に既載
12. [ ] `BLUR_VARIANCE_THRESHOLD` (100) / `MIN_SCORE` (91.0) / `same-page --threshold` (2.0) を実画像で再チューニング

---

## 参考情報

### 現在の構成スナップショット

| 項目 | 値 |
|------|-----|
| プロジェクト直下 | `/home/slmbrcat/projects/embodied-ai/` |
| C220 IP | `192.168.10.118`（ONVIF port 2020） |
| C220 プリセット | token=`"1"`, name=`screen-read`（撮影位置・Tapo アプリで上書き編集可能） |
| 自動キャプチャ保存先 | `/tmp/wifi-cam-mcp/capture_<timestamp>.jpg` |
| memory DB | `~/.claude/memories/memory.db` |
| 接続済み MCP | wifi-cam / memory / system-temperature / sociality / pal |
| screen_read venv | `screen_read/.venv/`（uv 管理、Python 3.13.13） |
| pytest 結果 | 20 passed (merge 14 + preprocess 6) |
| 実機 1 ページテスト出力 | `/tmp/screen-read-test01/clip.md`（55 行） |

### 実機運用早見表

```bash
# 1. プリセット位置に移動
# (mcp__wifi-cam__camera_go_to_preset preset_id="1")

# 2. 撮影
# (mcp__wifi-cam__see) → /tmp/wifi-cam-mcp/capture_<TS>.jpg

# 3. セッション dir にコピー & 前処理
SD=/tmp/screen-read-${SESSION_ID}; mkdir -p "$SD"
cp /tmp/wifi-cam-mcp/capture_<TS>.jpg "$SD/page-${page}.jpg"
HELPER='uv run --project screen_read python .claude/skills/screen-read/scripts/screen_read_helper.py'
$HELPER preprocess "$SD/page-${page}.jpg"

# 4. OCR (mcp__pal__chat with system prompt) → ocr_text を変数に保存

# 5. ページ保存
echo "$ocr_text" | $HELPER save-page --session-dir "$SD" --page ${page} --image "$SD/page-${page}.jpg"

# 6. 終了判定（page>1）
$HELPER same-page "$SD/page-$((page-1)).jpg" "$SD/page-${page}.jpg"

# 7. ループ終了後
$HELPER merge-save --session-dir "$SD" --vault ~/obsidian-vault --source "メモ"
```

### ドキュメント一覧
- `docs/要件定義.md` — F-1〜F-16 機能要件
- `docs/アーキテクチャ.md` — コンポーネント・処理シーケンス・リスク表
- `docs/結合アルゴリズム.md` — RapidFuzz 擬似コード（merge.py の参照元）
- `docs/CHRONICLE.md` — セッション履歴
- `docs/archive/handover-20260428-2235.md` — 本セッション直前のスナップショット

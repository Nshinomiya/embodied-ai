# Session Handover

**最終更新:** 2026-04-29 14:47

---

## 前提と目的 (Context & Intent)

前セッション（OCR を OpenRouter 直叩きに切替）の **次に控えていた未実装タスク 2 件**を片付けるサブセッション：

1. **preprocess の輝度ゲート追加** — Vision モデルが暗い画像で「読めない」と認めず捏造する silent hallucination の対策（feedback_vision_low_contrast_hallucination.md）
2. **F-13 救済 UI 実装** — `<!-- MERGE_UNCERTAIN -->` 境界をユーザーが手修正できるフロー

両方を実装してコミット済み。次セッションは **実機 2 ページ統合テスト**から再開する想定。

---

## 成果と変更箇所 (Outcomes & Changed Files)

### コミット履歴（本セッション）

- `ffb738d` feat(screen-read): implement F-13 boundary rescue UI
- `0e303fb` feat(screen-read): add brightness gate to preprocess pipeline

### 1. 輝度ゲート（`0e303fb`）

- `screen_read/preprocess.py` — `BrightnessCheck` dataclass + `measure_brightness()` 追加
  - グレースケール化 → 平均輝度 `mean` + 標準偏差 `std` + 暗部割合 `dark_ratio`（< 50/255 のシェア）
  - 閾値: `mean < 60` OR `std < 20` で `is_low_contrast: True`
  - 定数: `BRIGHTNESS_MEAN_THRESHOLD = 60.0` / `BRIGHTNESS_STD_THRESHOLD = 20.0` / `BRIGHTNESS_DARK_PIXEL_VALUE = 50`
- `screen_read/tests/test_preprocess.py` — 3 ケース追加（暗い画像 / 低 std 画像 / 明るい画像）
- `.claude/skills/screen-read/scripts/screen_read_helper.py` — `cmd_preprocess` で輝度ゲートを blur と同等扱い（`ok: false, low_contrast: true, hint: "...照明を明るくして..."`）。OK 時も `brightness_mean` / `brightness_std` / `dark_ratio` を JSON に乗せる
- `.claude/skills/screen-read/SKILL.md` — 前処理セクションに輝度ゲートの分岐、前提に Copilot ポップアップ Esc 操作と jq 依存メモを追加。OCR の `jq -r '.text'` 例を `python -c` ワンライナーに書き換え

### 2. F-13 救済 UI（`ffb738d`）

- `.claude/skills/screen-read/scripts/screen_read_helper.py`:
  - `cmd_merge_save` の戻り値: `decisions` → `boundaries` に拡張。各境界に `prev_image` / `next_image` / `prev_tail` / `next_head`（OCR スニペット末尾／先頭 8 行）
  - 新サブコマンド `inspect-boundary --session-dir DIR --boundary-index N` — 個別境界の画像 + スニペット + decision を再取得
  - 新サブコマンド `apply-boundary-fix --output MD --boundary-index N --replacement TEXT` — マージ済み Markdown 中の N 番目の `<!-- MERGE_UNCERTAIN -->` を手修正テキストで置換、戻り値で `remaining_uncertain` を返す
- `.claude/skills/screen-read/SKILL.md` — F-13 救済フローを 4 ステップに書き直し（Read で境界画像を並列提示 → スニペット併記 → ユーザーから受けたブリッジを `apply-boundary-fix` で反映 → `remaining_uncertain` が 0 になるまで繰り返す）

### テスト

- `pytest`: 23 passed (merge 14 + preprocess 9)
- `ruff check`: clean
- F-13 dry-run: merge-save → inspect-boundary → apply-boundary-fix の 3 段が連携することを確認

---

## 検討と意思決定 (Decisions & Rationale)

- **判断:** 輝度ゲートの閾値を `mean < 60` OR `std < 20` の OR 条件にする
  - **理由:** 「全体が暗い」と「コントラストが足りない」は別の failure mode で、片方ずつ捕捉する必要がある。フラットなグレー画面（mean ≒ 128, std ≒ 0）はブレ検知も輝度平均ゲートも通過してしまうので std を別ゲートで持つ
  - **代替案:** AND 条件 → 漏れが大きすぎる。`dark_ratio` をしきい値化 → 主指標として使うとライトテーマ画面で誤検知が出やすい。当面は補助メトリクスとして JSON に乗せるだけにとどめた

- **判断:** F-13 救済 UI を「helper の薄いサブコマンド 2 個 + SKILL.md のフロー記述」で実装する
  - **理由:** 救済 UI は「画像を並べて見せる」「ユーザーの修正案を Markdown に挿入する」の 2 操作だけ。前者は `Read` ツール、後者は `apply-boundary-fix` という単機能 CLI で足り、対話の流れ自体は SKILL.md の自然言語で記述するほうが柔軟性が高い
  - **代替案:** TUI / Web UI を新規構築 → MVP 範囲外、依存も増える。やめた

- **判断:** `cmd_merge_save` の戻り値フィールドを `decisions` から `boundaries` にリネームし、既存フィールドを残さない
  - **理由:** 旧フィールドは内部 dry-run でしか使ってなく、外部利用者なし。残すとフィールドが2つに割れて SKILL.md の説明が冗長になる。後方互換は YAGNI
  - **代替案:** 新フィールドを追加して旧フィールドを残す → 不要

- **判断:** 救済時にユーザーへ画像を見せる手段は `Read` ツール（`mcp__pal__chat` ではない）
  - **理由:** PAL の persona injection で vision モデルが OCR / 画像描写を拒否する事象を前回確認済み（feedback_pal_ocr_unsuitable.md）。`Read` なら Claude 自身が画像をマルチモーダル入力として受け取り、ユーザーに自然言語で説明できる。PAL を経由する理由がない
  - **代替案:** OpenRouter 直叩きで境界画像を vision モデルに描写させる → 救済 UI の主体はユーザーの判断であり、別 LLM を挟む価値が低い

---

## ハマった点・失敗したアプローチ (Friction & Anti-patterns)

特に大きなハマりはなし。輝度ゲートは TDD でスムーズに通り、F-13 も dry-run で一発で通った。`split_lines` を helper に追加 import した点と、`re` 未 import で apply-boundary-fix を書いた点だけ後追いで修正した（コミット前に解消）。

唯一の懸念点：

- **問題:** `boundaries` の `prev_image` / `next_image` は `page-N.json` の `image_path` フィールドを引いているため、`/tmp/wifi-cam-mcp/capture_*.jpg` を指したまま揮発する可能性がある
  - **試したこと:** 現状の SKILL.md は `cp` で `${SESSION_DIR}/page-${page}.jpg` にコピーしてから `save-page` に渡しているので、`image_path` はセッションディレクトリ配下になる
  - **教訓:** ただしユーザーが手作業で別パスから `save-page` を呼んだ場合は壊れる。実機テスト後にエッジケースを再確認

---

## 次にやること (Next Steps)

### 1. 2 ページ統合テスト（実機・再挑戦）— 最優先

前セッションで詰まっていたタスク。今回の輝度ゲート + F-13 を組み合わせて完走させる。

1. [ ] 撮影元 PC で **Copilot Chat ポップアップを Esc で閉じる**
2. [ ] 室内照明を十分に明るくする（輝度ゲート通過確認）
3. [ ] page-1: `mcp__wifi-cam__camera_go_to_preset preset_id="1"` → `see` → `cp` → `preprocess`（`low_contrast: false` を確認） → `ocr` → `save-page`
4. [ ] PgDn 1 回 + Up キー 5〜10 行戻して overlap を確保
5. [ ] page-2: 同じ手順
6. [ ] `merge-save` で `uncertain_boundaries: 0` を確認
7. [ ] `uncertain_boundaries > 0` なら F-13 フローで救済（境界画像 Read → ユーザーへ確認 → `apply-boundary-fix`）

### 2. 輝度ゲート閾値の実機チューニング

8. [ ] 1〜2 セッション運用したら `BRIGHTNESS_MEAN_THRESHOLD` / `BRIGHTNESS_STD_THRESHOLD` を実測値ベースで再調整
9. [ ] ライトテーマ画面で誤検知（暗いと誤判定）が出ないか観察。出るなら `dark_ratio` を併用するか std 閾値を下げる

### 3. テスト用画像の永続化（運用改善）

10. [ ] `/tmp/wifi-cam-mcp/capture_*.jpg` が WSL 再起動で消える件、検証用に残したい画像を `docs/test-images/` 等に GC されない場所へコピーする運用を考える

### 4. クリーンアップ（前回からの持ち越し）

11. [ ] `wifi-cam-mcp/.env` を削除
12. [ ] ルーターで C220 DHCP 固定割り当て（192.168.10.118）

---

## 参考情報

### 現在の構成スナップショット

| 項目 | 値 |
|------|-----|
| プロジェクト直下 | `/home/slmbrcat/projects/embodied-ai/` |
| C220 IP / プリセット | `192.168.10.118` / token=`"1"` name=`screen-read` |
| 自動キャプチャ保存先 | `/tmp/wifi-cam-mcp/capture_<timestamp>.jpg`（揮発、再起動で消える） |
| OCR 経路 | OpenRouter API 直叩き |
| OPENROUTER_API_KEY | 環境変数で export（`~/.bashrc` 等） |
| 標準モデル | 一次 `google/gemini-2.5-flash` ($0.002/page) / 二次 `google/gemini-2.5-pro` ($0.051/page) |
| pytest 結果 | 23 passed (merge 14 + preprocess 9) |
| F-9 検証 | ✅ 完了 |
| 輝度ゲート | ✅ 実装済み（`measure_brightness`） |
| F-13 救済 UI | ✅ 実装済み（`inspect-boundary` / `apply-boundary-fix`） |
| 2 ページ統合テスト | ❌ 未完走（次セッション最優先） |

### helper CLI 早見表

```bash
HELPER='uv run --project screen_read python .claude/skills/screen-read/scripts/screen_read_helper.py'

$HELPER preprocess /tmp/page.jpg                          # blur + brightness + EXIF + resize
$HELPER same-page /tmp/a.jpg /tmp/b.jpg --threshold 2.0
$HELPER ocr --image /tmp/page.jpg                          # 一次（gemini-2.5-flash 既定）
$HELPER ocr --image /tmp/page.jpg --model google/gemini-2.5-pro  # 二次
echo "$ocr_text" | $HELPER save-page --session-dir DIR --page 1 --image /tmp/page.jpg
$HELPER merge-save --session-dir DIR --vault ~/obsidian-vault --source "メモ"
# F-13 救済
$HELPER inspect-boundary --session-dir DIR --boundary-index 0
echo "<bridge>" | $HELPER apply-boundary-fix --output OUT.md --boundary-index 0
```

### preprocess JSON フィールド

```json
{
  "ok": true,
  "blurry": false, "variance": 2407.3,
  "low_contrast": false, "brightness_mean": 132.5, "brightness_std": 78.4, "dark_ratio": 0.12,
  "size": [1920, 1080],
  "cooldown_seconds": 0.5
}
```

### merge-save JSON フィールド（境界）

```json
{
  "ok": true,
  "output": "...",
  "page_count": 2,
  "uncertain_boundaries": 1,
  "boundaries": [
    {
      "index": 0,
      "prev_page": 1, "next_page": 2,
      "uncertain": true,
      "decision": {"ok": false, "k": 0, "score": 0.0, "reason": "..."},
      "prev_image": "...", "next_image": "...",
      "prev_tail": "...", "next_head": "..."
    }
  ]
}
```

### ドキュメント
- `docs/要件定義.md` — F-1〜F-16 機能要件
- `docs/アーキテクチャ.md` — シーケンス図
- `docs/結合アルゴリズム.md` — RapidFuzz 擬似コード
- `docs/CHRONICLE.md` — セッション履歴
- `docs/archive/handover-20260429-1447.md` — 本セッション直前のスナップショット

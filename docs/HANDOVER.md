# Session Handover

**最終更新:** 2026-04-29 11:30

---

## 前提と目的 (Context & Intent)

前セッション（OCR を OpenRouter 直叩きに切替）の **動作確認**を行うサブセッション。

主な目的:
1. `OPENROUTER_API_KEY` の保管方法決定（プロジェクト直下 `.env` か環境変数か）
2. `helper ocr` の live 動作確認（一次 Flash・二次 Pro 両方）
3. F-9 二次 OCR の効果を実数で確認

これらが片付いたら、いったんここで止め、次セッションで **preprocess の輝度ゲート追加 + 2 ページ統合テスト**を合わせて行う方針。

---

## 成果と変更箇所 (Outcomes & Changed Files)

本セッションで **コード変更はなし**。前セッションでコミット済みの helper ocr を実機検証しただけ。

### コミット履歴（直近）

- `3acb8b6` docs: handover OCR-via-OpenRouter pivot and 2-page test friction
- `1910a78` feat(screen-read): standardize OCR on direct OpenRouter API
- `6da135f` docs: update handover and chronicle for real-device test session
- `9f1de17` feat(screen-read): wire skill to real-device flow

### F-9 二次 OCR 検証結果（同一画像で Flash vs Pro 比較）

撮影対象: Claude Code ターミナル画面（マゼンタ背景・本セッションの会話履歴）

| 項目 | Flash（一次） | Pro（二次） |
|---|---|---|
| `OPENROUTER_API_KEY` | `OPENROUTER API KEV` ❌ | `OPENROUTER_API_KEY` ✅ |
| `.env` | `y()` ❌ | `.env` ✅ |
| `Crunched for 6m 37s` | `64 375` ❌ | `6m 37s` ✅ |
| Markdown 表 | 構造崩壊 | 正しい table 化 |
| 全体誤字率 | 高い | 大幅減 |
| トークン | 2,653 | 6,854 |
| **コスト** | **$0.002** | **$0.051** |

- ✅ OpenRouter 直叩き経路は機能（PAL persona injection 完全回避）
- ✅ Pro の品質改善は明確 — Flash の誤読をほぼ修正
- ✅ `_strip_outer_fence` 動作確認（内側コードフェンス・テーブル構造は保持）
- ✅ F-15 hard-code システム指示が機能（OCR 指示への persona 干渉なし）
- ✅ F-16 リトライ未発火（429/5xx に当たらず attempts: 1）

### コスト試算（実測ベース）

- 一次 Flash: $0.002/page
- 二次 Pro: $0.051/page（疑義ページのみ）
- 1 セッション 10 ページ・疑義 1〜2 ページの想定: **$0.07〜$0.12**
- 要件「1ページ < 0.5円（≒$0.003）」は Flash で満たす
- 要件「1セッション < 10円（≒$0.07）」は **疑義 2 ページくらいまでが上限**

---

## 検討と意思決定 (Decisions & Rationale)

- **判断:** `OPENROUTER_API_KEY` の保管はユーザー判断で **環境変数（`~/.bashrc` 等）** を採用
  - **理由:** ユーザーが `export` 済みで helper も即動作。現状 embodied-ai だけが OpenRouter を使うので、プロジェクト .env を作る価値は限定的
  - **代替案:** プロジェクト直下 `.env` + helper 自動 source → 将来別プロジェクトでも OpenRouter を使うなら検討。今は YAGNI

- **判断:** F-9 の二次モデルとして `google/gemini-2.5-pro` の実用性を実画像で確定
  - **理由:** $0.05/page で Flash の誤読をほぼ修正。疑義ページに限定すればコスト要件もクリア
  - **代替案:** Anthropic SDK 経由で Claude Opus 直叩き → SDK 追加 / コスト不明、現時点で必要性なし

- **判断:** 本セッションは F-9 検証で打ち止め、2 ページ統合テストは次セッションで preprocess 輝度ゲート追加とまとめて実施
  - **理由:** 夜帯のハルシネーション事例で「ブレ検知だけでは品質ゲート不十分」が明らかになっており、輝度ゲート未実装のまま 2 ページテストを再開すると同じ failure に再遭遇するリスク。先に preprocess を補強したほうが効率的

---

## ハマった点・失敗したアプローチ (Friction & Anti-patterns)

- **問題:** `/tmp/screen-read-20260428-233512/` と `/tmp/wifi-cam-mcp/capture_*.jpg` が **WSL 再起動かファイル GC で消失**
  - **試したこと:** 前セッションの実画像で F-9 検証しようとした
  - **結果:** ファイルが見つからず、新規キャプチャからやり直し
  - **教訓:** `/tmp/` は揮発前提。検証用に残したい画像は `/tmp/wifi-cam-mcp/` の外にコピーするか、`docs/test-images/` 等にチェックインする運用を考える

- **問題:** Bash で `jq` が PATH になく JSON パースに失敗
  - **試したこと:** `jq -r '.text'` で結果抽出
  - **結果:** `jq: command not found`
  - **教訓:** WSL 環境に `jq` 未インストール。helper の出力パースは Python ワンライナー（`uv run --project screen_read python -c "..."`）で代替可能。SKILL.md の例で `jq` を使っている部分は **`apt install jq` が前提**であることを明記するか、Python へ書き換える

---

## 次にやること (Next Steps)

### 1. preprocess の輝度ゲート追加（最優先）

1. [ ] `screen_read/preprocess.py` に `measure_brightness()`（仮称）を追加
   - グレースケール化 → 平均輝度 + 標準偏差 + 暗部ピクセル割合（< 50/255 のシェア）
   - 閾値案: 平均輝度 < 60 OR 標準偏差 < 20 → `low_contrast: True`
2. [ ] helper の `cmd_preprocess` で `low_contrast` を JSON に乗せ、blurry と同じ扱い（`ok: false, hint: ...`）にする
3. [ ] `screen_read/tests/test_preprocess.py` にケース追加
   - 暗い画像（mean < 60）→ low_contrast: True
   - 鮮明な画像 → low_contrast: False

### 2. 2 ページ統合テスト（再挑戦）

4. [ ] 撮影前に **Copilot Chat ポップアップを Esc で閉じる**
5. [ ] PgDn 1 回 + Up キー 5〜10 行戻して overlap を確保
6. [ ] page-1, page-2 とも輝度ゲートを通過することを確認
7. [ ] `merge-save` で `uncertain_boundaries: 0` を確認

### 3. SKILL.md 運用ルール追加（一緒にやる）

8. [ ] 前提セクションに「Copilot 通知ダイアログを閉じる」を追加
9. [ ] `jq` 依存を明記、または `python -c` 例に書き換え

### 4. F-13 救済 UI 検討

10. [ ] `uncertain_boundaries > 0` のとき、境界画像を提示して手修正候補を出すフロー設計

### 5. クリーンアップ

11. [ ] `wifi-cam-mcp/.env` を削除
12. [ ] ルーターで C220 DHCP 固定割り当て

---

## 参考情報

### 現在の構成スナップショット

| 項目 | 値 |
|------|-----|
| プロジェクト直下 | `/home/slmbrcat/projects/embodied-ai/` |
| C220 IP / プリセット | `192.168.10.118` / token=`"1"` name=`screen-read` |
| 自動キャプチャ保存先 | `/tmp/wifi-cam-mcp/capture_<timestamp>.jpg`（揮発、再起動で消える） |
| OCR 経路 | OpenRouter API 直叩き（live 動作確認済み） |
| OPENROUTER_API_KEY | 環境変数で export（`~/.bashrc` 等） |
| 標準モデル | 一次 `google/gemini-2.5-flash` ($0.002/page) / 二次 `google/gemini-2.5-pro` ($0.051/page) |
| pytest 結果 | 20 passed (merge 14 + preprocess 6) |
| F-9 検証 | ✅ 完了（Flash vs Pro 実数比較済み） |
| 輝度ゲート | ❌ 未実装（次セッション最優先） |

### helper CLI 早見表

```bash
HELPER='uv run --project screen_read python .claude/skills/screen-read/scripts/screen_read_helper.py'

$HELPER preprocess /tmp/page.jpg                          # blur+EXIF+resize（輝度は今は未チェック）
$HELPER same-page /tmp/a.jpg /tmp/b.jpg --threshold 2.0
$HELPER ocr --image /tmp/page.jpg                          # 一次（gemini-2.5-flash 既定）
$HELPER ocr --image /tmp/page.jpg --model google/gemini-2.5-pro  # 二次
echo "$ocr_text" | $HELPER save-page --session-dir DIR --page 1 --image /tmp/page.jpg
$HELPER merge-save --session-dir DIR --vault ~/obsidian-vault --source "メモ"
```

### ドキュメント
- `docs/要件定義.md` — F-1〜F-16 機能要件（F-9 のモデル指定は古い）
- `docs/アーキテクチャ.md` — シーケンス図
- `docs/結合アルゴリズム.md` — RapidFuzz 擬似コード
- `docs/CHRONICLE.md` — セッション履歴
- `docs/archive/handover-20260429-1127.md` — 本セッション直前のスナップショット

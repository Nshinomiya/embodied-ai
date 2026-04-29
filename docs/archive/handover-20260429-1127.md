# Session Handover

**最終更新:** 2026-04-29 09:59

---

## 前提と目的 (Context & Intent)

実機 2 ページ統合テスト（F-3 / F-7）に着手するセッション。前回までで 1 ページ E2E は通っており、本セッションは

1. ページ 1 + ページ 2（オーバーラップあり）→ 結合 → 保存
2. F-9 二次 OCR の実装可能性検証

を目標に開始した。実走中に **PAL `chat` ツールが OCR 用途には構造的に不適**という設計上の発見があり、その対処として **OCR を OpenRouter 直叩きに標準化**する意思決定とコード変更まで完了した。

---

## 成果と変更箇所 (Outcomes & Changed Files)

### 既コミット（本セッション分）

- `1910a78` feat(screen-read): standardize OCR on direct OpenRouter API
  - `.claude/skills/screen-read/scripts/screen_read_helper.py` — `ocr` サブコマンド追加
  - `.claude/skills/screen-read/SKILL.md` — OCR ステップを `mcp__pal__chat` から `helper ocr` へ切替

### コミット内容詳細

- **`helper ocr` サブコマンド**
  - urllib.request ベース（追加依存なし）
  - `OPENROUTER_API_KEY` env を必須化、未設定時は `ok: false` で即終了
  - 定数: `OPENROUTER_URL`, `DEFAULT_OCR_MODEL=google/gemini-2.5-flash`, `DEFAULT_SECOND_OCR_MODEL=google/gemini-2.5-pro`, `RETRY_HTTP_CODES={429,500,502,503,504}`
  - F-15 のシステム指示を hard-code（行番号 / オーバーレイ / ステータスバー無視 + ```markdown フェンス抑制）
  - F-16 の指数バックオフ（1s → 2s → 4s, 最大 3 回）内蔵
  - `_strip_outer_fence` で返答全体を囲む ` ``` ... ``` ` を自動除去（内側コードフェンスは保持）
  - 出力 JSON: `{"ok": true, "text": ..., "model": ..., "attempts": ..., "usage": ...}`

- **SKILL.md 変更点**
  - 前提に `OPENROUTER_API_KEY` env export 必須を追加
  - 「4. OCR」を `mcp__pal__chat` から `$HELPER ocr ... | jq -r '.text'` へ書き換え
  - 「6. 疑義検知 + 二次 OCR」を `model=anthropic/claude-3.5-haiku` から `model=google/gemini-2.5-pro` に変更（Haiku は image 非対応のため）

### 実機テスト結果

- ページ 1（明所、夜帯）→ Gemini Flash で `## カイゼンチーム / ## GitHub で人生を管理する ...` を正しく抽出 → save-page OK
- ページ 2 一回目（PgDn 直後、Copilot Chat ポップアップ干渉）→ OCR 結果が断片化（「しまするなら『し』」等）。マージ用には不適と判断
- ページ 2 二回目（前ページ末尾「登録するなら...」を画面上部に残す位置で再撮影、Copilot ポップアップ閉じず）→ 同様に断片化。**Copilot Chat ポップアップが OCR 阻害要因と判明**

### F-9 二次 OCR 検証ログ（PAL 経由全モデル不可）

| モデル | 結果 |
|---|---|
| `anthropic/claude-3.5-haiku` | API エラー: image input non-supported |
| `anthropic/claude-haiku-4.5` | PAL バリデーションで弾かれる |
| `openai/gpt-4o-mini` | PAL バリデーションで弾かれる |
| `anthropic/claude-opus-4.1` | "no image was provided" と persona 拒否 |
| `openai/o3` | "no image was provided" と persona 拒否 |
| `google/gemini-2.5-pro` | 画像と無関係な persona boilerplate を返却（実害ハルシネーション） |
| `google/gemini-2.5-flash` | ✅ 唯一動作 |

---

## 検討と意思決定 (Decisions & Rationale)

- **判断:** OCR を `mcp__pal__chat` から **OpenRouter 直叩き**に標準化（一次 OCR も二次 OCR も）
  - **理由:** PAL `chat` は "engineering thought partner" の system prompt を注入する設計。Gemini Flash は素直に従うが、それ以外の vision モデルは persona に引っ張られて画像認識を拒否したり捏造する。OCR の責任境界として PAL は不適。OpenRouter API を helper から直接叩けば persona injection は無く、F-9 は `--model` 切替で素直に実装される
  - **代替案:** PAL 維持 + Gemini 系のみ使用 → 二次 OCR の独立性が確保できず F-9 検証としての意味が薄まる。あと PAL 構成変更の影響も受ける

- **判断:** F-9 の二次 OCR モデルを Haiku から `google/gemini-2.5-pro` に変更
  - **理由:** 元の Haiku は OpenRouter で image input をサポートしていない（claude-3.5-haiku エラー、claude-haiku-4.5 も同様）。Anthropic / OpenAI の vision モデルは PAL 経由で全滅、OpenRouter 直叩きでも persona 由来の挙動が確認されたため、当面は Gemini ファミリ内のグレード違いで二次 OCR を行う
  - **代替案:** Anthropic SDK 経由で Claude Opus 直接呼び出し → 認証情報・SDK 追加が必要、コスト高。MVP の範疇外

- **判断:** helper の HTTP 実装は `urllib.request` で stdlib 完結
  - **理由:** `requests` / `httpx` を入れると `screen_read` パッケージの最小依存方針（rapidfuzz だけ必須、cv2/Pillow/numpy は extra）を崩す。OCR HTTP のためだけに新規必須依存を増やしたくない
  - **代替案:** httpx 追加 → リトライや非同期が必要になった時の選択肢、現状必要なし

- **判断:** F-15 のシステム指示を helper 内 hard-code（SKILL.md からは消した）
  - **理由:** プロンプトインジェクション耐性は信頼境界の設計事項。skill 文を書き換えただけで耐性が落ちる構造を避け、helper 側で固定する。skill から `--user-prompt` で追記はできるが system_prompt は不変
  - **代替案:** SKILL.md に system prompt を書く → ユーザーや別 skill が誤って書き換えるリスク

---

## ハマった点・失敗したアプローチ (Friction & Anti-patterns)

- **問題:** 夜帯にページ 1 を撮影したら Gemini Flash が **完全にハルシネーション**（架空の「人材ソフトウェア」記事を生成）した
  - **試したこと:** `BLUR_VARIANCE_THRESHOLD=100` のチェックは通過（variance 1662）
  - **結果:** 低コントラスト画像（赤紫がかった薄暗いモニタ）でラプラシアン分散はエッジ検出を拾うが、vision モデルは「読めない」と認めず捏造する。**ブレ検知だけでは不十分**
  - **教訓:** preprocess に **コントラスト / 輝度チェック**を追加すべき。または OCR 後の sanity check（同モデル 2 回比較 → 内容差分検知）を入れる。今回は照明を明るくして回避

- **問題:** PAL `chat` を `claude-opus-4.1` / `o3` で OCR しようとしたら "no image was provided" と persona 拒否
  - **試したこと:** Gemini Flash で動作したので、PAL の whitelist で OK と仮定
  - **結果:** PAL は内部で "engineering thought partner" の system prompt を注入しており、Anthropic / OpenAI 系モデルは persona に従って OCR を engineering タスクではないと判断 → image を無視
  - **教訓:** **PAL は対話・思考補助ツール、OCR は別レイヤ**。境界を間違えるとハマる。OCR は責任境界として helper / SDK 直叩きが正解

- **問題:** Gemini 2.5 Pro が画像と無関係な「I am a helpful assistant」boilerplate を返した
  - **試したこと:** PAL chat に画像を渡して OCR 指示
  - **結果:** PAL の persona 注入と Pro の指示理解の組合せで、画像内容を完全に無視して箱書きを返答した（最悪のサイレント失敗）
  - **教訓:** vision モデルでも persona 拒否 / 捏造のパターンは存在する。**出力が画面の内容と関係するか** をプログラム的に検出する必要がある（将来の sanity check）

- **問題:** ページ 2 撮影で **Copilot Chat ポップアップ**「Pin selection to current chat prompt (Ctrl+Alt+X)」が画面に重なり、OCR が断片化した
  - **試したこと:** 撮り直し（位置調整）はしたがポップアップを閉じなかった
  - **結果:** OCR テキストにポップアップ文字列が紛れ、エディタ本文が部分的に欠落
  - **教訓:** 撮影前にエディタ画面を **ポップアップなし**にする運用ルールを追加。SKILL.md の前提に Copilot 通知ダイアログを閉じる手順を追加検討

- **問題:** PgDn 1 回での標準スクロールでは **オーバーラップが残らない**（VSCode は次ページの先頭に前ページ末尾を残さない）
  - **試したこと:** PgDn のみで撮影
  - **結果:** ページ 1 末尾「飽きてくる」とページ 2 先頭「これまで `git` を...」に共通行ゼロ → MERGE_UNCERTAIN 確実
  - **教訓:** ユーザーに **PgDn 後 Up キーで 5〜10 行戻す**運用を明示。SKILL.md の「8. 次ページ」に強調

---

## 次にやること (Next Steps)

### 1. live OCR テストの完走

1. [ ] `OPENROUTER_API_KEY` を export し helper ocr を実画像で動作確認（ページ 1 一枚で OK）
2. [ ] Copilot Chat ポップアップを閉じてからページ 2 を再撮影 → ページ 1 + 2 のマージを成功させる
3. [ ] 同じ画像で `--model google/gemini-2.5-pro` を試し、F-9 二次 OCR の差分が見えることを確認

### 2. 撮影前の品質ゲート強化（次回優先度高）

4. [ ] preprocess に **コントラスト/輝度チェック**を追加（夜帯ハルシネーション防止）。実装案: ヒストグラムの平均輝度が閾値外（暗すぎ・明るすぎ）なら blurry と同じ扱いで撮り直し要求
5. [ ] OCR 後の **長さ sanity check**（OCR 文字数が極端に少ない・極端に多い場合は疑義扱い）

### 3. SKILL.md 運用ルール追加

6. [ ] 撮影側 PC で **Copilot Chat ポップアップを Esc で閉じる**手順を「前提」セクションに追加
7. [ ] PgDn 後の **Up キー 5〜10 行戻し**を「8. 次ページ」に強調表示

### 4. F-13 救済 UI（マージ失敗時）

8. [ ] `uncertain_boundaries > 0` のとき、前ページ末尾画像と次ページ先頭画像を helper 経由で OCR 比較し、ユーザーに修正候補を提示する流れを SKILL.md に追加

### 5. クリーンアップ・運用改善

9. [ ] `wifi-cam-mcp/.env` を削除（認証は `.mcp.json` 集約済み）
10. [ ] ルーターで C220（`192.168.10.118`）の DHCP 固定割り当て設定

---

## 参考情報

### 現在の構成スナップショット

| 項目 | 値 |
|------|-----|
| プロジェクト直下 | `/home/slmbrcat/projects/embodied-ai/` |
| C220 IP / プリセット | `192.168.10.118` / token=`"1"` name=`screen-read` |
| 自動キャプチャ保存先 | `/tmp/wifi-cam-mcp/capture_<timestamp>.jpg` |
| OCR 経路 | OpenRouter API 直叩き（PAL は使わない） |
| OCR 必須環境変数 | `OPENROUTER_API_KEY` |
| 標準モデル | 一次 `google/gemini-2.5-flash` / 二次 `google/gemini-2.5-pro` |
| 接続済み MCP | wifi-cam / memory / system-temperature / sociality / pal（pal は OCR 以外で使用） |
| screen_read venv | `screen_read/.venv/`（uv 管理、Python 3.13.13） |
| pytest 結果 | 20 passed (merge 14 + preprocess 6) + helper エラーパス手動確認 |

### helper CLI 早見表（更新版）

```bash
HELPER='uv run --project screen_read python .claude/skills/screen-read/scripts/screen_read_helper.py'

# 画像処理
$HELPER preprocess /tmp/page.jpg
$HELPER same-page /tmp/a.jpg /tmp/b.jpg --threshold 2.0

# OCR（NEW: OpenRouter 直叩き）
$HELPER ocr --image /tmp/page.jpg                                # 一次（gemini-2.5-flash 既定）
$HELPER ocr --image /tmp/page.jpg --model google/gemini-2.5-pro  # F-9 二次 OCR

# レジューム + マージ
echo "$ocr_text" | $HELPER save-page --session-dir DIR --page 1 --image /tmp/page.jpg
$HELPER merge-save --session-dir DIR --vault ~/obsidian-vault --source "メモ"
```

### ドキュメント一覧
- `docs/要件定義.md` — F-1〜F-16 機能要件（F-9 の二次モデル指定は古い）
- `docs/アーキテクチャ.md` — コンポーネント・処理シーケンス
- `docs/結合アルゴリズム.md` — RapidFuzz 擬似コード
- `docs/CHRONICLE.md` — セッション履歴
- `docs/archive/handover-20260429-0958.md` — 本セッション直前のスナップショット

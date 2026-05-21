# Session Handover

**最終更新:** 2026-05-20 16:20

---

## 前提と目的 (Context & Intent)

screen-read スキルの実機運用フェーズ。前回 (2026-04-29) 以降スキル本体は安定しており、ユーザーが孤立 PC（Copilot Studio の Markdown 編集画面）から技術メモを Obsidian Vault に取り込む実用ワークフローとして使い始めた。今回のセッションは「実機で使ってみて出た不具合・運用ギャップを SKILL.md に還流する」が主目的。実装変更はゼロ、ドキュメント・スキル定義のみ。

## 成果と変更箇所 (Outcomes & Changed Files)

git status: `.claude/skills/screen-read/SKILL.md` のみ変更（+34, -2）。

- `.claude/skills/screen-read/SKILL.md` — 6 件の運用学びを追記後、blockquote 多用箇所を本文化して圧縮（269 → 234 行）
  - **4. OCR**: OpenRouter `content: None` 由来の `_strip_outer_fence(None)` AttributeError 時は同じ画像で 1 回手動リトライ
  - **6. プレビューと疑義検知**: 見出しレベル揺れ（`##` ↔ `###` ↔ `#`）/ `**...**` の `・・...・・` 化け / 番号付きリストの行欠落を疑義シグナルに追加
  - **8. 次ページ**: 「撮影前に必ず明示スクロール指示 → ユーザー確認後に `see`」をテンプレ化。例外（`page=1` 初回・「再撮影して」明示時）も明文化。`same-page` の `mean_abs_diff < 5` で同範囲なら勝手に進めず確認
  - **結合 + 保存**: `uncertain_boundaries: 0` でも silent 欠落リスクあり → 自己確認必須を明記
  - **自己確認（新セクション）**: 結合後に Claude 自身が全文 Read して 4 観点（連続性 / 記号化け / 境界跨ぎ / 不要要素残留）を点検 → `Edit` で直接補正 → ユーザーに一行報告。「通す前に完了宣言しない」明文化
  - **既存ファイルへの追記（新セクション）**: tempvault → overlap 判定 → `Edit` → 自己確認 → クリーンアップの 5 ステップ
- 副次: Auto Memory に [feedback-screen-read-scroll-prompt](~/.claude/projects/-home-slmbrcat-projects-embodied-ai/memory/feedback_screen_read_scroll_prompt.md) 追加

実機で生成された Obsidian 取り込み: `/mnt/c/Users/SlmbrCat/Documents/obsidian/pkm/00_Inbox/clip-20260520-1008.md`（全 141 行、7 ページ相当）。手動補正済み。

## 検討と意思決定 (Decisions & Rationale)

- **判断:** 「自己確認」を独立セクションとして必須化し、`uncertain_boundaries: 0` でも省略不可とした
  - **理由:** 今セッションで実際に `uncertain_boundaries: 0` のまま page-1↔page-2 境界で番号付きリストの `2. 製品 → 機能` が silent 欠落するケースを観測。merge.py の overlap カット (k=6) を信用するだけでは文書整合性は保証されないと判明
  - **代替案:** merge.py 側で欠落検出ロジックを追加することも検討したが、Markdown 構造を理解した上での判断は LLM 側が得意。決定論層は単純に保ち、整合性判定は Claude に委ねる方が三層モデル（下位＝決定論 / 上位＝Claude 判断）に整合
- **判断:** 「既存ファイルへの追記」は tempvault → 手動 Edit のフローに固定（`merge-save` を直接既存 Vault に向けない）
  - **理由:** `merge-save` は単一セッション完結設計で front matter ごと新規ファイルを書き出すため、既存 Vault に同名ファイルを向けると上書きされて元データが消える
  - **代替案:** helper に `append-to-existing` サブコマンドを追加することも検討したが、Markdown レベルの overlap 判定は人間 / Claude の目視が確実で、ロジック追加の費用対効果が薄いと判断
- **判断:** スクロール指示テンプレ化は SKILL.md 本体に明文化し、Auto Memory にも保存
  - **理由:** Auto Memory は文脈依存の好み、SKILL.md はタスクフロー本体（[[feedback-claude-code-layer-separation]] の役割分担に従う）。スクロール指示の出し方は両方の性質を持つので双方に置く方が抜けない

## ハマった点・失敗したアプローチ (Friction & Anti-patterns)

- **問題:** ユーザーが「次へ」と言ってもスクロールが反映されておらず、同じ範囲を 2-3 回ループ撮影してしまった
  - **試したこと:** `same-page` の `is_same: false` を信用してそのまま続行（mean_abs_diff=4.36 でしきい値は超えない）
  - **結果:** ピクセル差はカメラ位置の微振動だけで、テキスト範囲は同一。`is_same` の閾値だけでは「ユーザーがスクロールしたつもりだったが効いていなかった」状況を捕捉できない → 撮影前の明示指示と、同範囲を観測したら止まる対応を追加
- **問題:** OCR 結果が `## 6.` を `### 6.`、`## 7.` を `# 7.` と誤読する見出しレベル揺れが頻発
  - **試したこと:** 当初は merge 結果のまま保存
  - **結果:** Obsidian で開いた時の見出し階層が崩れる。Gemini Pro の癖として既知化し、疑義シグナル + 自己確認チェックリストに追加
- **問題:** merge.py の overlap カットで page 境界をまたぐ番号付きリストの中の 1 行（`2. 製品 → 機能`）が silent 欠落
  - **試したこと:** `boundaries[*].decision.score=93.6` で uncertain=false 扱い → そのまま結合
  - **結果:** drop した k=6 行に本来残すべき行が含まれていた。RapidFuzz スコアは「重複している」と判定したが、merge 側は前ページ末尾を保持し次ページ冒頭を drop する設計なので、次ページ側にしかない `2. 製品 → 機能` が消えた。自己確認で目視照合する以外の機械的検出は難しい
- **問題:** OpenRouter で `content: None` が返って `_strip_outer_fence` が AttributeError でクラッシュ
  - **試したこと:** F-16 リトライ（429/5xx）は通っているはずだが None は別パス
  - **結果:** 同じ画像を再度 OCR したら通った（過渡的な失敗）。helper 側の修正は後回しで OK、手順書に「同じ画像で 1 回手動リトライ」を明記

## 次にやること (Next Steps)

1. [ ] **clip-20260520-1008.md の中黒化け修正をユーザーが完了したか確認**（43 行目: `**` → `・・` の 1 箇所、前セッション分の指摘事項）
2. [ ] **screen-read の次回利用時に SKILL.md の自己確認セクションを実際に通す** — 運用しながら漏れ・冗長を発見したら追記改善。特に「不要要素の残留」項目（サイドバー語句混入）の検出パターンが充実する余地あり
3. [ ] **VOICEVOX 接続の前セッション残課題** — `0.0.0.0` バインド + Windows Firewall Private プロファイル限定方針（前回 HANDOVER 参照: `docs/archive/handover-20260520-1123.md`）。ユーザー側設定変更待ち
4. [ ] **SKILL.md 変更のコミット判断** — ユーザーが運用しながら改善する想定とのことなので、コミットするかは次セッション開始時に確認

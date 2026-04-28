# Session Handover

**最終更新:** 2026-04-28 20:18

---

## 前提と目的 (Context & Intent)

screen-read サブプロジェクトの **オーケストレーション層** を実装するセッション。前回までで `screen_read/merge.py`（決定論的ページ結合）と `screen_read/preprocess.py`（撮影前処理）のロジックは出来ていたが、これらを実運用で繋ぐ「撮影 → 前処理 → OCR → 疑義 → 結合 → Obsidian 保存」のフロー本体がまだなかった。

ユーザーから「スラッシュコマンドは `commands` ではなく `skills` では？」という方針指摘を受け、自然言語で自動発動させたいフローは `.claude/skills/<name>/` に置くと整理。スコープも改めて確認し、skill はプロジェクトスコープ（embodied-ai リポジトリ内）で実装する方針で進めた。

---

## 成果と変更箇所 (Outcomes & Changed Files)

### 既コミット（本セッションで作成）

- `518ddf7` feat(screen-read): add skill and CLI helper for capture-to-vault flow
  - `.claude/skills/screen-read/SKILL.md`（新規） — オーケストレーション本体
  - `.claude/skills/screen-read/scripts/screen_read_helper.py`（新規） — JSON 出力 CLI ヘルパー

### コミット内容詳細

- **`.claude/skills/screen-read/SKILL.md`**
  - frontmatter: `name: screen-read`, `description: 孤立PCの画面をWi-Fiカメラで連続撮影しMarkdown化してObsidian Vaultに保存する。...`
  - フロー: セッション初期化（vault 確認 / `SESSION_ID` / `${SESSION_DIR}` 作成）→ ページループ（撮影 → preprocess → cooldown → OCR → save-page → preview → 疑義検知 → same-page で終了判定）→ merge-save → cleanup
  - F-15 のシステム指示（プロンプトインジェクション耐性）を OCR プロンプトに inline 記載
  - F-16 の指数バックオフ（1s → 2s → 4s, 最大 3 回）を OCR ステップに記載
  - F-7 の終了判定二重化（`---END---` OR pixel-diff `is_same`）
  - F-12 のレジューム（`${SESSION_DIR}/page-*.json` を保持し、同 SESSION_ID で再開可能）
  - F-13 の救済 UI（`uncertain_boundaries > 0` で境界画像を並列提示）

- **`.claude/skills/screen-read/scripts/screen_read_helper.py`**
  - 4 サブコマンド全て JSON 出力 / exit code 0=success, 1=hard error
  - `preprocess <path>` — `screen_read.preprocess` の `measure_blur` / `strip_exif` / `resize_long_edge` を呼ぶ。blurry 時は `ok: false, blurry: true` で即座に返す（`--force` で続行可）
  - `same-page <a> <b>` — OpenCV でグレースケール読み込み、サイズ揃えて mean abs diff、閾値 2.0 未満で `is_same: true`
  - `save-page --session-dir --page --image [--text -]` — stdin から OCR テキストを受け取り `page-NNN.json` で保存。**末尾空白を `.rstrip()` で正規化**（重要）
  - `merge-save --session-dir [--output] [--vault] [--source]` — 全ページを順番に `best_overlap` + `merge_pages` で結合、`---END---` 除去、frontmatter 付きで Obsidian に保存
  - `sys.path.insert(0, REPO_ROOT / "screen_read")` で screen_read パッケージを再利用（`uv run --project screen_read` 経由で起動）

### ドライラン結果

```
preprocess (sharp 3040×3040 jpg + EXIF) → variance 1586.7, size [2000,2000], EXIF 除去確認
same-page (identical) → mean_abs_diff 0.56, is_same true
save-page x 2 → merge-save → score 100.0, k=3 overlap, uncertain_boundaries: 0
```

既存テスト: **20 passed in 1.00s**, ruff clean。

---

## 検討と意思決定 (Decisions & Rationale)

- **判断:** スラッシュコマンドではなく `.claude/skills/screen-read/SKILL.md` で実装
  - **理由:** screen-read は「画面を読み取って」と自然言語で頼んだら自動発動するフロー。`.claude/commands/<name>.md` は明示的な `/<name>` タイプを前提とし、エージェントの自律起動には対応しない。skill は frontmatter `description` を見て文脈で発動する
  - **代替案:** `.claude/commands/screen-read.md` → ユーザーから方針指摘あり却下。両方置く案も検討したが、運用フローが skill 一本で十分

- **判断:** skill 配置はユーザースコープ（`~/.claude/skills/`）ではなくプロジェクトスコープ（`embodied-ai/.claude/skills/`）
  - **理由:** screen-read は `screen_read/` モジュール / `wifi-cam-mcp` / `docs/要件定義.md` に依存する embodied-ai 専用機能。skill だけユーザースコープに上げるとリポジトリと skill の整合性が壊れる。Git にコミットして再現性を確保する
  - **代替案:** ユーザースコープ → memory-mcp の DB がユーザースコープなのは「Claude の長期記憶は人格として一つ」だから。skill とは判断基準が違う

- **判断:** helper CLI は `JSON 出力 + exit code` で skill と疎結合
  - **理由:** skill の Bash ステップで stdout を JSON パースしてエージェントが分岐できる。Python から直接呼び出すより skill 文章とのインターフェース境界が明確
  - **代替案:** Python ライブラリとして直接 import → skill が Python 環境に踏み込む必要があり境界がぼやける

- **判断:** `save-page` で `text.rstrip()` 正規化
  - **理由:** OCR レスポンスや `echo -e` で末尾改行 / 空行が入ると `best_overlap` の整列が 1 行分ズレ、`MAX_SHIFT=3` でカバーできない場合がある。ドライランで実際に MERGE_UNCERTAIN を生成してこの問題が顕在化
  - **代替案:** `best_overlap` 側で末尾 ignorable 行を切り落とす → コアアルゴリズムの挙動が変わるため避けた。境界での正規化のほうが副作用が小さい

- **判断:** MCP 設定の移動は実機テスト後の課題として保留
  - **理由:** memory-mcp はクロスプロジェクトで使いたい候補だが、現状 1 プロジェクトしか使っていない。`wifi-cam` / `system-temperature` は embodied-ai 専用ハードウェアなので **絶対にプロジェクトスコープ**
  - **代替案:** 即時で memory のみユーザースコープに昇格 → 実運用で「他プロジェクトでも欲しい」と感じてからで十分

---

## ハマった点・失敗したアプローチ (Friction & Anti-patterns)

- **問題:** ドライランで `merge-save` が `uncertain_boundaries: 1` を返した（本来 score 100 で結合できるべきデータ）
  - **試したこと:** `echo -e "...\n---END---" | save-page` でテキスト保存
  - **結果:** echo の trailing newline が末尾の空行となり、`best_overlap` の tail で k=3 整列が 1 行ズレた。`MAX_SHIFT=3` の範囲内だが、empty 行が join_for_compare で混ざるとスコアが大きく下がる
  - **教訓:** OCR テキストを skill から helper に渡す境界で **必ず `.rstrip()` 正規化**。trailing whitespace は merge アルゴリズムにとって毒になる

- **問題:** `Skill` ツール経由で `/handover` を起動しようとして拒否された
  - **試したこと:** `Skill(skill="handover", args="docs")` でモデル発動
  - **結果:** `disable-model-invocation: true` で起動不可。前回セッションでも同じ壁に当たっていた
  - **教訓:** `disable-model-invocation` の skill は **ユーザーが `/<name>` を打つ** か、テンプレートに従ってエージェントが手動で同等処理を書くしかない。フローの設計時にこの制約を考慮する

- **問題:** wifi-cam-mcp の `see` ツールが画像をどう返すか（base64 / file path）が確認できていない
  - **試したこと:** ドライランは検証用 jpeg を直接 `/tmp/` に置いて pipeline 通過を確認しただけで、実際の `see` 経由の image flow は通していない
  - **結果:** 実機テスト時に SKILL.md の「1. 撮影」ステップで実装詳細を埋める必要がある（必要なら Bash で base64 デコード or ファイルコピーを挟む）
  - **教訓:** MCP ツールの **戻り値スキーマ確認** は実装前にやる。今回は paper design で進めた

---

## 次にやること (Next Steps)

### 1. 実機 1 ページテスト

1. [ ] `mcp__wifi-cam__see` の戻り値を確認し、画像保存の Bash ステップを SKILL.md の「1. 撮影」に追記
2. [ ] 500 字 1 ページの実画面を撮影し、preprocess → PAL OCR → save-page → merge-save を通す
3. [ ] 出力 markdown が要件 F-4 / F-5（保存先・frontmatter）を満たすか確認

### 2. 統合テスト

4. [ ] 3 ページ（1500 字相当）の連続撮影 → 自動結合
5. [ ] `same-page` 終了判定の閾値（既定 2.0）を実画像で調整
6. [ ] `BLUR_VARIANCE_THRESHOLD` (100) を実カメラ環境でチューニング
7. [ ] `MIN_SCORE` / `TAIL_LINES` / `HEAD_LINES` を実 OCR テキストで微調整

### 3. クリーンアップ

8. [ ] `wifi-cam-mcp/.env` を削除（認証は `.mcp.json` 集約済み）
9. [ ] ルーターで C220（`192.168.10.118`）の DHCP 固定割り当て設定
10. [ ] 実運用後、memory-mcp を `claude mcp add --scope user` でユーザースコープに昇格するか判断

---

## 参考情報

### 現在の構成スナップショット

| 項目 | 値 |
|------|-----|
| プロジェクト直下 | `/home/slmbrcat/projects/embodied-ai/` |
| C220 IP | `192.168.10.118`（ONVIF port 2020） |
| memory DB | `~/.claude/memories/memory.db` |
| 接続済み MCP | wifi-cam / memory / system-temperature / sociality |
| screen_read venv | `screen_read/.venv/`（uv 管理、Python 3.13.13） |
| pytest 結果 | 20 passed (merge 14 + preprocess 6) |
| skill | `.claude/skills/screen-read/SKILL.md` + `scripts/screen_read_helper.py` |

### モジュール構成

```
embodied-ai/
├── screen_read/
│   ├── pyproject.toml          # rapidfuzz / [preprocess] / [dev]
│   ├── merge.py                # 決定論的ページ結合（rapidfuzz）
│   ├── preprocess.py           # ブレ検知 / EXIF 除去 / リサイズ
│   ├── tests/
│   │   ├── test_merge.py       # 14 ケース
│   │   └── test_preprocess.py  # 6 ケース
│   └── uv.lock
└── .claude/skills/screen-read/
    ├── SKILL.md                # オーケストレーション
    └── scripts/screen_read_helper.py  # JSON 出力 CLI（preprocess/same-page/save-page/merge-save）
```

### helper CLI 早見表

```bash
HELPER='uv run --project screen_read python .claude/skills/screen-read/scripts/screen_read_helper.py'

$HELPER preprocess /tmp/page.jpg                            # blur+EXIF+resize
$HELPER same-page /tmp/a.jpg /tmp/b.jpg --threshold 2.0     # 終了判定
echo "ocr text" | $HELPER save-page --session-dir DIR --page 1 --image /tmp/page.jpg
$HELPER merge-save --session-dir DIR --vault ~/obsidian-vault --source "メモ"
```

### ドキュメント一覧
- `docs/要件定義.md` — F-1〜F-16 機能要件
- `docs/アーキテクチャ.md` — コンポーネント・処理シーケンス・リスク表
- `docs/結合アルゴリズム.md` — RapidFuzz 擬似コード（merge.py の参照元）
- `docs/CHRONICLE.md` — セッション履歴
- `docs/archive/handover-20260428-2017.md` — 本セッション直前のスナップショット

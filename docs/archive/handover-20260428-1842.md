# Session Handover

**最終更新:** 2026-04-28 17:48

---

## 前提と目的 (Context & Intent)

本セッション（2026-04-28 後半）の目的は、**screen-read サブプロジェクトの実装着手**。前半セッションで embodied-ai の開発環境構築と Tapo C220 の接続確認まで完了したため、いよいよ docs/ に設計だけが存在していた screen-read（孤立 PC の画面を撮影 → OCR → 結合 → Obsidian 保存するパイプライン）の Python 実装を始めるフェーズに入った。

最初のマイルストーンとして、`docs/結合アルゴリズム.md` の擬似コードを実コードに落とし、ユニットテストでロックダウンすることを目標に置いた。

---

## 成果と変更箇所 (Outcomes & Changed Files)

### 新規追加: `screen_read/` パッケージ（未コミット、git status `?? screen_read/`）

- `screen_read/pyproject.toml` — uv 管理の独立サブパッケージ。`rapidfuzz>=3.5` を必須依存、`Pillow / opencv-python / numpy` を `preprocess` extra、`pytest / ruff` を `dev` extra。`hatchling` ビルド。
- `screen_read/merge.py` — 決定論的ページ結合アルゴリズム本体。擬似コードからの実装移植。
  - `compute_in_code_mask` をページ全体で生成してからスライスする設計を維持
  - `normalize_for_compare` / `join_for_compare` は比較専用、保存テキストにはオリジナルを保持
  - `MIN_SCORE=91.0`, `MIN_SAFE_K=3`, `MAX_PAGES=20` の既定値
  - `OverlapDecision` / `MergeMeta` を dataclass として定義（擬似コードの dict より型安全）
- `screen_read/tests/test_merge.py` — 14 ケースのユニットテスト
  - in_code マスクのスライス耐性
  - 正規化が保存テキストに漏れないことの検証（`“quoted”` と `—` がそのまま残る）
  - 短い・低多様性の重複が採用されないこと
  - `MERGE_UNCERTAIN` フラグの挙動
- `screen_read/tests/__init__.py` — 空ファイル
- `screen_read/uv.lock` — 依存ロック

### 既コミット（2 件、本セッション前半分）

- `484c629` docs(claude): correct memory-mcp implementation details — CLAUDE.md の ChromaDB 記載を SQLite + sentence-transformers + BM25 + Hopfield に修正
- `39b6373` docs: add screen-read sub-project design docs and session handover — docs/ 以下の設計ドキュメント 7 ファイルを追加（CHRONICLE / HANDOVER / 要件定義 / アーキテクチャ / 結合アルゴリズム / archive 2 件）

### テスト結果

```
14 passed in 0.10s
ruff check .  →  All checks passed!
```

---

## 検討と意思決定 (Decisions & Rationale)

- **判断:** screen_read を `desire-system/` と同じ「フラットな uv パッケージ」構造で配置（src レイアウトを使わない）
  - **理由:** 既存サブプロジェクトの慣習に揃える。`merge.py` 単一モジュールから始めるため src/ 階層は過剰
  - **代替案:** src レイアウト → 将来 MCP 化する時に移行すればよい

- **判断:** `OverlapDecision` / `MergeMeta` を dataclass で型付け
  - **理由:** 擬似コードでは `__dict__` で dict 化していたが、メタの形を呼び出し側が型として扱えた方が保守しやすい
  - **代替案:** dict のまま → 型エラーが実行時まで隠れるため不採用

- **判断:** preprocess（Pillow / opencv-python / numpy）を optional extra に分離
  - **理由:** merge.py 単体テストでは画像処理依存は不要。撮影前処理を実装するときに `--extra preprocess` を指定する流れ
  - **代替案:** 必須依存に含める → CI / 軽量検証時の依存ダウンロードコストが増えるため不採用

- **判断:** `compute_in_code_mask` でフェンス行自身は「pre-toggle 状態」を返す（擬似コード通り）
  - **理由:** 開く ``` は outside、閉じる ``` は inside と扱うことで、tail スライスが閉じフェンスを含む場合でもマスクが破綻しない
  - **代替案:** フェンス行は両方 inside に倒す → 開きフェンス自体の正規化が変わって比較スコアに影響しうる

- **判断:** テストでは `MIN_SAFE_K` と `has_diversity` の組み合わせをチェックする 1 ケース（`test_best_overlap_skips_short_low_diversity_match`）を必ず通す
  - **理由:** 短い記号 `---` だけで偶発マッチして結合してしまう事故が、運用で最も後から気づきにくいバグ
  - **代替案:** OR 条件のテストだけ → 多様性条件の単独テストは関数単位ですでにあるが、`best_overlap` 統合での挙動こそ守りたい

---

## ハマった点・失敗したアプローチ (Friction & Anti-patterns)

- **問題:** `git status` を screen_read ディレクトリ内で実行すると `?? ./` という曖昧な出力になり、未追跡ファイルの中身が見えない
  - **試したこと:** 普通の `git status --short` のみ
  - **結果:** プロジェクトルートに移動してから `git status --short` を実行すると `?? screen_read/` と出るが、サブパッケージ内の個別ファイルを見るには `cd <subdir> && git status --short --untracked-files=all` が必要
  - **教訓:** サブパッケージのコミット前確認はプロジェクトルートと当該サブディレクトリの両方で `git status` を確認する

（merge.py 実装自体は擬似コードが完成度高く、想定外のハマりはなし）

---

## 次にやること (Next Steps)

### 直近: コミット

1. [ ] `screen_read/` をコミット
   ```bash
   cd /home/slmbrcat/projects/embodied-ai
   git add screen_read/
   git commit -m "feat(screen-read): add deterministic page merger"
   git push
   ```

### 撮影前処理の実装（要件 F-9 系）

2. [ ] `screen_read/preprocess.py` を新規作成
   - **ブレ検知**: ラプラシアン分散、閾値 100 未満で再撮影要求（OpenCV）
   - **EXIF 除去**: `exiftool -all=` を subprocess で呼ぶ。`exiftool` が無い環境では Pillow で `Image.open` → 新 `Image` に paste して保存し直す方法のフォールバック
   - **リサイズ**: 長辺 1600-2000px、Pillow `Image.thumbnail` で十分
   - **撮影クールダウン**: 500ms（呼び出し側で `time.sleep` でよいが、ここに定数として置く）
   - 依存: `uv sync --extra preprocess` で Pillow / opencv-python / numpy が入る

3. [ ] `screen_read/tests/test_preprocess.py` を作成
   - サンプル画像（テスト用に小さい JPEG を tests/fixtures/ に置く or 動的生成）
   - ぼやけた画像でブレ検知が True を返すこと
   - リサイズで長辺が 1600-2000px に収まること
   - EXIF 除去後に `Image.open(out).getexif()` が空になること

### スラッシュコマンド

4. [ ] `.claude/commands/screen-read.md` を作成（embodied-ai リポジトリ内）
   - フロー: 撮影 → ブレ検知 → クールダウン → EXIF 除去 → リサイズ → `mcp__pal__chat` (Gemini Flash) → `merge_pages` → 疑義検知 → プレビュー → frontmatter → Obsidian 保存
   - プロンプトインジェクション対策のシステム指示を含める
   - 429/5xx は指数バックオフ最大 3 回
   - レジューム機能（`tmp/{session_id}-{page}.json` 逐次保存）

### クリーンアップ・運用

5. [ ] `wifi-cam-mcp/.env` を削除（認証は `.mcp.json` 集約済み）
6. [ ] ルーターで C220（`192.168.10.118`）の DHCP 固定割り当て設定

### テスト・チューニング

7. [ ] 単体テスト: 500 字 1 ページの OCR → 保存
8. [ ] 統合テスト: 3 ページ（1500 字）連続撮影 → 自動結合
9. [ ] 実サンプルで `MIN_SCORE` / `TAIL_LINES` / `HEAD_LINES` をチューニング

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
| pytest 結果 | 14 passed |

### ドキュメント一覧
- `docs/要件定義.md` — F-1〜F-16 機能要件
- `docs/アーキテクチャ.md` — コンポーネント・処理シーケンス・リスク表
- `docs/結合アルゴリズム.md` — RapidFuzz 擬似コード（実装の参照元）
- `docs/CHRONICLE.md` — セッション履歴
- `docs/archive/handover-20260428-1748.md` — 本セッション直前のスナップショット

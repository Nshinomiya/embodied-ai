# Session Handover

**最終更新:** 2026-04-28 18:43

---

## 前提と目的 (Context & Intent)

screen-read サブプロジェクトの実装を merge.py に続いて推進するセッション。前回のハンドオーバ「次にやること 2」に従い、`screen_read/preprocess.py`（撮影前処理: ブレ検知・EXIF 除去・リサイズ・撮影クールダウン）を実装し、ユニットテストでロックダウンするのが本セッションのゴール。

加えて、HANDOVER の Next Steps 4 で `.claude/commands/screen-read.md` を作る予定だったが、ユーザーから「commands ではなく skills では？」との指摘があり、画面読取りは「自動発動」が自然なため `.claude/skills/screen-read/SKILL.md` に方針変更した（実装は次セッション）。

---

## 成果と変更箇所 (Outcomes & Changed Files)

### 既コミット（本セッションで作成）

- `267cc04` feat(screen-read): add pre-OCR image preprocessing
  - `screen_read/preprocess.py`（新規, 108 行） — `measure_blur` / `strip_exif` / `resize_long_edge` / 定数 4 種
  - `screen_read/tests/test_preprocess.py`（新規, 6 ケース）

### コミット内容詳細

- **`screen_read/preprocess.py`**
  - `BLUR_VARIANCE_THRESHOLD = 100.0`（F-10 既定値）, `RESIZE_LONG_EDGE_MAX = 2000`, `RESIZE_LONG_EDGE_MIN = 1600`, `CAPTURE_COOLDOWN_SECONDS = 0.5`
  - `measure_blur(path) -> BlurCheck` — OpenCV `Laplacian(..., CV_64F).var()`。`BlurCheck.is_blurry` はしきい値未満で True
  - `strip_exif(path)` — `shutil.which("exiftool")` で分岐: あれば `exiftool -overwrite_original -all=`、無ければ `Image.new + paste` 経由で再エンコード
  - `resize_long_edge(path, max_long_edge=2000)` — 長辺超過時のみ `LANCZOS` で縮小、JPEG は quality=95 で保存。**拡大はしない**（min 側はチューニング指針として定数のみ用意）
  - `cv2` / `PIL` は関数内で遅延インポート → `merge.py` 単体テストでは preprocess extra 無しでも動作

- **`screen_read/tests/test_preprocess.py`**
  - `pytest.importorskip` で PIL / cv2 / numpy が無い環境ではスキップ
  - 鮮鋭画像（チェッカーボード）/ ぼやけ画像（線形グラデーション）を `np.random` で動的生成
  - exiftool 経路 + `monkeypatch.setattr(shutil, "which", lambda _: None)` で Pillow フォールバック経路の両方をテスト

### テスト結果

```
20 passed in 0.80s   (merge 14 + preprocess 6)
ruff check .  →  All checks passed!
```

---

## 検討と意思決定 (Decisions & Rationale)

- **判断:** `cv2` / `PIL` を関数内で遅延インポート
  - **理由:** `merge.py` だけ動かしたい場面（CI 軽量レーン・素早いユニットテスト）で preprocess extra をインストールしないで済む。pyproject.toml の optional-dependencies 分離と整合
  - **代替案:** モジュール先頭で import → preprocess extra 必須化されてしまうため不採用

- **判断:** `strip_exif` のフォールバックは `Image.new + paste` 経由（`getdata`/`putdata` ではなく）
  - **理由:** Pillow 14（2027-10-15 リリース予定）で `Image.Image.getdata` が削除予定の DeprecationWarning が出た。`paste` ベースに切り替えて将来互換を確保
  - **代替案:** `getdata`/`putdata` のまま → 警告抑制でしのげるが廃止予定 API を持ち込む意味がない

- **判断:** `resize_long_edge` は縮小のみ（既に閾値以下なら no-op で元ファイルそのまま）
  - **理由:** OCR コスト削減が目的。低解像度を引き延ばしても情報量は増えない。ファイル書き換え無しは「変更があったかどうか」を呼び出し側が `Path.stat` で見られる利点もある
  - **代替案:** 常に最大解像度に揃える → 余計なリサイズで品質劣化＋無駄 IO

- **判断:** スラッシュコマンドではなく `.claude/skills/screen-read/SKILL.md` で実装する方針に転換
  - **理由:** screen-read は「画面を読み取って」と自然言語で頼んだら自動発動するのが自然。`.claude/commands/` は明示的に `/screen-read` を打つ前提で、frontmatter `description` を見たエージェントの自律起動には対応しない
  - **代替案:** `.claude/commands/screen-read.md` のまま → 毎回ユーザーが `/screen-read` をタイプする運用は MVP のフロー（撮影→確認→次ページ）と相性が悪く却下

---

## ハマった点・失敗したアプローチ (Friction & Anti-patterns)

- **問題:** `Pillow.Image.getdata()` の DeprecationWarning が pytest 出力に紛れ込んだ
  - **試したこと:** 当初は擬似コード由来の `getdata`/`putdata` で実装
  - **結果:** Pillow 14 で削除予定の API。`Image.new(mode, size); clean.paste(src)` に書き直して解消
  - **教訓:** 新規実装時に `pytest -v` の warnings summary を必ず確認する

- **問題:** `/handover` skill を `Skill` ツールから呼び出そうとして失敗
  - **試したこと:** `Skill(skill="handover", args="docs")` で起動
  - **結果:** `disable-model-invocation: true` のため拒否。skill によってはユーザー起動限定があると改めて確認
  - **教訓:** モデル起動不可の skill はユーザーに `/handover` を打ってもらうか、テンプレートに従って手動で同等処理を書く

---

## 次にやること (Next Steps)

### 1. screen-read skill の実装

1. [ ] `.claude/skills/screen-read/SKILL.md` を作成
   - frontmatter: `name: screen-read`, `description: 孤立PCの画面をWi-Fiカメラで連続撮影しMarkdown化してObsidian Vaultに保存する...`（自然言語で「画面を読み取って」と言われた時に発動できる説明）
   - フロー: 撮影 → `measure_blur` → `CAPTURE_COOLDOWN_SECONDS` → `strip_exif` → `resize_long_edge` → `mcp__pal__chat` (Gemini Flash) → `merge_pages` → 疑義検知 → プレビュー → frontmatter → Obsidian 保存
   - F-15 のシステム指示（プロンプトインジェクション耐性）を OCR プロンプトに含める
   - F-16 の指数バックオフ（429/5xx, 最大 3 回）
   - F-12 のレジューム機能（`tmp/{session_id}-{page}.json` 逐次保存）
   - F-7 の終了判定二重化（`---END---` OR 画像 SSIM 連続同一）
2. [ ] 必要に応じて `.claude/skills/screen-read/scripts/ocr_page.py` を分離（PAL 呼び出し + retry ラッパ）

### 2. クリーンアップ

3. [ ] `wifi-cam-mcp/.env` を削除（認証は `.mcp.json` 集約済み）
4. [ ] ルーターで C220（`192.168.10.118`）の DHCP 固定割り当て設定

### 3. テスト・チューニング

5. [ ] 単体テスト: 500 字 1 ページの OCR → 保存
6. [ ] 統合テスト: 3 ページ（1500 字）連続撮影 → 自動結合
7. [ ] 実サンプルで `BLUR_VARIANCE_THRESHOLD` / `MIN_SCORE` / `TAIL_LINES` / `HEAD_LINES` をチューニング

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

### モジュール構成

```
screen_read/
├── pyproject.toml          # rapidfuzz / [preprocess] Pillow,opencv-python,numpy / [dev] pytest,ruff
├── merge.py                # 決定論的ページ結合（rapidfuzz）
├── preprocess.py           # ブレ検知 / EXIF 除去 / リサイズ / クールダウン
├── tests/
│   ├── __init__.py
│   ├── test_merge.py       # 14 ケース
│   └── test_preprocess.py  # 6 ケース
└── uv.lock
```

### ドキュメント一覧
- `docs/要件定義.md` — F-1〜F-16 機能要件
- `docs/アーキテクチャ.md` — コンポーネント・処理シーケンス・リスク表
- `docs/結合アルゴリズム.md` — RapidFuzz 擬似コード（merge.py の参照元）
- `docs/CHRONICLE.md` — セッション履歴
- `docs/archive/handover-20260428-1842.md` — 本セッション直前のスナップショット

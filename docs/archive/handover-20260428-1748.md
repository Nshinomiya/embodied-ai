# Session Handover

**最終更新:** 2026-04-28 17:12

---

## 前提と目的 (Context & Intent)

本セッション（2026-04-28）の主目的は、**embodied-ai プロジェクトの開発環境構築と Tapo C220 の初期接続確認**。前セッション（2026-04-22）でドキュメントレビューが完了していたため、今回は「実機を立ち上げる」フェーズに進んだ。

ユーザーは Tapo C220 カメラを購入済み、それ以外（uv・ffmpeg・MCP 依存・カメラセットアップ・MCP 接続設定）はすべて未着手の状態からスタート。最終的にカメラ越しの視覚応答までを確認した。

---

## 成果と変更箇所 (Outcomes & Changed Files)

### 環境構築

- **uv インストール**: `curl -LsSf https://astral.sh/uv/install.sh | sh` で 0.11.8 を `/home/slmbrcat/.local/bin/` に配置
- **ffmpeg インストール**: `apt-get install ffmpeg`（v6.1.1）
- **全 MCP 依存関係の一括インストール**: `scripts/install-mcps.sh` 実行
  - desire-system / memory-mcp / system-temperature-mcp / tts-mcp / usb-webcam-mcp / wifi-cam-mcp / x-mcp / sociality-mcp（8 サブパッケージ含む）すべて成功
  - PyTorch + CUDA + Whisper + sentence-transformers 含むフル依存（合計約 2GB ダウンロード、~10分）

### 設定ファイル作成

- **`.mcp.json`**（プロジェクトルート）: wifi-cam / memory / system-temperature / sociality の 4 サーバーを登録。tts・x-mcp は API キー未取得のため除外。
- **`socialPolicy.toml`**（プロジェクトルート）: `examples/configs/socialPolicy.example.toml` をコピー
- **`~/.claude/memories/`**（ユーザースコープ）: memory-mcp の SQLite DB 配置先を作成

### 動作確認

- wifi-cam: ONVIF 経由で C220（`192.168.10.118`）に接続成功、`see` でカメラ越しの視覚応答を確認
- memory / system-temperature / sociality: MCP 接続成功

### 認証情報の集約

- 当初 `wifi-cam-mcp/.env` に認証情報を書いたが、README の方針（`.mcp.json` の `env` フィールドに集約）に従ってユーザー側で `.mcp.json` に移動。`.env` は削除予定。

---

## 検討と意思決定 (Decisions & Rationale)

- **判断:** `.mcp.json` 初版には wifi-cam / memory / system-temperature / sociality のみ登録
  - **理由:** ElevenLabs / xAI / X Developer の API キーが未取得。声と SNS 機能は後回しでよい。usb-webcam は USB カメラ未所持のため除外
  - **代替案:** 全サーバー登録（プレースホルダー入り）→ 起動時エラーが出続けるため不採用

- **判断:** 認証情報は `.mcp.json` の `env` に集約（個別 `.env` は使わない）
  - **理由:** README に明示的にそう書いてある。複数の認証情報ソースが並立すると競合・移行が困難になる
  - **代替案:** `wifi-cam-mcp/.env` を残す → 当初こちらで作業したがユーザー指摘で `.mcp.json` に移行

- **判断:** memory-mcp の DB はユーザースコープ（`~/.claude/memories/`）に置く
  - **理由:** デフォルトパスがそうなっており、記憶はプロジェクトを跨いで永続すべき性質のもの。プロジェクトスコープに置く理由がない
  - **代替案:** プロジェクト直下 → 別プロジェクトで Claude を立ち上げると記憶を引き継げないため不採用

### 副次的な気づき（ドキュメント反映候補）

- **memory-mcp は ChromaDB を使っていない**: CLAUDE.md には「ChromaDB」と記載があるが、実装は SQLite + numpy + sentence-transformers + BM25 + Modern Hopfield Network の自前ハイブリッド検索。CLAUDE.md の記載を実装に合わせて更新する必要がある
- **C220 の ONVIF 接続は port 2020 で問題なし**: pytapo + ONVIF 経由で `update_xaddrs` → `see` まで通った。RTSP フォールバックは現時点で不要

---

## ハマった点・失敗したアプローチ (Friction & Anti-patterns)

- **問題:** wifi-cam の初回接続失敗（`192.168.1.118` に ping 100% loss）
  - **原因:** ユーザーがメモした IP（`192.168.1.118`）が実際のカメラ IP（`192.168.10.118`）と異なっていた。サブネットを `1` と思い込んでいた
  - **結果:** Tapo アプリの「端末情報」で再確認 → `.mcp.json` で `192.168.10.118` に修正 → 接続成功
  - **教訓:** カメラ接続失敗時はまず ping で到達性を確認、次に ONVIF ポート確認の順で切り分ける

- **問題:** memory-mcp が起動時にクラッシュ（`sqlite3.OperationalError: unable to open database file`）
  - **原因:** デフォルト DB 配置先 `~/.claude/memories/` ディレクトリが存在しなかった。memory-mcp はディレクトリを自動作成しない
  - **結果:** `mkdir -p ~/.claude/memories` で解決
  - **教訓:** memory-mcp の最初の起動前にディレクトリを必ず作成。インストール手順に組み込むべき

- **問題:** `wifi-cam-mcp/.env` を作ってから `.mcp.json` にも認証情報を入れて二重管理になりかけた
  - **原因:** README の冒頭ではなく中盤に「`.env` を作るな」の警告がある
  - **結果:** ユーザー指摘で `.mcp.json` 一本化。`.env` は削除予定
  - **教訓:** README の `⚠️ 認証情報の管理` セクションを最初に確認

---

## 次にやること (Next Steps)

### クリーンアップ（短時間で終わる）

1. [ ] `wifi-cam-mcp/.env` を削除（認証情報は `.mcp.json` に集約済み）
2. [ ] ルーターで C220（`192.168.10.118`）の DHCP 固定割り当てを設定。再起動で IP が変わると `.mcp.json` 再編集になる
3. [ ] CLAUDE.md の「ChromaDB」記載を「SQLite + numpy + sentence-transformers + BM25 + Hopfield」に修正

### 任意: 残りの MCP サーバー有効化

4. [ ] tts-mcp: ElevenLabs API キー or VOICEVOX を用意して `.mcp.json` に追加
5. [ ] x-mcp: xAI + X Developer の API キー一式を用意して `.mcp.json` に追加
6. [ ] usb-webcam-mcp: USB カメラを用意するなら（任意）

### 主要タスク: screen-read サブプロジェクトの実装

> **背景**: docs/ には設計（要件定義・アーキテクチャ・結合アルゴリズム）が完成しているが実装はゼロ。本セッションで身体側の準備は完了したので、いよいよ実装に着手できる。

7. [ ] `結合アルゴリズム.md` の擬似コードを Python に実装
   - 配置先: `embodied-ai/screen_read/merge.py`（または `src/merger.py`）
   - 依存: `rapidfuzz`, `Pillow`（リサイズ用）, `exiftool`（EXIF 除去）
   - 注意点:
     - `compute_in_code_mask` はページ全体で生成→スライス（重要）
     - `normalize_for_compare` は比較専用、保存テキストはオリジナル保持
     - `MIN_SCORE=91`（初期値）、`MIN_SAFE_K=3`

8. [ ] ブレ検知（ラプラシアン分散、閾値 100）と撮影クールダウン（500ms）の実装
9. [ ] レジューム機能（`tmp/{session_id}-{page}.json` 逐次保存）の実装

### 実装: スラッシュコマンド

10. [ ] `.claude/commands/screen-read.md` の作成
    - 全体フロー: 撮影→EXIF 除去→リサイズ→OCR→疑義検知→結合→プレビュー→保存
    - プロンプトインジェクション対策のシステム指示を含める
    - 429 指数バックオフリトライ（最大 3 回）

### テスト

11. [ ] 単体テスト: 500 字 1 ページの OCR ＋保存
12. [ ] 統合テスト: 3 ページ（1500 字）連続撮影＋自動結合
13. [ ] パラメータチューニング: `MIN_SCORE`, `TAIL_LINES`, `HEAD_LINES` を実サンプルで調整

---

## 参考情報

### 現在の構成スナップショット（2026-04-28 17:12）

| 項目 | 値 |
|------|-----|
| プロジェクト直下 | `/home/slmbrcat/projects/embodied-ai/` |
| C220 IP | `192.168.10.118`（ONVIF port 2020） |
| 認証情報の置き場所 | `.mcp.json` の `env` のみ |
| memory DB | `~/.claude/memories/memory.db` |
| socialPolicy | `socialPolicy.toml`（プロジェクトルート、example をコピー） |
| 接続済み MCP | wifi-cam / memory / system-temperature / sociality |
| 未接続 MCP | tts / x-mcp / usb-webcam（API キー or HW 未取得） |

### rtsp フォールバックコマンド（pytapo 破断時の備え）
```bash
ffmpeg -rtsp_transport tcp -i rtsp://<TAPO_USER>:<TAPO_PASS>@192.168.10.118/stream1 \
       -frames:v 1 -q:v 2 /tmp/capture.jpg
```

### Gemini Flash 画像トークン課金の注意点
4MP（2688×1520px）をそのまま送信するとトークンコストが増大する。必ず長辺 1600-2000px にリサイズしてから送信すること。

### ドキュメント一覧
- `docs/要件定義.md` — 機能要件 F-1〜F-16・非機能要件・決定事項
- `docs/アーキテクチャ.md` — コンポーネント・処理シーケンス・リスク表
- `docs/結合アルゴリズム.md` — RapidFuzz 擬似コード・疑義検知ルール
- `docs/CHRONICLE.md` — セッション履歴
- `CLAUDE.md` — プロジェクト指示（※ ChromaDB 記載は実装と乖離あり、要修正）

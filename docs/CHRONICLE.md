# Session Chronicle

Chronological log of session summaries.

- **[2026-04-21 15:45]** — プロジェクト立ち上げ・要件定義／アーキテクチャ策定。QRコード生成ツール凍結を受けた光学的テキスト持ち出し方式として`Nshinomiya/embodied-ai`の`wifi-cam-mcp`流用を決定。OCRはPAL経由`google/gemini-2.5-flash`主力（コスパ重視）。方式B（連続撮影＋ページ結合）をMVPとし、既存MCP無改造＋スラッシュコマンド層で実装する方針。保存先は`00_Inbox/`既定。開発リポジトリは別途用意。
- **[2026-04-21 16:10]** — PAL（gpt-5.1）によるレビューを反映。重要な設計変更: (1)ページ結合をLLMプロンプトからRapidFuzzベースの決定論的アルゴリズムに変更、(2)OCRをGemini Flash主力＋疑義ページのみHaiku二次OCRのハイブリッド化、(3)終了判定を`---END---`＋画像SSIM連続同一の二重化、(4)撮影前ラプラシアン分散ブレ検知追加、(5)成功基準を「誤字ゼロ」から「疑義ハイライト率＋誤字率」に変更、(6)VSCode Word Wrap OFFを撮影運用要件に明記、(7)HDMIキャプチャをバックアップ案として記載。結合アルゴリズム仕様（擬似コード＋疑義検知ルール）を別ドキュメント化。
- **[2026-04-21 19:12]** — handoverスキルでセッション全体のまとめを生成。旧HANDOVER.mdを`archive/handover-20260421-1912.md`に退避し、要件定義・アーキテクチャ・結合アルゴリズムの3ドキュメントを中核とする体制で次セッション（開発リポジトリ構築・ローカル結合モジュール実装）へ引き継ぎ。
- **[2026-04-22 00:30]** — gpt-5.2＋gemini-2.5-proのコンセンサスレビューを実施し、3ドキュメントに多数の指摘を反映（F-11〜F-16追加・結合アルゴリズムのin_codeバグ修正・MIN_SCORE引き上げ・リサイズMVP格上げ等）。ユーザー確認事項（撮影場所・HDMIポリシーNG・情報機密度・前処理方針）も反映。pytapo破断対策をRTSPフォールバックに確定。
- **[2026-04-28 17:12]** — embodied-ai 開発環境構築：uv / ffmpeg をインストールし `scripts/install-mcps.sh` で全 MCP 依存を一括導入。`.mcp.json` で wifi-cam / memory / system-temperature / sociality を接続、Tapo C220（`192.168.10.118`）越しの視覚応答まで確認。ハマりは IP 取り違え（`.1.118` → `.10.118`）と memory DB 用 `~/.claude/memories/` 未作成。memory-mcp 実装が ChromaDB ではなく SQLite + sentence-transformers + BM25 + Hopfield であることを発見し CLAUDE.md を修正。
- **[2026-04-28 17:48]** — screen-read 実装着手：`screen_read/` を uv パッケージとして作成し `merge.py` に決定論的ページ結合アルゴリズムを実装。14 ケースのユニットテスト（in_code マスクのスライス耐性・正規化漏れ防止・低多様性偶発マッチ抑制・MERGE_UNCERTAIN 挙動）が全て通過、ruff も clean。次は撮影前処理（ブレ検知・EXIF 除去・リサイズ）。
- **[2026-04-28 18:43]** — screen-read 撮影前処理を実装：`preprocess.py` にラプラシアン分散ブレ検知・EXIF 除去（exiftool 優先 + Pillow フォールバック）・長辺 ≤2000px リサイズ・撮影クールダウン定数を追加。重い依存（cv2/PIL/numpy）は遅延インポートで preprocess extra 切り離しを維持。pytest 6 ケース追加で計 20 通過、ruff clean。スラッシュコマンドは `.claude/commands/` ではなく `.claude/skills/screen-read/` で実装する方針に転換（自動発動が自然なため）。
- **[2026-04-28 20:18]** — screen-read オーケストレーション層を実装：`.claude/skills/screen-read/SKILL.md` に撮影→前処理→OCR→疑義→結合→Obsidian 保存の全フロー（F-1〜F-16 網羅）と、`scripts/screen_read_helper.py` に JSON 出力 CLI 4 サブコマンド（preprocess / same-page / save-page / merge-save）を追加。ドライランで k=3 score 100.0 結合・EXIF 除去・frontmatter 生成を確認。`save-page` の `.rstrip()` で OCR 末尾改行による境界整列ズレを防止。

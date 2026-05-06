# Session Handover

**最終更新:** 2026-05-06 21:35

---

## 前提と目的 (Context & Intent)

前セッション（2026-05-06 15:31）で Plan エージェントが立てた「テキスト + 音声インタラクティブ会話マイルストーン」到達計画（Phase 1〜4）に従い、**Phase 1（コネクタ層）と Phase 2（データ層初期化）を一気に消化したセッション**。

このセッションでは:
- `tts-mcp` を `.mcp.json` に統合（VOICEVOX も含む両エンジン対応）
- `.env` 経由ではなく `.mcp.json` の env に集約（wifi-cam と同じスタイル、`.gitignore` 済み）
- daybook を 2 回 append（fallback `2026-01-01` の検証 + 今日付 `2026-05-06`）
- ついでに interaction skill 試運転 E-1 の主要項目（compose / ingest×2 / record_agent_experience）も実機で動作確認

**コードはほぼゼロ変更**（設定ファイル `.mcp.json` のみ編集）。残るは API キー入力 + Claude Code 再起動 → Phase 4 フル試運転。

---

## 成果と変更箇所 (Outcomes & Changed Files)

### 設定変更（コミット対象は CHRONICLE / archive のみ。`.mcp.json` は `.gitignore` 済み）

- `/.mcp.json`（**ローカル**、git 管理外）— `tts` エントリ新設。env に ElevenLabs / VOICEVOX 両方の環境変数を集約。`ELEVENLABS_API_KEY` のみプレースホルダ
- `docs/HANDOVER.md` — このファイル（更新）
- `docs/CHRONICLE.md` — このセッションの 1 行追記
- `docs/archive/handover-20260506-1531.md` — 前セッションの HANDOVER を退避
- `docs/archive/handover-20260506-2135.md` — もう 1 つ前の HANDOVER（実は同日 15:31 の handover skill が生成、archive ディレクトリに既に lossい移動）。命名衝突回避のため別タイムスタンプで保存

### データベース変更（social.db — `~/.claude/sociality/`）

- `narrative_daybooks` テーブル: 2 件追加（`2026-01-01` fallback / `2026-05-06` 今日付）
- `events` テーブル: 2 件追加（`evt_9a4ef0a52630a416` incoming / `evt_2e5c087f6ba0db1e` outgoing）
- `agent_experiences` テーブル: 1 件追加（`exp_187fee053546` kind=agent_response）

### コード未変更ファイル（CLAUDE.md, .claude/skills, .claude/rules はそのまま）

git status は CHRONICLE / archive 関連のみ。

---

## 検討と意思決定 (Decisions & Rationale)

### 1. `.env` ではなく `.mcp.json` の env に集約

- **判断:** `tts-mcp/.env` を作成 → 削除し、`.mcp.json` の `tts.env` に書く
- **理由:** ユーザー指摘。`.mcp.json` は `.gitignore` 済み（リポジトリのローカル運用）。既存の `wifi-cam` も同じスタイルで TAPO_PASSWORD を直書きしている。一貫性。`.env` を増やすと管理場所が分散する
- **代替案:** `.env` ファイルを採用 → 不採用（管理分散 + git 管理外なのに別の隠しファイルが増える）

### 2. VOICEVOX も両立で入れる（ElevenLabs 単独にしない）

- **判断:** `.mcp.json` の tts エントリに `VOICEVOX_URL` / `VOICEVOX_SPEAKER` も入れて両エンジン対応
- **理由:** ユーザー要望。ElevenLabs（感情豊か・有料）と VOICEVOX（無料・ローカル・低レイテンシ）を使い分けたい
- **エンジン選択優先順位:** `mcpBehavior.toml [tts] default_engine = ""`（auto）の場合、tts-mcp の auto-detect は `elevenlabs first for backward compat, then voicevox`（`config.py:156`）。VOICEVOX を既定にするなら `default_engine = "voicevox"` か say 呼び出し時に `engine="voicevox"` 明示

### 3. Phase 2 のトークン消費影響は軽微（推奨実行）

- **判断:** Phase 2 の `append_daybook` 初期化を実行。トークン削減策（max_chars 削減等）は採用せず
- **理由:** ユーザー懸念に対する根拠調査の結果、`build_day_summary`（`summarizer.py:8`）が生成する `latest_daybook` 文字列は約 60 文字 ≒ 20 トークン程度。compose 戻り値の `compact_prompt_block` は `max_chars=3000` でクリップされるため誤差レベル
- **重要:** **`append_daybook` を自動的に呼ぶ仕組みは現状どこにも存在しない**。`heartbeat-daemon.sh` も interaction/SKILL.md も daybook 更新を触っていない。CLAUDE.md 縮約時に旧 Heartbeat Protocol の「毎日1回 append_daybook」記述は意図的に削除済み。Phase 2 単発初期化で「Claude が指示なしに毎日日誌を更新し始める」運用にはならない

### 4. fallback 日付 daybook も残す

- **判断:** `append_daybook()` 引数なしで呼んだら fallback `2026-01-01` で生成された。これは消さず、続けて `append_daybook(day="2026-05-06")` で今日付も追加
- **理由:** fallback 日付の daybook は実用価値こそ低いが、システム検証としては「`latest_daybook` が non-null になる」を一度確認できた意味がある。daybook テーブルは `ON CONFLICT(day) DO UPDATE` なので将来同日付で再呼びすれば更新される

### 5. Phase 4 E-1 試運転は実は半分済み

- **判断:** Phase 2 を進める過程で `compose → ingest×2 → record_agent_experience` が実機で動いた。明示的に「E-1 試運転」とは呼ばずに済んだが、合格基準の主要項目は満たした
- **理由:** `interaction/SKILL.md` のフローを daybook 更新の文脈で踏んだ結果
- **未消化:** `plan_response_tool` 経由は今回スキップ。Phase 4 E-1 の正式試運転（plan も含む）は次セッションで

---

## ハマった点・失敗したアプローチ (Friction & Anti-patterns)

### F-1: `record_agent_experience` の payload フィールド名は `kind`

- **問題:** 1 回目の `record_agent_experience` 呼び出しで `experience_kind` フィールドを送って `Field required: kind` エラー
- **原因:** `plan_response_tool` の `followup_action` は `experience_kind` というキーで返すが、`record_agent_experience` の payload で実際に必要なのは **`kind`**。SKILL.md の 4-b 表で記法が混在している
- **対処:** `kind: "agent_response"` で再送 → 成功
- **次セッションで:** Phase 3 のスコープに「SKILL.md の `kind` / `experience_kind` 統一」を入れる

### F-2: `.mcp.json` 経由の env が `.env.example` の `VOICEVOX_URL` 指針に合うか

- **問題:** VOICEVOX エンジンが現在 localhost:50021 で起動していない（`curl -s http://localhost:50021/version` 失敗）
- **原因:** VOICEVOX は別途起動が必要。Windows GUI 版 or Docker 版どちらか
- **対処方針:** ユーザーが任意で起動。WSL2 mirrored networking で localhost が Windows 側 VOICEVOX に届く想定

### F-3: 「Phase 2 を実行すると勝手に日誌を更新するのでは」という懸念

- **問題:** ユーザーから「特に指示してない時でも Claude が日誌更新するってこと？」と質問
- **検証:** grep / 実装読みで「自動化はどこにもない」ことを確認
- **学び:** 設計書（HANDOVER）の文言だけで判断せず、実装と hook 設定を確認するのが正解。同様の懸念が出た時は実コードを示すのが説得的

---

## 次にやること (Next Steps)

### 即時（API キー入力 + Claude Code 再起動を伴う）

1. [ ] `/home/slmbrcat/projects/embodied-ai/.mcp.json` の `ELEVENLABS_API_KEY` プレースホルダを実キーに置換
2. [ ] VOICEVOX エンジンを起動（任意。Windows GUI 版 or Docker 版）
   - GUI: https://voicevox.hiroshiba.jp/ → アプリ起動
   - Docker: `docker run -d --name voicevox --restart unless-stopped -p 50021:50021 voicevox/voicevox_engine:cpu-ubuntu20.04-latest`
3. [ ] Claude Code 再起動（`/exit` → `claude`）
4. [ ] `mcp__tts__say` がツール一覧に出ることを確認
5. [ ] 接続確認: `curl http://localhost:50021/version`（VOICEVOX 起動済みなら version 文字列）

### Phase 3: interaction skill ガイド微調整（P1）

6. [ ] `.claude/skills/interaction/SKILL.md` 4-b 表で `kind` / `experience_kind` の記法を統一（実 API は `kind`）
7. [ ] SKILL.md 冒頭に「voice 入力時の `plan.voice.speak` 上書きチェックリスト」を**目立つ位置**に追記
8. [ ] SKILL.md の record 表に「stay_silent + voice 入力」ケースを追記
9. [ ] `socialPolicy.toml` の `[[person_rules]]` natsuko に `loud_voice_during_quiet_hours` を avoid_actions に追加
10. [ ] `.claude/rules/tts.md` に「voice 入力には text + voice を**並列に**返す」アンチパターンを明記
11. [ ] `.claude/rules/tts.md` にエンジン使い分けガイドを追記（ElevenLabs: 感情豊か / VOICEVOX: 無料・ローカル）

### Phase 4: 試運転（P0/P1）

12. [ ] **E-1 テキスト 1 ターン（フル）**: 今回スキップした `plan_response_tool` 経由を含めて再試運転
13. [ ] **E-2 `/voice` 1 ターン**: API キーと VOICEVOX 起動が整ってから
14. [ ] **E-3 quiet_hours 模擬**: 深夜帯または fixture
15. [ ] **E-4 wifi-cam `listen` 連携**（任意・P2）

**マイルストーン到達条件:** E-1〜E-3 が合格基準を満たす（前回 HANDOVER の合格基準セクション参照）。E-4 は任意。

### 継続改善: メタ層（Step 5、観測ベース着手）

16. [ ] `scripts/meta_layer_observation.py` を書く（social.db 週次集計、followup 取りこぼし率 / record なし outgoing 連発回数 / interpretation_shift 後の user_correction 検出）
17. [ ] 1 週間以上運用 → トリガーが立った時点で対応シグナル（S1/S2/S3）から着手

詳細は前回 HANDOVER（`docs/archive/handover-20260506-1531.md`）の「継続改善」セクション参照。

---

## 参考情報

### Critical Files for Implementation

- `/home/slmbrcat/projects/embodied-ai/.mcp.json` — tts エントリ既存、API キーのみ置換待ち
- `/home/slmbrcat/projects/embodied-ai/.claude/skills/interaction/SKILL.md` — Phase 3 で kind/voice/record 表を調整
- `/home/slmbrcat/projects/embodied-ai/.claude/rules/tts.md` — Phase 3 でアンチパターン + エンジン使い分けを追記
- `/home/slmbrcat/projects/embodied-ai/socialPolicy.toml` — Phase 3 で natsuko の avoid_actions 追記
- `/home/slmbrcat/projects/embodied-ai/mcpBehavior.toml` — `[tts] default_engine = ""` の変更検討（VOICEVOX 既定にしたい場合のみ）

### 検証スニペット

```bash
# VOICEVOX 接続確認
curl -s http://localhost:50021/version

# tts-mcp 直起動（stdio MCP server）
uv run --directory tts-mcp tts-mcp

# social.db の最新 daybook 確認
sqlite3 ~/.claude/sociality/social.db "SELECT day, summary FROM narrative_daybooks ORDER BY day DESC LIMIT 5;"

# このセッションの events と experiences
sqlite3 ~/.claude/sociality/social.db "SELECT event_id, kind, ts FROM events ORDER BY ts DESC LIMIT 5;"
sqlite3 ~/.claude/sociality/social.db "SELECT experience_id, kind, ts FROM agent_experiences ORDER BY ts DESC LIMIT 5;"
```

### plan_response_tool の voice ロジック（実装位置）

`sociality-mcp/packages/interaction-orchestrator-mcp/src/interaction_orchestrator_mcp/plan.py:275-285`

入力 channel は見ていない。voice 入力時は SKILL.md の voice 例外で Claude 側が `speak=true` に上書きする契約。

### `record_agent_experience` のフィールド対応表（**重要**）

| 場面 | フィールド名 |
|---|---|
| `plan_response_tool` の `followup_action` 戻り値 | `experience_kind` |
| `record_agent_experience` の payload 引数 | **`kind`** |

両方読む時は混乱しないよう注意。

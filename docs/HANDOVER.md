# Session Handover

**最終更新:** 2026-05-21 16:15

---

## 前提と目的 (Context & Intent)

embodied-ai の **Phase 1（VOICEVOX 接続）を完全完遂**することが目的。同日 11:11 の HANDOVER で「WSL 内 Docker で VOICEVOX を起動して `/version` `/speakers` まで疎通」までは取れていたが、**`/mcp` に tts が出ない・Claude Code から `say` ツールが叩けない**という壁が残っていた。本セッションでその壁を解体し、実機で VOICEVOX 発話に成功するところまで持っていった。

ユーザー側で `claude mcp reset-project-choices` を実行 → 全 claude プロセス pkill → クリーン再起動という重い手順も挟んだが、それでも tts が見えなかった。最終的に `.claude/settings.local.json` の `disabledMcpjsonServers: ["tts"]` が原因と特定して修正、発話成功で Phase 1 を閉じた。

## 成果と変更箇所 (Outcomes & Changed Files)

git status（今セッション開始時点）:
```
 M .claude/skills/screen-read/SKILL.md        # 別セッション分（未コミット）
 M docs/CHRONICLE.md                          # 11:11 セッション + 本セッション分の追記予定
 M docs/HANDOVER.md                           # この書換え対象（archive 済）
?? docs/archive/handover-20260521-1057.md     # 14:35 セッション archive
?? docs/archive/handover-20260521-1111.md     # 11:11 archive
?? docs/archive/handover-20260521-1615.md     # 本書換え時の archive（新規）
```

本セッションで触れたファイル:

- **`.claude/settings.local.json`** — `disabledMcpjsonServers: ["tts"]` → 空配列、`enabledMcpjsonServers` 末尾に `"tts"` 追加。これが Phase 1 完遂の決定打。permission allow に `mcp__tts__say` も自動追加（ツール初回呼び出し時の prompt で許可）。**gitignore 対象なのでコミット差分には出ない**
- **active session ID = `024ca0ed-1474-4f04-b00c-afc86d298731`** — 再開コマンドは `cd ~/projects/embodied-ai && claude --resume 024ca0ed-1474-4f04-b00c-afc86d298731`。途中で snapshot を `docs/sessions-snapshot-20260521-1556.txt` に書き出したが `/background` 化のタイミングでファイル消失したため、ここに ID だけ転記
- **`~/.claude.json`** — `projects/.../enableAllProjectMcpServers: True` にセット（コミット対象外、Claude Code 内部設定）
- **Auto Memory `feedback_claude_mcp_new_entry_approval.md`** — 「`settings.local.json` の `disabledMcpjsonServers` が `~/.claude.json` より優先される」という最重要落とし穴を追記

実機側で完了した運用:

- VOICEVOX Docker container は CPU 版で安定稼働中（11:11 セッション分）。`docker ps` で `Up`、`/version=latest`、`speaker_id=3 = ずんだもん/ノーマル`
- `mcp__tts__say(engine="voicevox", speaker="local")` で実発話 2 回成功。`paplay` 経由 PulseServer `unix:/mnt/wslg/PulseServer` でユーザー耳に届いた

## 検討と意思決定 (Decisions & Rationale)

- **判断:** `.claude/settings.local.json` の `disabledMcpjsonServers` から tts を削除して `enabledMcpjsonServers` へ移す方式で対処
  - **理由:** `claude mcp reset-project-choices` + `enableAllProjectMcpServers: True` でも tts が `claude mcp list` に出なかった。`grep -rn '"tts"' .claude/settings.local.json` で direct disable を発見。`~/.claude.json`（global per-project state）より `.claude/settings.local.json` の方が project-local で優先される設計と判明
  - **代替案:** Claude Code の正規 UI で個別 approve を試みる → そもそも approve プロンプトが再起動時に出てこないため不可能。settings.local.json を直接編集するのが現実的に唯一の経路

- **判断:** 完全クリーンアップ手順（pkill claude 系 → 新ターミナルで起動）を経由
  - **理由:** `pgrep -af 'mcp'` で各 MCP（pal/wifi-cam/sociality/system-temperature）が **4–5 個ずつ重複起動**していることが判明。並走セッション + agent view の spare worker が終了時に MCP 子プロセスを始末していなかった。port 18900（memory MCP の HTTP server）の占有で `Failed to connect` も誘発
  - **代替案:** ターミナルを閉じるだけ → 不十分。`claude --bg` 起動セッションや `/bg` 取り込みされたセッション、agent view 配下の spare PTY host は detach されており SIGHUP が届かない

- **判断:** session snapshot を `docs/sessions-snapshot-*.txt` に保存してから pkill
  - **理由:** Claude Code を全部殺すと現セッション（私）も死ぬので、ユーザーが再開時にどの session-id に戻ればいいか分からなくなる懸念。実際に動いている "本物のセッション" は 1 つ（`024ca0ed-1474-4f04-b00c-afc86d298731`）だけだったが、それを明示する文書が必要

## ハマった点・失敗したアプローチ (Friction & Anti-patterns)

- **問題:** `claude mcp reset-project-choices` + Claude Code 再起動でも tts が `/mcp` に出ない
  - **試したこと:** `~/.claude.json` の `enableAllProjectMcpServers: True` も書き込み済、`hasTrustDialogAccepted: True`、再起動時の trust dialog は表示されない
  - **結果:** `.claude/settings.local.json:89` に `"disabledMcpjsonServers": ["tts"]` が残存していた。**`reset-project-choices` は `~/.claude.json` 側しかリセットしない**。`settings.local.json` の方が project-local で優先順位高いため、`~/.claude.json` をいくらいじっても上書きできない
  - **教訓:** Claude Code の MCP 承認は二層管理。`~/.claude.json` が global per-project、`.claude/settings.local.json` が project-local override。後者が優先。新規 .mcp.json エントリ追加時に「No」を押した記録は **settings.local.json** に書き込まれて永続化する

- **問題:** Claude Code 子プロセス（MCP 各種）が終了時に始末されず累積
  - **試したこと:** ターミナル close → daemon と spare worker が残存。`pgrep -af 'mcp'` で wifi-cam が 4 個、pal-mcp が 4 個、etc. memory-mcp は port 18900 衝突で Failed
  - **結果:** `pkill -TERM -f 'claude'` で daemon ごと殺す必要があった。`/bg` や agent view 経由の background session は通常終了で死なない設計

- **問題:** memory MCP の `Failed to connect` 表示が紛らわしい
  - **試したこと:** `claude mcp list` で常に Failed と出るので壊れていると勘違いしかけた
  - **結果:** 実は現セッション内では `/mcp` Reconnect で復活しており、deferred tools `mcp__memory__*` 27 個もロード可能だった。`claude mcp list` は **list 実行のたびに新しいプロセスを spawn して health check** するため、既存セッションの memory MCP が port 18900 を取っていると衝突して Failed と表示される。表示と実動作が乖離

- **問題:** `ELEVENLABS_API_KEY="your-api-key-here"` プレースホルダ
  - **試したこと:** tts MCP 起動失敗の犯人かと疑った
  - **結果:** 関係なし。tts-mcp は `_get_client()` で遅延初期化なので fake key でも起動は通る。ただし `say` 呼出し時に **`engine="voicevox"` を明示しないと auto-detect が ElevenLabs を選び 401 で失敗**するので、VOICEVOX-first 運用なら `mcpBehavior.toml` に `[tts] default_engine = "voicevox"` を入れる方が安全（未対応、次の改善余地）

## 次にやること (Next Steps)

1. [ ] **`mcpBehavior.toml` の `[tts] default_engine = "voicevox"` を設定** — `say` 呼出し時の engine 引数省略を許す（現状は `engine="voicevox"` 明示必須）
2. [ ] **`.mcp.json` から `ELEVENLABS_*` プレースホルダ env を削除 or 空文字列化** — VOICEVOX-first にするなら `ELEVENLABS_API_KEY=""` で `ElevenLabsConfig.from_env()` が None を返す動作にする方が事故防止になる
3. [ ] **Phase 4 試運転 E-1**（text 1 turn full）— `compose_interaction_context_tool` → `plan_response_tool` → text 応答 → `ingest_interaction` → `record_agent_experience`
4. [ ] **Phase 4 試運転 E-2**（/voice 1 turn）— 音声入力 → 認識 → text + `say(engine="voicevox")` 並列応答 → boundary 判定
5. [ ] **Phase 4 試運転 E-3**（quiet_hours 模擬）— 深夜想定でカメラスピーカー抑制テスト
6. [ ] **未コミット差分の整理** — 以下 3 系統が累積中:
   - 別セッションの `.claude/skills/screen-read/SKILL.md` 修正
   - 本セッションの `docs/CHRONICLE.md` + `docs/HANDOVER.md` 更新
   - 新規 `docs/archive/handover-20260521-{1057,1111,1615}.md`
   - 次セッション開始時にコミット可否を判断
7. [ ] **`claude --bg` / agent view 配下のセッション運用ルール化** — 終了時の MCP プロセス始末は手動 pkill が必要、というのを CLAUDE.md か skill に書く（並走運用が増えるなら必須）
8. [ ] **memory MCP の port 18900 多重起動の根治** — sociality-mcp と同様に環境変数で port をずらせるようにする / または `claude mcp list` の health check spawn を回避する設計検討（影響は表示だけだが運用感が悪い）
9. [ ] **OpenRouter monthly limit を $10–20 に引き上げ** — pal consensus の高単価モデル使用時に必要、前セッション継続課題

### 発話成功確認コマンド

```bash
# VOICEVOX コンテナ生存確認
sg docker -c "docker ps --filter name=voicevox --format 'table {{.Names}}\t{{.Status}}'"
# 接続確認
curl -s http://localhost:50021/version
# /speakers の数（33 が正常）
curl -s http://localhost:50021/speakers | jq 'length'
```

### Claude Code の MCP 状態確認

```bash
# tts が見えるか
claude mcp list | grep tts
# settings.local.json の状態（重要）
grep -A3 'disabledMcpjsonServers\|enabledMcpjsonServers' .claude/settings.local.json
```

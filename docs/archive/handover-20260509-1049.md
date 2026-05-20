# Session Handover

**最終更新:** 2026-05-07 19:23

---

## 前提と目的 (Context & Intent)

前セッション（2026-05-06 21:35）で完了した Phase 1（コネクタ層）+ Phase 2（daybook 初期化）に続き、**Phase 3（interaction skill ガイド微調整）を完遂したセッション**。

このセッションの主目的:
1. SKILL.md の `kind` / `experience_kind` 表記を実 API に揃える（前セッションで発見した validation error の根本対処）
2. SKILL.md 冒頭に voice 入力時の `voice.speak` 上書きチェックリストを目立つ位置で追加（CLAUDE.md 縮約と同じ位置バイアス対策）
3. socialPolicy.toml の natsuko ルールを quiet_hours での音声抑制と整合
4. tts.md にエンジン使い分けガイド + アンチパターン明記

副次的に `/statusline` を 2 段階で構成（PS1 起点 → モデル名/コンテキスト/セッションリミット追加）。これは embodied-ai プロジェクト外（`~/.claude/` 配下）の global config 変更。

**重要**: Phase 3 の編集は完了しているが、**コミットはユーザー判断で拒否された**ため未コミット状態（git status: modified 3 files）。次セッション開始時に working tree が dirty な状態で再開する。

---

## 成果と変更箇所 (Outcomes & Changed Files)

### Phase 3 編集（git status: modified、未コミット）

- `.claude/skills/interaction/SKILL.md` (216 → 237 行、+21)
  - 冒頭付近に「⚡ voice 入力時の上書きチェックリスト（最重要）」セクション新設（4 項目チェックリスト + plan.voice.speak 上書きの根拠説明）
  - 4-b の `record_agent_experience` 表を `payload.kind` 起点に再構成。冒頭に **重要なフィールド名規約** ブロック追加（`followup_action.experience_kind` → `payload.kind` 変換ルールを明示）
  - 4-b 状況表に「voice 入力だったが stay_silent / quiet_hours で発話を抑えた」行を追加（`boundary_respected` で記録、summary に経路明記）

- `.claude/rules/tts.md` (31 → 51 行、+20)
  - 「エンジン使い分け」表を新設（ElevenLabs / VOICEVOX の強み・弱み・使う場面）
  - VOICEVOX 起動前提（`localhost:50021`）と未起動時の ElevenLabs fallback を明記
  - 「アンチパターン」節を新設（音声/テキスト並列必須・speak 上書き禁止・max_sentences 厳守・感情タグ誤用 NG）

- `socialPolicy.toml`
  - `[[person_rules]] natsuko` の `avoid_actions` に `loud_voice_during_quiet_hours` を追加（既存の `camera_speaker_after_midnight` と並列）

### Global 設定（`~/.claude/`、embodied-ai 外。コミット対象外）

- `~/.claude/statusline-command.sh`（**新規**） — シェル PS1 起点の statusLine 変換スクリプト + モデル名 / コンテキスト残量 / セッションリミット表示
- `~/.claude/settings.json`（**更新**） — `statusLine` フィールド追加

---

## 検討と意思決定 (Decisions & Rationale)

### 1. voice チェックリストを SKILL.md 冒頭に置く（位置バイアス対策）

- **判断:** voice 入力特例セクションは元々 4 節「3. act」内の `#### voice 入力の特例` にあったが、それを残しつつ **冒頭付近にチェックリストを duplicate 配置**
- **理由:** CLAUDE.md 424 行が位置バイアスで Heartbeat Protocol を機能不全にしていた構造的問題と同じ。voice 入力の判断フローはセッション後半でも必ず参照される必要があるため、起動条件のすぐ後に置く。重複は「読み返す手間」を削るほうを優先
- **代替案:** 1 箇所に集約して相互参照リンク → 不採用（リンクをたどらない場合があるため、目に入る位置に重複させる方が安全）

### 2. `payload.kind` 表記に統一（experience_kind は注釈付きで残す）

- **判断:** 4-b 表のデータ列見出しを `experience_kind` → `payload.kind` に変更しつつ、`followup_action.experience_kind` から変換するルールも明示
- **理由:** 前セッションで実機呼び出し時に `Field required: kind` エラーが出た。SKILL.md 内で書き換えなしの場合、再び同じエラーを踏む。`experience_kind` は plan の戻り値構造としては存在するため、変換が必要なことを明示するのが正解
- **代替案:** `experience_kind` を完全に削除 → 不採用（plan の戻り値を読むときに `experience_kind` キーが出てくるので、そこに気づく必要がある）

### 3. `loud_voice_during_quiet_hours` を新設（既存の camera_speaker_after_midnight と並列）

- **判断:** `camera_speaker_after_midnight` を変更せず、新たな avoid_action として `loud_voice_during_quiet_hours` を追加
- **理由:** 既存の "after_midnight" は時刻ベース（00:00-）に対応するが、SKILL.md の voice チェックリストで参照したいのは quiet_hours（policy 設定値、現在 `00:00-07:00`）に基づく抑制。policy 名と avoid_action 名を整合させた
- **副作用:** plan の `forbidden_actions` にこの 2 つが乗る場面で、Claude の voice 出力が抑止される（_pick_must_lists の挙動で。ただし plan 側の参照実装は確認していない）

### 4. tts.md にアンチパターン節（rules/ ファイル粒度の例外）

- **判断:** 通常 rules/ は「事実とフォーマットの定義」に絞るが、tts.md だけは「アンチパターン」節を含める
- **理由:** 音声出力は失敗しやすい（喋るな決定を破る、片方だけ出す、感情タグ誤用）。これらは SKILL.md の中で interaction フローの一部として書いているが、tts.md を編集中の Claude（say の引数を組み立てている瞬間）にも目に入る位置に置きたい
- **代替案:** SKILL.md 一極集中 → 不採用（rules はパス条件で注入されるので、tts-mcp/**/*.py 編集時に tts.md だけが load される。SKILL.md は別タイミング）

### 5. statusLine 設定は user global（プロジェクトに含めない）

- **判断:** `/statusline` 由来の変更は `~/.claude/` 配下で完結。プロジェクトの `.claude/` には書き込まない
- **理由:** ステータスラインは作業環境の設定で、embodied-ai プロジェクトの動作には影響しない。プロジェクト .claude/ に書くと他プロジェクトでも同じ statusline が強制される可能性
- **副作用:** このプロジェクトを別マシンで開いた時にステータスラインの設定は引き継がれない（必要なら別途再設定）

---

## ハマった点・失敗したアプローチ (Friction & Anti-patterns)

### F-1: コミットが拒否された（次セッション開始時の状態に注意）

- **問題:** Phase 3 の 6 タスク編集後、コミットコマンドが Denied by user で拒否された
- **試したこと:** `docs(interaction): clarify voice override checklist and kind/experience_kind mapping` のメッセージで `git commit` 実行
- **結果:** ユーザー判断で拒否。理由は確認していない（メッセージ調整希望か、まだ commit したくないか、編集内容の見直し希望かは不明）
- **次セッションで:** dirty working tree のまま再開。`git status` で modified を確認 → ユーザーに「Phase 3 の編集をコミットするか / 見直すか」を聞く

### F-2: 既存セッション継続 vs 新規 Agent 生成（statusline 2 回目）

- **問題:** `/statusline` を 2 回目呼んだ時、前回の statusline-setup エージェントを SendMessage で継続するか、新規 Agent を生成するか迷った
- **判断:** コマンド定義 `Create an Agent with subagent_type "statusline-setup"` に従って新規 Agent を生成
- **結果:** うまくいった（既存の `~/.claude/statusline-command.sh` を読み取って差分追加）
- **学び:** スラッシュコマンドの instruction が "Create an Agent" と明示している場合は、既存セッションがあっても新規生成する。SendMessage は Claude が自発的に判断して使うとき向け

### F-3 (構造的): SKILL.md の重複情報の管理コスト

- **問題:** voice チェックリストを冒頭に追加したことで、`#### voice 入力の特例`（4 節内）と内容が重複
- **影響:** 今後どちらかを更新したらもう片方も更新する必要がある
- **対処方針:** 次の Phase 3 微調整があれば「voice チェックリストは冒頭が source of truth、4 節は要約」とどちらかに役割を寄せる。今は両方を完全版にしておく（位置バイアス対策優先）

---

## 次にやること (Next Steps)

### 即時（最初のターンで判断する）

1. [ ] `git status` で modified ファイル 3 件を確認 → ユーザーに以下を聞く:
   - Phase 3 の編集内容を読み直してコミットするか
   - メッセージを変えてコミットするか
   - 編集をロールバックするか
2. [ ] コミット決まったら `.claude/skills/interaction/SKILL.md` `.claude/rules/tts.md` `socialPolicy.toml` の 3 つを 1 コミットで（前回の HANDOVER で提案したメッセージ案: `docs(interaction): clarify voice override checklist and kind/experience_kind mapping`）

### Phase 1 完了待ち（ユーザー作業）

3. [ ] `.mcp.json` の `ELEVENLABS_API_KEY` プレースホルダを実キーに置換
4. [ ] （任意）VOICEVOX エンジン起動: GUI 版（https://voicevox.hiroshiba.jp/）or Docker 版（`docker run -d --name voicevox --restart unless-stopped -p 50021:50021 voicevox/voicevox_engine:cpu-ubuntu20.04-latest`）
5. [ ] Claude Code 再起動（`/exit` → `claude`）
6. [ ] `mcp__tts__say` がツール一覧に出ることを確認
7. [ ] 接続確認: `curl http://localhost:50021/version`（VOICEVOX 起動済みなら version 文字列）

### Phase 4: 試運転（P0/P1）

8. [ ] **E-1 テキスト 1 ターン（フル）**: `plan_response_tool` 経由を含めて改めて試運転（前セッションでスキップした項目）
9. [ ] **E-2 `/voice` 1 ターン**: API キーと VOICEVOX 起動が整ってから
10. [ ] **E-3 quiet_hours 模擬**: 深夜帯（22:00-07:00）または fixture
11. [ ] **E-4 wifi-cam `listen` 連携**（任意・P2）

**マイルストーン到達条件:** E-1〜E-3 が合格基準を満たす（合格基準は `docs/archive/handover-20260506-1531.md` 末尾参照）。

### 継続改善: メタ層（Step 5、観測ベース着手）

12. [ ] `scripts/meta_layer_observation.py` 作成（social.db 週次集計: followup 取りこぼし率 / record なし outgoing 連発 / interpretation_shift 後の user_correction 検出）
13. [ ] 1 週間以上運用 → トリガーが立った時点で対応シグナル（S1/S2/S3）から着手

---

## 参考情報

### Critical Files for Implementation

- `/home/slmbrcat/projects/embodied-ai/.mcp.json` — tts エントリ完成、API キーのみ置換待ち
- `/home/slmbrcat/projects/embodied-ai/.claude/skills/interaction/SKILL.md` — Phase 3 完了（未コミット）。voice チェックリスト + kind 表記統一済み
- `/home/slmbrcat/projects/embodied-ai/.claude/rules/tts.md` — Phase 3 完了（未コミット）。エンジン使い分け + アンチパターン追加済み
- `/home/slmbrcat/projects/embodied-ai/socialPolicy.toml` — Phase 3 完了（未コミット）。natsuko avoid_actions 拡張済み

### `record_agent_experience` のフィールド対応表（**変わらず重要**）

| 場面 | フィールド名 |
|---|---|
| `plan_response_tool` の `followup_action` 戻り値 | `experience_kind` |
| `record_agent_experience` の payload 引数 | **`kind`** |

Auto Memory にも `feedback_record_agent_experience_kind.md` として保存済み。

### コミット拒否されたコミットメッセージ案

```
docs(interaction): clarify voice override checklist and kind/experience_kind mapping

- SKILL.md: prepend voice-input override checklist near the top so it survives late-session position bias
- SKILL.md: rewrite the 4-b record_agent_experience tables to mark payload.kind as the actual API field and explain the followup_action.experience_kind → payload.kind conversion
- SKILL.md: add a row covering "voice input but suppressed" so the boundary_respected summary records why
- rules/tts.md: add ElevenLabs / VOICEVOX engine selection guide and an antipattern block (parallel text+voice required, no rogue speak overrides)
- socialPolicy.toml: extend natsuko avoid_actions with loud_voice_during_quiet_hours so plan's forbidden_actions stays aligned with the new SKILL contract
```

メッセージ調整したい場合の起点として残しておく。

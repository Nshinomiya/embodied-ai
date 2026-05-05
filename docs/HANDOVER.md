# Session Handover

**最終更新:** 2026-05-05 13:32

---

## 前提と目的 (Context & Intent)

前セッションで sociality インフラの初期化（person_id 統一・social.db 生成・heartbeat daemon 起動・compose→plan 動作確認）が完了した状態でスタート。

このセッションは **コード変更ゼロの設計フェーズ**。残課題だった「`ingest_interaction` / `record_agent_experience` の運用設計」を起点に、プロジェクト全体の設計思想と Claude Code 機構（CLAUDE.md / rules / skills / hooks）の住み分けを再整理した。

主な議題：
1. `record_agent_experience` の運用は自動化（フック）か、Claude の自律判断か
2. auto-social.sh の存在意義（直 INSERT で解釈レイヤーをスキップしている問題）
3. CLAUDE.md が 424 行に肥大化しており、参照効率が落ちている
4. プロジェクトの設計原則を「身体メタファー三層」で再整理する

---

## 成果と変更箇所 (Outcomes & Changed Files)

**コード変更なし**（設計議論のみ）。git status は clean。

このセッションの成果はすべて「次セッションで実装するための設計合意」として本 HANDOVER に記録される。

---

## 検討と意思決定 (Decisions & Rationale)

### 1. 設計の基礎は「身体メタファー三層モデル」

| 層 | 性質 | 該当処理 |
|---|---|---|
| **下位層（不随意・知覚）** | 自動化 OK | interoception / auto-recall / heartbeat-daemon |
| **上位層（随意・行動）** | Claude が判断して呼ぶ | ingest_interaction / record_agent_experience / append_daybook |
| **メタ層（自己認識補助）** | 自動化 OK（行動は強制しない） | 「最後の experience 記録から N ターン経過」を compose 戻り値に注入する等 |

- **判断:** 上位層の自動化は embodied AI の設計思想に反するため避ける
  - **理由:** Claude Code に自律性を持たせることがプロジェクト目的。スクリプト自動化で行動を肩代わりすると主体性が消える
  - **代替案:** Stop フックで record_agent_experience を自動呼び出し → 不採用（応答テキストをフックから取得しづらく、summary が空 or 固定文になる）

### 2. auto-social.sh は廃止する

- **判断:** 廃止し、Claude 自身が `ingest_interaction` を呼ぶ運用に切り替える
  - **理由:** auto-social.sh は SQLite に直 INSERT しており、`_update_open_loops` と `refresh_snapshot` という解釈処理をスキップしている。知覚にも行動にもなれていない中途半端な層
  - **重要な確認:** 「セッションログがあるから記録不要」は **誤り**。session log は生テキストの完全記録だが、social.db は構造化された解釈・自己モデルで別物。social.db が空になると compose の `recent_events` / `recent_experiences` が機能不全になり、`get_person_model` の snapshot が古くなる

### 3. CLAUDE.md / rules / skills の住み分け

参考記事: https://qiita.com/nogataka/items/d6c83ea50b82e1c2602c

| 機構 | 役割 | サイズ目安 |
|---|---|---|
| CLAUDE.md | プロジェクト全体の最小限 | 30-35 行 |
| `.claude/rules/` | パス条件付き規約 | 1 ファイル 10-20 行 |
| `.claude/skills/` | タスク単位のフロー | タスクの粒度に応じて |
| `.claude/hooks/` | 知覚層・メタ層 | （記事範囲外） |

- **判断:** 現在の CLAUDE.md（424 行）から MCP ツール一覧と Heartbeat Protocol を切り出す
  - **理由:** CLAUDE.md は user message として注入されるため位置バイアスで減衰する。セッション後半で Heartbeat Protocol が無視されているのは構造的問題
  - **配置先:** MCP ツール表 → rules（パス別）、Heartbeat Protocol → skills（フェーズ別ではなくタスク別）

### 4. skill 分割は「フェーズ単位」ではなく「タスク単位」

- **判断:** `compose/SKILL.md` `plan/SKILL.md` のようなフェーズ分割は**しない**
  - **理由:** compose と plan は常にセットで呼ばれるので、毎回 2 つ起動するのは煩雑。記事の skills は「タスク層」でフェーズより粗い粒度
  - **採用案:** `interaction/SKILL.md`（対話応答ループ全体）/ `autonomous-tick/SKILL.md`（自律 tick）/ `daily-routine/SKILL.md`（daybook ルーチン）/ `boundary-review/SKILL.md`（投稿前レビュー）

### 5. drift 対策はメタ層で

- **判断:** SKILL.md に「呼べ」と書くだけでは Claude は忘れる（CLAUDE.md の Heartbeat Protocol が今日まで一度も呼ばれていないのが証拠）
  - **対策:**
    - `plan_response_tool` の `followup_action` を**契約**として SKILL.md で明文化（無視できないルール化）
    - メタ層フックで「最後の experience 記録から N ターン経過」を compose 戻り値に注入
    - Stop フックで「followup pending」警告（行動は強制せず Claude に気づかせる）

---

## ハマった点・失敗したアプローチ (Friction & Anti-patterns)

このセッションは設計議論のみのため、コード起因の friction はなし。

ただし議論中に判明した既存の構造的問題：

- **問題:** auto-social.sh は MCP を経由せず SQLite に直 INSERT しているため、open_loop 検出と person snapshot 更新が走らない
  - **影響:** 現状すでに person_model が古いまま。社会的記憶の解釈レイヤーが機能不全
  - **対処方針:** 廃止して Claude 自身の `ingest_interaction` 呼び出しに置き換える

- **問題:** CLAUDE.md の Heartbeat Protocol が記述されているのに一度も実行されていない
  - **原因:** CLAUDE.md は user message として注入されるが、セッション後半で位置バイアスにより参照されない
  - **対処方針:** skills に切り出して、必要なタイミングで明示的に load されるようにする

---

## 次にやること (Next Steps)

優先順位順。**機能停止期間ゼロで段階移行する**ことが目的。

### Step 1: `interaction/SKILL.md` を新設（最優先）

auto-social.sh を廃止する前に、運用ループの受け皿を先に作る。

1. [ ] `.claude/skills/interaction/SKILL.md` を作成
2. [ ] 内容: compose → plan → act → ingest_interaction + record_agent_experience の明示的フロー
3. [ ] `plan_response_tool` の `followup_action` を「無視できない契約」として明文化
4. [ ] `record_agent_experience` の `kind` 体系（reply / boundary_respected / open_loop_progress / agent_private_reflection など）を整理して記載

### Step 2: auto-social.sh を廃止

5. [ ] `.claude/hooks/auto-social.sh` を削除
6. [ ] `.claude/settings.json` から該当エントリを除去
7. [ ] commit message: `chore(hooks): remove auto-social.sh in favor of skill-based ingest_interaction`

### Step 3: CLAUDE.md を縮約

8. [ ] CLAUDE.md から MCP ツール一覧表を削除（rules へ移管）
9. [ ] CLAUDE.md から Heartbeat Protocol を削除（`interaction/SKILL.md` へ移管）
10. [ ] CLAUDE.md から WSL2 注意事項・カメラ設定詳細を削除（rules へ移管）
11. [ ] 残すのは: プロジェクト概要 / 三層モデル宣言 / ディレクトリ構造（簡略） / rules・skills への誘導

### Step 4: `.claude/rules/` の段階的構築

一気に作らず、サブプロジェクト編集時に必要に応じて切り出す。

12. [ ] `python-mcp-dev.md` → `paths: */src/*_mcp/**/*.py`（uv / pytest / ruff）
13. [ ] `wifi-cam.md` → `paths: wifi-cam-mcp/**/*.py`（Tapo / Imou の差異）
14. [ ] `tts.md` → `paths: tts-mcp/**/*.py`（感情タグ / voice / speaker 切替）
15. [ ] `social-policy.md` → `paths: socialPolicy.toml`（書き方）
16. [ ] `mcp-server-design.md` → `paths: **/server.py`（MCP tool 設計規約）
17. [ ] **重要:** `paths` フィールドは YAML 配列ではなく**カンマ区切り**で書く（記事のバグ指摘）

### Step 5: メタ層フックの追加（運用が回り始めてから）

18. [ ] post-response フックで「followup pending」警告
19. [ ] compose 戻り値に「最後の experience 記録から N ターン」を注入する仕組み

### Step 6: 残課題（前セッションから持ち越し）

20. [ ] daybook の初期化（`append_daybook` 一度呼んで `latest_daybook: null` を解消）
21. [ ] quiet_hours 中の自律 tick で `write_private_reflection` が選ばれることを実機確認

---

## 参考情報

### 三層モデル × Claude Code 機構の対応表

| 身体メタファー \ Claude Code | CLAUDE.md | rules | skills | hooks |
|---|---|---|---|---|
| **下位層（知覚）** | - | - | - | ✅ interoception / auto-recall / heartbeat |
| **上位層（行動）** | 行動原則のみ | パス別規約 | タスク別フロー | - |
| **メタ層（自己認識）** | - | - | - | ✅ post-response 警告（追加予定） |

### 参考記事

- https://qiita.com/nogataka/items/d6c83ea50b82e1c2602c
  - CLAUDE.md は 30-35 行に絞る
  - rules はパス条件付きで注入され、セッション後半でも効果維持
  - skills はタスク層
  - frontmatter `paths` は YAML 配列だとパースバグ → カンマ区切り必須

### 既存の skills

- `screen-read/SKILL.md` — 既存（変更不要）

### auto-social.sh の現状（廃止対象）

ファイル: `.claude/hooks/auto-social.sh`
動作: UserPromptSubmit で stdin から prompt を受け取り、`social.db` の events テーブルに `human_utterance` として直 INSERT。

問題点:
- MCP を経由しないため `_update_open_loops` / `refresh_snapshot` が走らない
- 解釈処理を飛ばしているので「知覚層」にも「行動層」にもなれていない

### `record_agent_experience` の followup_action ヒント実装

`sociality-mcp/packages/interaction-orchestrator-mcp/src/interaction_orchestrator_mcp/plan.py:312` の `_pick_followup` 関数で、primary_move に応じた experience_kind を返す仕組みは既に実装済み。

```python
if primary_move in {"write_private_reflection", "compose_letter"}:
    return {"kind": "record_agent_experience",
            "experience_kind": "agent_private_reflection" or "agent_file_created"}
if primary_move == "answer_directly" and ctx.open_loops:
    return {"kind": "record_agent_experience",
            "experience_kind": "open_loop_progress"}
```

`interaction/SKILL.md` ではこの followup を「契約」として参照すること。

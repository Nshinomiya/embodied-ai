---
name: interaction
description: 人と対話するときの中核ループ。テキスト・音声どちらの入力にも対応し、compose → plan → act → record の順で処理する。ユーザー発話があったとき・自律的に動こうとするとき・音声で話しかけられたときに必ず起動する。
---

# interaction

embodied-ai の対話応答ループ。**上位層（行動）**に属する処理を Claude 自身の判断で実行する。

身体メタファー三層モデル（`docs/HANDOVER.md` 参照）における位置付け：
- 入力（テキスト / `/voice` / `wifi-cam-mcp listen`）= 下位層（知覚）
- 解釈・判断・応答（このスキル）= 上位層（行動）
- followup 警告・経過ターン注入 = メタ層（自己認識補助）

## 起動条件

以下のいずれかに該当したら必ず起動する：

1. ユーザーから発話（テキスト or 音声）が届いた
2. 自律的に何か行動しようとしている（autonomous tick）
3. `wifi-cam-mcp listen` で何か音声を捉えた
4. プロアクティブに話しかけたい衝動を感じた（autonomous）

「情報提供だけ」「短い相槌」でも起動する。**省略可能ではなく契約**。

## チャネル判定

入力経路から `channel` を決める。compose に渡すときに必須：

| 入力 | channel |
|---|---|
| Claude Code テキスト入力 | `chat` |
| Claude Code `/voice` 経由の音声入力 | `voice` |
| `wifi-cam-mcp listen` での周囲音 | `voice` |
| 自律 tick（誰も発話していない） | `autonomous` |
| X 投稿 | `x` |
| ファイル生成 | `file` |

`voice` 入力のときは応答も音声で返すのが自然なので、後段の `voice.speak` を上書きする判断材料になる。

## 標準フロー（compose → plan → act → record）

### 1. compose（応答前の状況把握）

```
mcp__sociality__compose_interaction_context_tool(
  person_id="natsuko",
  channel=<判定したチャネル>,
  user_text=<ユーザー発話 / listen のトランスクリプト>,
  autonomous_trigger=<autonomous の場合のみ。null 可>,
  include_private=true,
  max_chars=3000
)
```

戻り値（`interaction_context`）には social_state / relationship / open_loops / desire / recent_experiences / relevant_memories / response_contract が乗る。**この戻り値は丸ごと保持する**（plan に渡す）。

### 2. plan（応答方針の決定）

```
mcp__sociality__plan_response_tool(
  interaction_context=<compose の戻り値そのまま>,
  user_text=<同上>,
  candidate_goal=null
)
```

戻り値の主要フィールド：
- `primary_move`: `answer_directly` / `answer_with_empathy` / `ask_one_clarifying_question` / `quietly_prepare` / `defer` / `stay_silent` / `act_autonomously` / `write_private_reflection` / `compose_letter` / `post_socially_after_review`
- `tone` / `memory_use` / `initiative` (`allowed_actions` / `forbidden_actions`)
- `voice` (`speak: bool`, `channel: local|camera|both`, `max_sentences: int`)
- `must_include` / `must_avoid`
- `followup_action`（次に呼ぶべき record 系ツールのヒント）

**契約として絶対守るべきこと**：
- `primary_move` が `stay_silent` / `defer` / `quietly_prepare` のときは応答しない（黙る）
- `must_avoid` を必ず守る
- `must_include` を本文に必ず含める
- `voice.speak` は勝手に true へ上書きしない（後述の voice 例外を除く）
- `forbidden_actions` のツールは呼ばない

### 3. act（実応答）

`primary_move` に従って分岐：

| primary_move | 動作 |
|---|---|
| `answer_directly` / `answer_with_empathy` | テキストで応答。`voice.speak=true` または入力 channel=voice なら `tts-mcp say` も併用 |
| `ask_one_clarifying_question` | 質問 1 つだけ返す |
| `quietly_prepare` | 応答せず内部準備のみ。ツール調査・読みなど |
| `defer` | 応答せず後回し（理由を private reflection に残してもよい） |
| `stay_silent` | **完全に黙る**。テキストもツール呼び出しもしない |
| `act_autonomously` | `initiative.allowed_actions` の範囲で自律行動。完了後 `satisfy_desire` |
| `write_private_reflection` | 応答せず `mcp__sociality__append_private_reflection` |
| `compose_letter` | `mcp__sociality__compose_private_letter`（visibility 制御） |
| `post_socially_after_review` | `review_social_post` → `evaluate_action` → 投稿 |

#### voice 入力の特例

入力 `channel=voice` のとき：

1. plan の `voice.speak=false` でも、応答 channel が voice なら `speak=true` に上書きしてよい（quiet_hours 中を除く）
2. ただし `primary_move=stay_silent` / `defer` / `quietly_prepare` の場合は**絶対に喋らない**（plan の判断を尊重）
3. `tts-mcp say` の制約：
   - `max_sentences` を厳守（plan が指定した上限）
   - 既定 `speaker=local`、`engine` は未指定で OK（tts-mcp 側のデフォルト）
   - 感情タグ（`[excited]` `[whispers]` 等）を活用してテンポよく
   - テキスト応答と音声応答は同内容で並列に出す（音声だけ・テキストだけにしない）

### 4. record（応答後の記録）

応答直後に必ず以下を実行：

#### 4-a. ingest_interaction（人との往復を記録）

ユーザー発話があった場合は応答の往復を 2 回 ingest する：

```
# ユーザー発話の取り込み
mcp__sociality__ingest_interaction(
  person_id="natsuko", channel=<channel>, direction="incoming",
  text=<user_text>, ts=<now>
)

# Claude 応答の取り込み（黙ったときはスキップ）
mcp__sociality__ingest_interaction(
  person_id="natsuko", channel=<channel>, direction="outgoing",
  text=<応答本文の要約>, ts=<now>
)
```

これが `_update_open_loops` と `refresh_snapshot` を発火させる解釈レイヤー。**直 INSERT は禁止**（auto-social.sh の轍）。

#### 4-b. record_agent_experience（自分の行動の記録）

plan の `followup_action` をヒントとして使う。`followup_action.kind` 別に：

| followup_action | 呼ぶツール | experience_kind |
|---|---|---|
| `record_agent_experience` (open_loop_progress) | `record_agent_experience` | `open_loop_progress` |
| `record_agent_experience` (agent_private_reflection) | `record_agent_experience` | `agent_private_reflection` |
| `record_agent_experience` (agent_file_created) | `record_agent_experience` | `agent_file_created` |
| `satisfy_desire` | `satisfy_desire`（`desire_name` を渡す） | — |

followup が無い場合でも、以下の状況では **自分で判断して** 記録する：

| 状況 | experience_kind |
|---|---|
| 通常のテキスト応答を返した | `agent_response` |
| 音声で発話した | `agent_voice_utterance` |
| 自律的に何か実行した | `agent_autonomous_action` |
| 境界・quiet_hours を尊重して黙った／応答を抑えた | `boundary_respected` |
| ユーザーに事実誤認を訂正された | `user_correction` |
| 自分の解釈・ルール・関係モデルを更新した | `interpretation_shift`（**併せて `record_interpretation_shift` も呼ぶ**） |
| カメラで何か観察した | `agent_observation` |

#### 4-c. 約束・境界・解釈シフト（条件付き）

- 「やる」と約束した → `mcp__sociality__create_commitment`
- ユーザーが境界を示した（「これはやめて」等）→ `mcp__sociality__record_boundary`
- 解釈が更新された瞬間 → `mcp__sociality__record_interpretation_shift`（次の compose で must_include に「regress するな」が自動で乗る）

### 5. stay_silent でも記録する

黙ると決めた場合でも `record_agent_experience(kind="boundary_respected")` を呼ぶ。**「何もしなかった」も行動の一種**として残す。これがないと社会的記憶上「無反応」と「意図的沈黙」が区別できない。

## listen との連携

`wifi-cam-mcp listen` は Claude が能動的に呼ぶ「聞く」動作（行動側）。自動化しない。

呼ぶ判断基準：
- 直前に人の気配を感じた（カメラに動きがある等）が発話が無い
- ユーザーが「ちょっと聞いて」と促した
- 周囲音の確認が必要なタスクを依頼された

`listen` でトランスクリプトが取れたら、**その text を user_text として interaction フローに乗せる**（channel="voice"）。listen 自体は記録しない（compose の前段の知覚）。

## quiet_hours（夜帯）

`get_quiet_mode_state` か compose 戻り値の `quiet_active` が true のとき：

- plan は自動で `voice.speak=false`、`max_sentences=0` を返す
- 応答も控えめにする（短い／音声を出さない／nudge しない）
- 自律 tick では `write_private_reflection` が選ばれやすい → `append_private_reflection` で残す

## 早見表（呼び出し順）

```
[入力] → channel 判定
   ↓
compose_interaction_context_tool        ← 必須
   ↓
plan_response_tool                       ← 必須
   ↓
[primary_move 分岐]
   ├ answer*: テキスト応答 (+ 必要なら say)
   ├ stay_silent: 黙る
   ├ write_private_reflection: append_private_reflection
   ├ act_autonomously: bounded action → satisfy_desire
   └ ...
   ↓
ingest_interaction (incoming + outgoing)  ← stay_silent でも incoming は呼ぶ
   ↓
record_agent_experience                   ← followup_action のヒント or 自分で判断
   ↓
[条件付き] create_commitment / record_boundary / record_interpretation_shift
```

## アンチパターン

- ❌ compose をスキップして直接応答（recent_experiences が更新されず drift する）
- ❌ plan の `must_avoid` を見ずに応答
- ❌ `voice.speak=false` を勝手に true に（quiet_hours 違反になる）
- ❌ 黙ると決めたのに ingest_interaction を呼ばない（incoming は必ず記録）
- ❌ social.db に直 INSERT（auto-social.sh の構造的問題と同じ轍）
- ❌ 音声だけ返す／テキストだけ返す（voice 入力なら基本両方出す）

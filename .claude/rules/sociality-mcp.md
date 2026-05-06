---
description: sociality-mcp（統合 façade）の全ツール一覧。詳細な対話フローは interaction/SKILL.md
paths: sociality-mcp/**/*.py
---

公開用 MCP は `sociality-mcp`（統合 façade）。内部実装は `social-state` / `relationship` / `joint-attention` / `boundary` / `self-narrative` / `interaction-orchestrator` の 6 サブパッケージに分割。

**対話フロー（compose → plan → act → record）の詳細は `.claude/skills/interaction/SKILL.md` を参照。** 以下はツールリファレンス。

### social-state（社会的状態）
- `ingest_social_event` / `get_social_state` / `should_interrupt` / `get_turn_taking_state` / `summarize_social_context`

### relationship（関係性）
- `upsert_person` / `ingest_interaction` / `get_person_model`
- `create_commitment` / `complete_commitment`
- `list_open_loops` / `suggest_followup`
- `record_boundary`

### joint-attention（共同注意）
- `ingest_scene_parse` / `resolve_reference`
- `get_current_joint_focus` / `set_joint_focus` / `compare_recent_scenes`

### boundary（行動ゲート）
- `evaluate_action` / `review_social_post`
- `record_consent` / `get_quiet_mode_state`

### self-narrative（自己要約）
- `append_daybook` (v0.3: concrete_events / noticed_changes / relationship_moments / next_gentle_actions 付き)
- `get_self_summary` (v0.3: recent experiences と interpretation_shifts を含む)
- `list_active_arcs` / `reflect_on_change`

### interaction-orchestrator（v0.3 オーケストレーション）
- `compose_interaction_context_tool` — 応答前の状況把握。social_state / relationship / open_loops / desire / recent_experiences / relevant_memories / response_contract を 1 回で返す
- `plan_response_tool` — primary_move / tone / voice / must_include / must_avoid / followup_action を決定
- `record_agent_experience` — 応答・行動・境界遵守などの experience 保存
- `record_interpretation_shift` — 解釈更新の瞬間を記録（以降の plan に「regress するな」制約が自動で乗る）
- `append_private_reflection` / `compose_private_letter` — 黙ったときのプライベート記録
- `get_agent_state` — 軽量な introspection（欲求・最近の experience・active arcs）

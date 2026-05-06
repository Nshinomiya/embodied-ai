---
description: memory-mcp（脳）のツール一覧と Emotion / Category 列挙
paths: memory-mcp/**/*.py
---

長期記憶システム（SQLite + sentence-transformers + BM25 + Modern Hopfield）。データ保存先は `~/.claude/memories/`。

### 想起・検索

| ツール | 説明 |
|---|---|
| `remember` | content, emotion?, importance?, category? を保存 |
| `search_memories` | query, n_results?, filters... |
| `recall` | context, n_results? — 文脈想起 |
| `recall_divergent` | context, max_branches?, max_depth?, temperature?, include_diagnostics? — 発散的想起 |
| `recall_with_associations` | context, chain_depth? — 関連記憶も含む |
| `list_recent_memories` | limit?, category_filter? |
| `get_memory_stats` | 統計情報 |
| `get_memory_chain` | memory_id, depth? |
| `get_association_diagnostics` | context, sample_size? |

### エピソード・連鎖

| ツール | 説明 |
|---|---|
| `create_episode` | title, memory_ids, participants?, auto_summarize? |
| `search_episodes` / `get_episode_memories` | エピソード検索・取得 |
| `link_memories` | source_id, target_id, link_type?, note? |
| `get_causal_chain` | memory_id, direction?, max_depth? |

### マルチモーダル

| ツール | 説明 |
|---|---|
| `save_visual_memory` | content, image_path, camera_position, emotion?, importance? |
| `save_audio_memory` | content, audio_path, transcript, emotion?, importance? |
| `recall_by_camera_position` | pan_angle, tilt_angle, tolerance? |

### 作業記憶・統合

| ツール | 説明 |
|---|---|
| `get_working_memory` / `refresh_working_memory` | 作業記憶バッファ |
| `consolidate_memories` | window_hours?, max_replay_events?, link_update_strength? — 海馬リプレイ風統合 |

### 列挙

- **Emotion**: `happy` / `sad` / `surprised` / `moved` / `excited` / `nostalgic` / `curious` / `neutral`
- **Category**: `daily` / `philosophical` / `technical` / `memory` / `observation` / `feeling` / `conversation`

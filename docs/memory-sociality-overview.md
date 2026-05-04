# memory-mcp と sociality-mcp 概要

> 作成: 2026-05-04 — セッション内の調査・議論を整理したもの

---

## 1. 全体像

embodied-ai における「記憶」と「社会性」は 2 つの MCP サーバーに分かれている。

```
memory-mcp          sociality-mcp
    │                     │
    │  HTTP /recall        │
    └──────────────────────►
                  compose_interaction_context
                  が内部で呼び出す
```

**memory-mcp** = 長期記憶の実体（SQLite: `memory.db`）  
**sociality-mcp** = 今この瞬間の判断・応答計画（memory-mcp を参照しながら動作）

---

## 2. memory-mcp

### 2-1. 何を保存するか

| 属性 | 選択肢 |
|---|---|
| **emotion** | happy / sad / surprised / moved / excited / nostalgic / curious / neutral |
| **category** | `core`（常に優先想起）/ daily / philosophical / technical / memory / observation / feeling / conversation |
| **importance** | 1〜5（5 が最重要） |
| sensory data | 画像パス・base64 JPEG コピー・音声パス |
| camera_position | pan / tilt 角度（視覚記憶の位置情報） |

### 2-2. 主要ツール

**保存**

| ツール | 用途 |
|---|---|
| `remember` | テキスト記憶を保存。類似記憶に自動リンク（閾値 0.8） |
| `save_visual_memory` | 画像付き記憶（低解像度コピーを DB 内に格納） |
| `save_audio_memory` | 音声 + トランスクリプト付き記憶 |

**想起**

| ツール | 特徴 |
|---|---|
| `recall` | E5 + BM25 + Hopfield ブレンド。最も高精度 |
| `search_memories` | ベクトル類似度のみ。シンプルな検索 |
| `recall_with_associations` | recall + リンク先を BFS 展開 |
| `recall_divergent` | temperature 付き発散想起（多様な連想） |
| `recall_by_camera_position` | pan/tilt 角度で視覚記憶を取得 |

**因果・リンク**

| ツール | 用途 |
|---|---|
| `link_memories` | similar / caused_by / leads_to / related でリンク |
| `get_causal_chain` | 因果チェーンを backward/forward に遡行 |

**高度な機能**

| ツール | 用途 |
|---|---|
| `tom` | 記憶から相手の心の理論（ToM）を推論 |
| `hypothesize` / `verify_hypothesis` | 行動前仮説の登録 → 結果検証（2 回棄却でアプローチ変更警告） |
| `consolidate_memories` | 海馬リプレイ風の統合（coactivation 強化） |

### 2-3. 内部アーキテクチャ

```
保存時: content → E5 encode_document → BLOB (SQLite)
想起時: query  → E5 encode_query ("query: " プレフィックス付き)
                → コサイン類似度（numpy 全件計算）
                + BM25 ブースト（日本語はふりがな索引も）
                + Hopfield ブースト（beta=4.0, n_iters=3）
                + 時間減衰 / 感情ブースト / 重要度ブースト
                → スコアが低いほど良い（距離ベース）
```

**coactivation テーブル**: 2 記憶が同時に想起されるたびに重みが増加。閾値（0.6）超えで自動リンク生成。

**HTTP エンドポイント**: ポート 18900 で `GET /recall?q=<query>` を公開。sociality-mcp がここを叩く。

---

## 3. sociality-mcp

### 3-1. 構成（ファサードパターン）

```
sociality-mcp（単一 MCP プロセス）
├── social-state-mcp       ← 今話しかけていいか
├── relationship-mcp       ← 人物モデル・約束・未解決話題
├── joint-attention-mcp    ← 共同注意・指示語解決
├── boundary-mcp           ← 倫理・プライバシー評価
├── self-narrative-mcp     ← 日記・内省・自己ナラティブ
└── interaction-orchestrator-mcp ← 上記を統合した応答計画生成
```

全サブパッケージは同一 SQLite（social DB）を共有。HTTP エンドポイントはポート 18901。

### 3-2. Heartbeat Protocol（推奨フロー）

```
1. compose_interaction_context_tool
   └── memory-mcp /recall を内部で叩き relevant_memories を取得
   └── social state / relationship / open loops / desires を集約
   └── response_contract（do / don't リスト）を生成

2. plan_response_tool
   └── primary_move を決定論的に導出:
       - quiet 時間中の自律 tick → write_private_reflection
       - availability = do_not_interrupt → stay_silent（override 禁止）
       - 質問形式 → answer_directly

3. act（allowed_actions のみ実行）

4. record_agent_experience
   └── 次の compose で recent_experiences として浮上
```

### 3-3. 主要ツール群

**social-state**: `get_social_state`（presence / activity / availability / affect_guess を返す）、`should_interrupt`、`get_turn_taking_state`

**relationship**: `upsert_person`、`ingest_interaction`、`get_person_model`、`create_commitment` / `complete_commitment`、`list_open_loops`、`record_boundary`

**joint-attention**: `ingest_scene_parse`、`resolve_reference`（「それ」等の指示語解決）、`get_current_joint_focus`

**boundary**: `evaluate_action`（発話・投稿前の倫理チェック）、`review_social_post`（顔・住所特定リスクまで検査）、`record_consent`

**self-narrative**: `append_daybook`、`get_self_summary`、`list_active_arcs`、`reflect_on_change`

### 3-4. socialPolicy.toml

プロジェクトルートに置く宣言的ポリシーファイル。boundary-mcp がここを参照する。

```toml
[global]
timezone = "Asia/Tokyo"      # 必須。未設定だと quiet_hours が UTC 解釈でズレる
quiet_hours = ["00:00-07:00"]

[[privacy_zones]]
name = "sleeping_area"
camera_presets = ["bed"]
deny_actions = ["speak_loud", "post_image"]

[[person_rules]]
person_id = "kouta"
avoid_actions = ["camera_speaker_after_midnight"]
```

---

## 4. 両者の使い分け

| 判断基準 | memory-mcp | sociality-mcp |
|---|---|---|
| **時間軸** | セッション横断・長期 | 今この瞬間・対話中 |
| **問い** | 「何があったか」「なぜそうなったか」 | 「今話しかけていいか」「どう応答すべきか」 |
| **直接呼ぶ場面** | 体験・好み・仮説の保存と想起 | 割り込み判断・投稿レビュー・応答計画 |

---

## 5. memory.db の活用方針（設計メモ）

| 記録先 | 向いているもの |
|---|---|
| **グローバル CLAUDE.md** | 絶対ルール（「必ず日本語で」「絵文字 NG」など） |
| **Auto Memory**（プロジェクト固有） | プロジェクト内の判断基準・経緯・フィードバック |
| **memory.db** | 文脈依存の学習済み好み・傾向・エピソード体験 |

memory.db の強みは「全部読む（ダンプ）」ではなく「文脈に合わせて想起する（サンプリング）」点。
`core` カテゴリに保存すると想起時に常に優先浮上する。

---

## 6. 関連ファイル

- `memory-mcp/src/memory_mcp/server.py` — ツール定義
- `memory-mcp/src/memory_mcp/store.py` — SQLite 永続化・スコアリング実装
- `sociality-mcp/src/sociality_mcp/server.py` — ファサード
- `sociality-mcp/packages/interaction-orchestrator-mcp/src/interaction_orchestrator_mcp/compose.py` — compose 実装
- `socialPolicy.toml` — boundary ポリシー

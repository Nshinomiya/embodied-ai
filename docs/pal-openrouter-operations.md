# pal-mcp + OpenRouter 運用ナレッジ

**最終更新:** 2026-05-09
**根拠セッション:** 2026-05-09 のセッションで実機検証 + consensus 試行で得た知見
**対象読者:** Claude（次回以降のセッション）/ ユーザー本人 / 後から参加する人

このドキュメントは、`pal-mcp`（複数の LLM プロバイダを束ねる MCP サーバー）を Claude Code から呼ぶときに繰り返し当たる **失敗パターン・コスト構造・モデル選択の指針** をまとめたもの。pal 自体には変更を加えず、**呼び出し側（Claude Code / SKILL）でカバーする運用** を前提とする。

---

## 1. 概要

### pal-mcp とは

- `mcp__pal__*` という名前空間で公開される MCP サーバー
- 内部で複数のプロバイダ API（OpenAI / Anthropic / Google / xAI / OpenRouter / 等）を切り替えて、統一的なツール（`chat` / `consensus` / `codereview` / `planner` / `debug` / `thinkdeep` / `precommit` / `challenge` / `apilookup` / `clink` 等）を提供する
- **このプロジェクトでの構成**: 設定済みプロバイダは **OpenRouter のみ**（27 モデル利用可能）。他は `*_API_KEY` 未設定で無効

### このドキュメントが解く問題

pal を Claude Code から呼んでいると、以下が繰り返し起きる：

1. **指定したモデルが API 側で 404**（preview 系・終了済みモデル）
2. **`max_tokens` 予約額不足の 402**（`gpt-5.2-pro` 等の高単価モデル）
3. **listmodels には載っているのに実呼び出しで失敗するモデルがある**
4. **コスト感がバラバラで、複数モデル並列の consensus がいきなり予算超過する**

これらは pal の責任ではなく **OpenRouter の課金構造 + プロバイダ側のエンドポイント生死** に起因する。事前検出 + フォールバックの仕組みを呼び出し側で持つしかない。

---

## 2. OpenRouter の課金モデル（重要）

### 2-1. `max_tokens × 出力単価` で事前予約する

OpenRouter は **リクエスト受付時に予約額を確保**する。実出力 token とは関係なく、`max_tokens` パラメータが要求する最大コストを **monthly credit limit から差し引けるか** を即時チェックし、不足なら **402** を返す。

```
要求: max_tokens=65536 / モデル: gpt-5.2-pro / 出力単価 ≈ $120/1M token
予約必要額 = 65536 × $120 / 1,000,000 ≈ $7.86
key の現状 afford 額 = $2.96  → 402
```

**生成は始まっていないので課金は発生していない**。ただしリクエストが通らない。

### 2-2. 「アカウント残高」と「key の monthly limit」は別

| 階層 | 内容 |
|---|---|
| アカウント残高（プリペイド） | OpenRouter ダッシュボードで確認できる累積ドル |
| API key の monthly limit | 個別キーごとに上限を設定可能。残高があってもキーの上限が低ければ早く弾かれる |

**402 エラーで参照されているのは key の monthly limit**。エラーメッセージに `https://openrouter.ai/settings/keys` が出るのはそのため。

### 2-3. 複数モデル並列リクエスト時の予約重複

`consensus` 等で複数モデルに同時に投げると、**同時に複数の予約**が走る。pal の consensus は**直列に呼んでいる挙動**だが（実際の観察）、リクエスト処理中はその予約が解放されない。安全な monthly limit は最も高い 1 モデル × 2-3 倍。

### 2-4. 推奨 monthly limit

| シナリオ | 推奨 |
|---|---|
| シングル `chat` のみ | $10（gpt-5.2-pro 1 回分の予約 $7.86 をカバー） |
| consensus 3 モデル | $20（複数モデル予約の重複を吸収） |
| 思考系（gpt-5.2-pro / opus 4.5）を頻用 | $30〜 |

3 ドル → 10 ドル → 20 ドル と段階的に上げていけば良い。**残高（プリペイド）は別途必要**。

---

## 3. 観察したエラー実例（2026-05-09 セッションの記録）

### 3-1. 404 No endpoints found（モデル不在）

```
OpenRouter API error for model google/gemini-3-pro-preview after 1 attempt:
Error code: 404 - {'error': {'message': 'No endpoints found for google/gemini-3-pro-preview.', 'code': 404}}
```

**原因**: OpenRouter 側で当該モデルの endpoint が一時的または恒久的に提供停止。`mcp__pal__listmodels` の結果には載っていても、実呼び出しで通るとは限らない。preview / 限定アクセス系は特に不安定。

**対処**:
- 安定版の同シリーズに切替（`gemini-3-pro-preview` → `gemini-2.5-pro`）
- `listmodels` は「ラインナップ」であって「ライブ可用性」ではない、と認識する
- consensus で 1 モデル 404 が出ても他モデルの結果は使えるので、回復可能

### 3-2. 402 max_tokens 予約超過

```
responses endpoint error after 1 attempt: Error code: 402 -
{'error': {'message': 'This request requires more credits, or fewer max_tokens.
You requested up to 65536 tokens, but can only afford 24710.
To increase, visit https://openrouter.ai/settings/keys ...'}}
```

**原因**: pal ツール内部で `max_tokens=65536` 固定で投げており、key の monthly limit が予約額に届かない。

**対処**:
- `max_tokens` をツール側で絞る方法は今のところない（pal の引数に存在しない）
- monthly limit を上げる（$10〜$20）か、安価モデルに切替

### 3-3. その他観察された傾向

- **gemini-2.5-pro** は安定。404 を踏みにくい
- **gpt-5.2** / **gpt-5.1-codex** はスコア 100 で thinking 対応、安定動作
- **claude-opus-4.5** はスコア 94 で 200K context、Anthropic ベンダーの代表として consensus に入れる価値あり

---

## 4. モデル一覧と単価感（pal listmodels 結果 + 推定単価）

### 設定済みプロバイダ: OpenRouter（27 モデル）

スコアは pal が独自に計算した総合指標（context size / thinking 対応 / 性能 / etc）。出力単価は OpenRouter 公開価格からの推定（変動するので数値はあくまで目安）。

#### スコア 100（最高位、思考系）

| Model ID | Context | Thinking | 推定出力単価 (per 1M) | max_tokens=65536 予約額 |
|---|---|---|---|---|
| `google/gemini-2.5-pro` | 1M | ✓ | ~$20 | ~$1.31 |
| `google/gemini-3-pro-preview` | 1M | ✓ | ~$20 | ~$1.31 |
| `openai/gpt-5.1-codex` | 400K | ✓ | ~$40 | ~$2.62 |
| `openai/gpt-5.2` | 400K | ✓ | ~$40 | ~$2.62 |
| `openai/gpt-5.2-pro` | 400K | ✓ | ~$120 | ~$7.86 |

#### スコア 90 台

| Model ID | Context | 推定出力単価 | 備考 |
|---|---|---|---|
| `anthropic/claude-opus-4.5` | 200K | ~$75 | Anthropic ベンダー代表 |
| `openai/gpt-5` | 400K | ~$30 | thinking |
| `openai/gpt-5-codex` | 400K | ~$30 | code-gen |
| `openai/gpt-5.1-codex-mini` | 400K | ~$15 | thinking、安価 |
| `x-ai/grok-4.1-fast` | **2M** | ~$8 | 巨大コンテキスト、thinking |
| `x-ai/grok-4` | 256K | ~$15 | thinking |

#### 中位（スコア 60-80）

| Model ID | Context | 備考 |
|---|---|---|
| `deepseek/deepseek-r1-0528` | 65K | 安価、thinking |
| `anthropic/claude-opus-4.1` | 200K | やや旧版 |
| `anthropic/claude-sonnet-4.5` | 200K | バランス |
| `mistralai/mistral-large-2411` | 128K | EU ベンダー |
| `openai/o3` / `o3-pro` / `o3-mini` 系 | 200K | 古い世代 |

#### 安価帯（スコア 40-60）

| Model ID | 備考 |
|---|---|
| `google/gemini-2.5-flash` | 1M context、thinking、激安 |
| `openai/gpt-5-mini` / `gpt-5-nano` | 軽量 |
| `anthropic/claude-3.5-haiku` | 200K、安い |
| `meta-llama/llama-3-70b` | 8K context のみ |

### 単価が分かる前のリスク減らし

- **未知のモデルを試すときはスコア低めから** → 単価不明でも被害が小さい
- **consensus で並列に 3 モデル使うときは「100/90/中位」のように散らす**

---

## 5. pal MCP ツール一覧と用途

### 軽量・対話系

| ツール | 用途 |
|---|---|
| `chat` | 単発の質問 / 会話。最も汎用 |
| `clink` | 別 LLM CLI（Codex / Gemini / Claude）を経由した specialized CLI 呼び出し |
| `apilookup` | API ドキュメント横断検索（最新情報取得） |

### 思考系

| ツール | 用途 |
|---|---|
| `thinkdeep` | 深い分析。複雑な推論を要する問題 |
| `planner` | 段階的計画立案。実行プラン作成 |
| `consensus` | 複数モデルの意見集約。重要意思決定 |
| `challenge` | 既存案への critical thinking。盲点発見 |

### 実装支援系

| ツール | 用途 |
|---|---|
| `debug` | バグ調査。再現手順から仮説提示 |
| `codereview` | コードレビュー。多観点でのレビュー |
| `precommit` | コミット前の最終チェック |

### メタ

| ツール | 用途 |
|---|---|
| `listmodels` | 利用可能なモデル一覧。**呼び出し前のチェック用** |
| `version` | pal 自体のバージョン |

### 各ツール共通の特徴

- ツール側で `max_tokens` パラメータを受け付けない（内部固定値、おそらく 65536）
- `model` 引数で個別モデル指定可
- `consensus` 等は内部で多段の workflow を持つ（step_number / total_steps を渡しながら走る）

---

## 6. consensus の使い方（実際に当たったケース）

### 6-1. 引数の組み立て

```python
mcp__pal__consensus(
    step="Evaluate ... <全モデルが見るプロンプト>",  # Step 1 のみ
    step_number=1, total_steps=4,                    # 3 モデル + synthesis
    next_step_required=True,
    findings="<Claude 自身の事前分析。他モデルには共有されない>",
    models=[
        {"model": "openai/gpt-5.2", "stance": "for", "stance_prompt": "..."},
        {"model": "google/gemini-2.5-pro", "stance": "against", "stance_prompt": "..."},
        {"model": "openai/gpt-5.1-codex", "stance": "neutral"}
    ]
)
```

### 6-2. ステップごとの仕事

| step_number | 役割 |
|---|---|
| 1 | 自分の独立分析 + 全モデルが見るプロンプト確定。最初のモデル呼び出しもこのステップで自動 |
| 2〜N | 各モデルの応答を `findings` に要約して次のモデルへ。`step` は短い注記でよい |
| N+1 | synthesis（すべての応答を assistant model が統合）。`next_step_required=False` |

### 6-3. ベンダー分散の指針

| ベンダー | 第一候補 | 第二候補 |
|---|---|---|
| OpenAI | `gpt-5.2` / `gpt-5.1-codex` | `gpt-5.2-pro`（高い） |
| Google | `gemini-2.5-pro` | `gemini-2.5-flash`（軽い） |
| Anthropic | `claude-opus-4.5` | `claude-sonnet-4.5` |
| xAI | `grok-4.1-fast` | `grok-4` |

異なるベンダーから 1 ずつ取ると視点が分散しやすい。同社内（gpt-5.2 と gpt-5.2-pro）だけだとバイアスが寄る傾向。

### 6-4. stance（賛成 / 反対 / 中立）の使い分け

- **for / against** を分けると、議論の対立軸が明確になり論点が浮かぶ
- 全員 **neutral** だと「無難で同じ意見」が並ぶリスク
- 推奨: 3 モデルなら `for / against / neutral` の三角形

---

## 7. 可用性事前チェック（skill 化を推奨）

### 7-1. なぜ skill か

- **タスク単位で自動発動**させたい（毎回コマンド打ちたくない）
- ユーザーの好み記録: 「自動発動させたいフローは skills、明示起動なら commands」
- rules では発動しない（`paths` 条件で編集中ファイルにマッチさせる仕組みなので、ツール呼び出し時には発動しない）

### 7-2. skill 配置の判断

- **プロジェクト内** (`.claude/skills/pal-consult/SKILL.md`): pal-mcp が `.mcp.json` で登録されているプロジェクト
- **Global** (`~/.claude/skills/pal-consult/SKILL.md`): pal-mcp が global で登録されている、もしくは複数プロジェクトで使う

embodied-ai の `.mcp.json` で pal が登録されているかは要確認。global の場合は `~/.claude/` 側に置くのが筋。

### 7-3. SKILL.md の最小構成案

```markdown
---
name: pal-consult
description: pal の consensus / chat / codereview 等のクラウドモデル系ツールを呼ぶ前に listmodels で可用性とコスト感を確認する。技術判断・コードレビュー・難題相談で起動する。
---

# pal-consult

pal の MCP ツールでモデルを呼ぶ前に、可用性 + コスト見積もりを取って失敗を防ぐ。

## 起動条件
- mcp__pal__consensus / chat / codereview / planner / thinkdeep / debug / challenge / precommit を呼ぶ直前

## フロー
1. mcp__pal__listmodels で対象モデルが Available か確認
2. 推定コスト（max_tokens × 単価）を docs/pal-openrouter-operations.md の表で照合
3. 高単価モデル（gpt-5.2-pro, claude-opus-4.5）を選ぶときは monthly limit に余裕があるか確認
4. preview 系（gemini-3-pro-preview 等）は安定版に降格を検討
5. consensus でベンダー分散させる（OpenAI / Google / Anthropic から 1 ずつ）
6. ツール呼び出し → 404/402 が出たらフォールバック表に従って再試行
```

詳細フローを書く場合は本ドキュメントを参照する形にして、SKILL.md は短く保つ。

---

## 8. トラブルシューティング

### 8-1. 404 No endpoints found

**症状**: 特定モデル ID で `404 No endpoints found for ...`

**手順**:
1. `mcp__pal__listmodels` で当該モデルがリストに載っているか確認
2. 載っていれば preview / 限定アクセス系の可能性。安定版に切替
3. 載っていなければ pal の構成 or OpenRouter 側で削除済み
4. `gemini-3-pro-preview` のような preview 系は通る日と通らない日がある。代替案: `gemini-2.5-pro`

### 8-2. 402 max_tokens 予約超過

**症状**: `Error code: 402 - You requested up to N tokens, but can only afford M`

**手順**:
1. エラーメッセージの `afford X` がそのキーで使える上限を示す
2. https://openrouter.ai/settings/keys で当該キーの monthly limit を上げる
3. もしくはモデルを 1 段安いものに切替（gpt-5.2-pro → gpt-5.2 で 1/3 程度）
4. consensus 内のモデル 1 つを安いものに変える / 2 モデルに減らす

### 8-3. 一部モデルだけ失敗、他は成功

**症状**: consensus で 3 モデル中 1 モデルがエラー

**手順**:
1. **そのまま synthesis に進む**（pal 側で部分結果を統合してくれる）
2. 重要な視点が抜けたら、別モデルで単独 `chat` 等を追加で呼んで補完

### 8-4. レイテンシが極端に大きい

**症状**: thinking 系（`gpt-5.2-pro`, `o3-pro`, `claude-opus-4.5`）が数十秒〜分単位で遅い

**手順**:
1. thinking 系は性質上遅い。タイムアウトを焦らず待つ
2. 急ぐなら `gpt-5.2` や `gemini-2.5-pro` に切替（thinking 強度は落ちる）
3. `grok-4.1-fast` は 2M context + 高速、長文処理には有利

---

## 9. 推奨設定まとめ

### 9-1. OpenRouter 側

- API key の monthly limit: **$20**（consensus でも安全、ほぼ全モデル使える）
- API key を「無制限」にすると暴走時に痛いので上限はかける
- 複数キー作って役割別に分けるのも有効（高単価用 / 通常用）

### 9-2. Claude Code 側

- `pal-consult` skill を作成（§7-3 参照）
- 本ドキュメント（`docs/pal-openrouter-operations.md`）を skill から参照する形にして、ナレッジは 1 箇所にまとめる
- consensus は 3 モデル以下に抑えて予算管理しやすくする

### 9-3. モデル選択の第一候補（2026-05 時点の経験則）

| 用途 | 第一候補 | 理由 |
|---|---|---|
| 軽い質問 | `gemini-2.5-flash` | 激安、1M context |
| 通常の chat / 計画 | `gpt-5.2` or `gemini-2.5-pro` | 性能と単価のバランス |
| 重要な技術判断 | `gpt-5.2-pro` or `claude-opus-4.5` | 思考力高い |
| 大量コンテキスト | `grok-4.1-fast`（2M） / `gemini-2.5-pro`（1M） | context window |
| consensus | OpenAI + Google + Anthropic 各 1 | 視点分散 |
| コード生成 | `gpt-5.1-codex` | 専用チューニング |

---

## 10. 参考リンク

- OpenRouter ダッシュボード: https://openrouter.ai/
- API key 設定: https://openrouter.ai/settings/keys
- モデル価格表: https://openrouter.ai/models
- pal-mcp（参考実装、本プロジェクトの設定に依存）: 各 MCP ツール定義を `mcp__pal__listmodels` で確認

---

## 11. このドキュメントの更新ガイドライン

- pal で新たな失敗パターンに当たったら **§3 観察したエラー実例** に追記
- モデルの単価が大きく変わったら **§4 単価感** を更新（推定値の括弧書きを実測値に）
- 新規モデルが pal に追加されたら listmodels 結果を再取得して **§4 一覧** を更新
- skill `pal-consult` を実装したら **§7** にパスを追記
- ナレッジが古くなったら最終更新日を上書き、当時のセッション ID も記録

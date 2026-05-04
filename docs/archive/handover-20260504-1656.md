# Session Handover

**最終更新:** 2026-05-04 12:30

---

## 前提と目的 (Context & Intent)

screen-read の実機テストは後回しにし、**memory-mcp と sociality-mcp の機能理解・初期設定**に集中したセッション。前セッションで memory.db が空のまま放置されていたため、システムの仕組みを把握しながら実際に動かすことが目的。

主なアジェンダ：
1. memory-mcp / sociality-mcp の機能・アーキテクチャの詳細調査
2. memory.db へのユーザー好みの記録
3. フック・デーモン類の現状診断
4. sociality の初期設定に向けた準備

---

## 成果と変更箇所 (Outcomes & Changed Files)

### git 上の変更

- `socialPolicy.toml` — `person_id = "kouta"` → `person_id = "slmbrCat"` に変更（ユーザーによる手動編集と思われる）
- `docs/memory-sociality-overview.md` — **新規作成（未コミット）**。memory-mcp / sociality-mcp の機能・ツール・アーキテクチャ・使い分け・設計方針を網羅したリファレンスドキュメント

### memory.db への記録（コミット対象外）

4 件の `core` カテゴリ記憶を保存済み：

| 内容 | 重要度 |
|---|---|
| 応答スタイル好み（簡潔・根拠重視） | 4 |
| memory.db 設計方針（CLAUDE.md / Auto Memory との分担） | 5 |
| カスタマイズ学習の関心方向（認知アーキテクチャ・HRI） | 4 |
| Obsidian PKM / screen-read 環境 | 4 |

---

## 検討と意思決定 (Decisions & Rationale)

- **判断:** memory.db をユーザー好み・振る舞い指示の保存先としても使う
  - **理由:** CLAUDE.md は「全部読む（ダンプ）」だが memory.db は「文脈に合わせて想起（サンプリング）」。文脈依存の好みや傾向には memory.db の方が適している
  - **分担設計:** CLAUDE.md（グローバル）= 絶対ルール、memory.db = 文脈依存の学習済み好み、Auto Memory = プロジェクト固有の判断基準

- **判断:** socialPolicy.toml の person_id を `slmbrCat` に変更
  - **理由:** 実際のユーザー名に合わせる（旧 `kouta` はプレースホルダー）
  - **影響:** boundary-mcp の `person_rules` が `slmbrCat` で評価されるようになる

---

## フック・インフラ現状診断

### 動作中 ✅

| コンポーネント | 場所 | 備考 |
|---|---|---|
| `auto-recall.sh` | UserPromptSubmit フック | memory HTTP:18900 を叩き関連記憶をコンテキスト注入。毎ターン動作確認済み |
| `interoception.sh` | UserPromptSubmit フック | daemon 未起動のため時刻・曜日のみ出力（縮退動作） |
| `memory.db` | `~/.claude/memories/memory.db` | 4 件保存済み |

### 未設定・未動作 ❌

| コンポーネント | 問題 | 対処方針 |
|---|---|---|
| `social.db` | `~/.claude/sociality/` ディレクトリごと存在しない | sociality MCP ツール（`upsert_person` 等）を一度呼べば自動生成される |
| `auto-social.sh` | social.db が存在しないため毎回 exit 0 | social.db 生成後は自動で有効化される |
| heartbeat daemon | WSL2 では launchd (plist) / systemd が使えない | cron（`crontab -e`）か `/etc/init.d` スタイルで代替する必要あり |

### フック定義場所

`.claude/settings.json` の `UserPromptSubmit` に 3 フック登録済み：
- `interoception.sh` — `/tmp/interoception_state.json` を読んで体の状態を注入
- `auto-recall.sh` — memory-mcp HTTP `/recall` を叩いて関連記憶を注入
- `auto-social.sh` — コウタ（slmbrCat）の発話を social.db に直接 INSERT

heartbeat daemon のスクリプト（`.claude/hooks/heartbeat-daemon.sh`）は存在する。5 秒ごとに arousal / thermal / mem_free を `/tmp/interoception_state.json` に書き出す設計。

---

## ハマった点・失敗したアプローチ (Friction & Anti-patterns)

- **問題:** social.db の場所を最初 `~/.claude/memories/` と思い込んで確認した
  - **正解:** `~/.claude/sociality/social.db`（`auto-social.sh` のソースから判明）
  - **教訓:** sociality-mcp は memory-mcp と別ディレクトリに DB を持つ

- **問題:** heartbeat daemon の起動方法が WSL2 と macOS で異なる
  - **plist ファイル** (`com.embodied-claude.heartbeat.plist`) は macOS launchd 用、WSL2 では無効
  - **WSL2 での代替:** cron ジョブ（`* * * * * /path/heartbeat-daemon.sh`）が最も単純

---

## 次にやること (Next Steps)

### 1. sociality 初期化（最優先）

```bash
# upsert_person で slmbrCat を登録 → social.db が自動生成される
# MCP ツールを Claude に頼んで呼んでもらうか、直接 MCP 経由で実行
# person_id は socialPolicy.toml と一致させる
```

1. [ ] `mcp__sociality__upsert_person` を呼んで `slmbrCat` を登録
2. [ ] `~/.claude/sociality/social.db` が生成されたことを確認（`ls ~/.claude/sociality/`）
3. [ ] `auto-social.sh` が動き出すことを確認（次のメッセージ送信後に実行されるはず）

### 2. heartbeat daemon を WSL2 で起動

4. [ ] cron で heartbeat-daemon.sh を定期実行するよう設定：
   ```bash
   crontab -e
   # 追加: * * * * * /home/slmbrcat/projects/embodied-ai/.claude/hooks/heartbeat-daemon.sh
   ```
5. [ ] `/tmp/interoception_state.json` が生成されることを確認
6. [ ] interoception フックが arousal / thermal / mem_free を出力するようになることを確認

### 3. compose → plan フローの試運転

7. [ ] `mcp__sociality__compose_interaction_context_tool` を呼んで InteractionContext を確認
8. [ ] `mcp__sociality__plan_response_tool` で ResponsePlan を取得
9. [ ] memory.db の記憶が `relevant_memories` に乗ってくることを確認

### 4. socialPolicy.toml の変更をコミット

10. [ ] `socialPolicy.toml` の `person_id = "slmbrCat"` 変更をコミット
11. [ ] `docs/memory-sociality-overview.md` を合わせてコミット

---

## 参考情報

### フックファイル一覧（`.claude/hooks/`）

```
interoception.sh        # UserPromptSubmit: 体の状態注入
auto-recall.sh          # UserPromptSubmit: memory.db から連想想起
auto-social.sh          # UserPromptSubmit: 発話を social.db に記録
continue-check.sh       # Stop フック
post-compact-recovery.sh # SessionStart(compact) フック
heartbeat-daemon.sh     # daemon 本体（cron で実行する）
install-heartbeat.sh    # macOS launchd インストーラ（WSL2 では不使用）
com.embodied-claude.heartbeat.plist  # macOS launchd 設定（WSL2 では不使用）
```

### DB パス

| DB | パス |
|---|---|
| memory.db | `~/.claude/memories/memory.db` |
| social.db | `~/.claude/sociality/social.db`（未作成） |

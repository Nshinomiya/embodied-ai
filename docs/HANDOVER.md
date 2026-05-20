# Session Handover

**最終更新:** 2026-05-20 11:23

---

## 前提と目的 (Context & Intent)

前セッション（2026-05-09 10:49）の続き。Phase 1（VOICEVOX 接続）に取り組んだが WSL2 の `networkingMode=mirrored` が反映されない問題に当たっていた。

このセッションの主目的（実際に進んだ範囲）:
1. mirrored 修復の最終切り分け（Windows 再起動 + ESET 停止後も改善せず確認）
2. `0.0.0.0` バインドを選ぶ場合のセキュリティ判断を pal consensus で多角的に検証
3. consensus 試行中に **OpenRouter の課金モデル（max_tokens × 出力単価で事前予約）**, **preview 系モデルの 404**, **モデル可用性事前チェックの skill 化案** など pal 運用のナレッジが得られた
4. それらを **`docs/pal-openrouter-operations.md` (376 行) として詳細ドキュメント化**

VOICEVOX 接続そのものは未完遂（ユーザーが VOICEVOX 設定で `0.0.0.0` バインドに変更する作業が次セッション）。

---

## 成果と変更箇所 (Outcomes & Changed Files)

### 新規ファイル

- `docs/pal-openrouter-operations.md` (新規・376 行) — pal-mcp + OpenRouter 運用の知識ベース
  - 11 章構成: 概要 / 課金モデル / 観察したエラー実例 / モデル一覧と単価感 / pal ツール / consensus / skill 化提案 / トラブルシューティング / 推奨設定 / 参考リンク / 更新ガイドライン
  - 404（`gemini-3-pro-preview`） / 402（`gpt-5.2-pro`）の生メッセージを保存（後で同症状を照合可能）
  - モデル別予約額試算（gpt-5.2-pro $7.86 / gpt-5.2 $2.62 / gemini-2.5-pro $1.31）
- `docs/archive/handover-20260509-1049.md` (前回 HANDOVER の退避)
- `docs/archive/handover-20260520-1123.md` (今回の handover skill 実行時の退避)

### 更新

- `docs/HANDOVER.md` — このファイル
- `docs/CHRONICLE.md` — 今回のセッション 1 行追記

### コード変更なし

WSL2 / Windows / ESET 設定確認のみ。Working tree でのコード変更はゼロ。

---

## 検討と意思決定 (Decisions & Rationale)

### 1. mirrored networking の修復は完全に打ち切り

- **判断:** これ以上 mirrored networking の調査・修復は行わない。`0.0.0.0` バインド + Windows Firewall scoping に切り替える
- **理由:** Windows 再起動 + WSL update + ESET 「保護を一時停止」を試したが、`ip addr` / `/etc/resolv.conf` / `curl localhost:50021` すべて NAT モードの徴候のまま不変。Windows 11 24H2 build 26200 系 + ESET の組み合わせで mirrored が機能しない事象は環境特有のバグと判断。pal consensus の GPT-5.2（for）も「ROI 悪い、追加投資は 30〜60 分以内に限定」と評価
- **代替案:**
  - ESET ファイアウォールモジュールを完全無効化 → 侵襲的で本セッションでは見送り。次セッションで実施したい場合のみ
  - Windows portproxy → 永続性問題で非推奨
  - Docker WSL 内 VOICEVOX → GPU/audio で苦労、最大複雑度

### 2. `0.0.0.0` バインドは家庭 LAN 限定で受け入れ可（条件付き）

- **判断:** VOICEVOX を `0.0.0.0:50021` で待ち受け、Windows Firewall でインバウンドを Private プロファイル + サブネット `192.168.10.0/24` に限定
- **理由:** consensus（GPT-5.2 信頼度 8/10）+ 独立分析で一致した結論。家庭 LAN・デスクトップ専用・信頼端末のみ・VOICEVOX が認証なし TTS（破壊操作なし）という条件下では、最大リスクは LAN 内端末からの CPU 消費 DoS 程度
- **重要前提:** Windows のネットワークプロファイルが Public ではなく Private になっていること。誤って Public のまま外で WiFi に繋ぐと露出
- **代替案:** SSH tunnel（追加運用コスト）、portproxy（IPv4/IPv6 混乱・永続性不安定）、Docker WSL 内（重い）

### 3. OpenRouter の課金モデルを正しく理解し monthly limit を引き上げる

- **判断:** OpenRouter API key の monthly limit を **$10〜$20** に引き上げる
- **理由:** 402 エラーは「実残高」ではなく「リクエスト時の `max_tokens × 出力単価` 予約額が key の monthly limit を超える」事象。`gpt-5.2-pro` で `max_tokens=65536` の予約は約 $7.86 必要、現行 key 上限が約 $3 弱だったため弾かれた
- **推奨額:** シングル `chat` なら $10、consensus 並列なら $20、高単価モデル頻用なら $30+

### 4. pal の可用性事前チェックは skill 化が筋

- **判断:** `pal-consult` という skill を作る方針（実装は次セッション）
- **理由:** タスク単位で自動発動させたい / 毎回コマンド打ちたくない / Memory に記録された好み「自動発動は skills、明示起動は commands」と合致 / rules は paths 条件でツール呼び出し時に発動しない
- **配置場所:** プロジェクト内 (`embodied-ai/.claude/skills/pal-consult/SKILL.md`) と global (`~/.claude/skills/pal-consult/SKILL.md`) の判断は pal-mcp の登録場所による。**次セッションで `.mcp.json` の場所を確認した上で決定**

### 5. pal-openrouter-operations.md は docs 配下に常設

- **判断:** 知識ベースとして `docs/pal-openrouter-operations.md` に集約。skill が必要に応じて参照する
- **理由:** 詳細な単価表 / エラー実例 / モデル別フォールバック表は SKILL.md に書くと肥大化する。skill は短く保ち、参照先として docs に切り出す（CLAUDE.md 縮約と同じ設計判断）

---

## ハマった点・失敗したアプローチ (Friction & Anti-patterns)

### F-1: WSL2 mirrored mode が複数の対処を経ても効かず

- **問題:** `.wslconfig` 設定正・WSL バージョン正・カーネル正・Windows ビルド正にもかかわらず、Windows 再起動 + `wsl --update` + `wsl --shutdown` + ESET 「保護を一時停止」を全部試して `ip addr` が NAT のまま
- **試したこと:**
  - Windows 再起動（電源 off → on）
  - `wsl --update`
  - 複数回の `wsl --shutdown` → 再起動（uptime=1min を毎回確認）
  - ESET の「保護を一時停止」（10 分間）
- **結果:** `ip addr` に Windows 側 NIC が一切現れない、`/etc/resolv.conf` の nameserver は `10.255.255.254` のまま、`curl localhost:50021/version` は timeout (exit 28)
- **学び:** ESET の「保護を一時停止」では **ネットワークフィルタリングドライバ自体は動き続ける**。これを切るにはサービス完全停止 or アンインストールが必要。これ以上の侵襲は ROI が悪いので mirrored 諦め

### F-2: pal consensus で 2/3 モデルが API エラー

- **問題:** consensus を 3 モデル（for: gpt-5.2 / against: gemini-3-pro-preview / neutral: gpt-5.2-pro）で実行したが、2 つがエラー
- **エラー内容:**
  - `google/gemini-3-pro-preview`: **404 No endpoints found**（OpenRouter 側で当該モデル提供停止）
  - `openai/gpt-5.2-pro`: **402 max_tokens=65536 / can only afford 24710**（key の monthly limit が予約額に届かない）
- **学び:**
  - `listmodels` は「ラインナップ」であって「ライブ可用性」ではない。preview 系（gemini-3-pro-preview 等）は通る日と通らない日がある
  - pal の各ツールは `max_tokens` パラメータを引数で受け付けないので、内部固定値（65536）でのコスト試算が必要
  - **次回 consensus する時は安定版モデルを選ぶ**（gemini-2.5-pro / gpt-5.2 / claude-opus-4.5 等）

### F-3: pal `--max_tokens` 引数を絞れない

- **問題:** `gpt-5.2-pro` の 402 を回避するため `max_tokens` を絞りたいが、ツール定義（mcp__pal__consensus 等）に `max_tokens` パラメータが存在しない
- **学び:** pal の構成変更はしたくないので、monthly limit を引き上げるか安価モデルに切り替えるしかない

---

## 次にやること (Next Steps)

### Phase 1 完遂（VOICEVOX 接続 — 最優先）

1. [ ] VOICEVOX の設定 → 詳細設定 → **「他のホストからの接続を許可」を ON**（or「ホスト」項目を `0.0.0.0`）
2. [ ] VOICEVOX を**完全に終了 → 再起動**（GUI 内の「エンジンの再起動」だけだと反映されないことあり）
3. [ ] Windows 側 `netstat -an | findstr 50021` で `0.0.0.0:50021 ... LISTENING` 確認
4. [ ] Windows Firewall インバウンドルールを確認（Private プロファイルのみ、サブネット `192.168.10.0/24` に限定推奨）
5. [ ] WSL から `curl http://localhost:50021/version` で接続テスト → JSON 文字列が返れば成功
6. [ ] WSL から `curl -s http://localhost:50021/speakers | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'speakers: {len(d)}')"` で speaker 一覧確認

### Phase 1 完遂（API キー、任意）

7. [ ] ElevenLabs API キーを `/home/slmbrcat/projects/embodied-ai/.mcp.json` の `ELEVENLABS_API_KEY` プレースホルダに入れる（VOICEVOX 主軸ならスキップ可）
8. [ ] Claude Code を `/exit` → `claude` で再起動
9. [ ] `mcp__tts__say` がツール一覧に出ることを確認
10. [ ] `mcp__tts__say(text="こんにちは", engine="voicevox", voicevox_speaker=3, speaker="local")` で素疎通確認

### OpenRouter monthly limit 引き上げ

11. [ ] https://openrouter.ai/settings/keys で当該 API key の monthly limit を **$10〜$20** に引き上げる
12. [ ] 引き上げ後、consensus で `gpt-5.2-pro` が通るか確認したい場合は別途検証

### pal-consult skill の実装

13. [ ] `.mcp.json` の pal-mcp 登録場所を確認（プロジェクト内 or global）
14. [ ] `pal-consult/SKILL.md` を作成（雛形は `docs/pal-openrouter-operations.md` §7-3 参照）
15. [ ] SKILL.md から `docs/pal-openrouter-operations.md` を参照する形にして、SKILL は短く保つ

### Phase 4 試運転（マイルストーン到達）

16. [ ] **E-1 テキスト 1 ターン（フル）**: `plan_response_tool` 経由を含めて改めて試運転
17. [ ] **E-2 `/voice` 1 ターン**: VOICEVOX で音声合成、speaker=local
18. [ ] **E-3 quiet_hours 模擬**: 深夜帯（22:00-07:00）or fixture で `say` が呼ばれないことを確認
19. [ ] **E-4 wifi-cam `listen` 連携**（任意・P2）

合格基準は `docs/archive/handover-20260506-1531.md` 末尾参照。

### 諦めなければの追加調査（mirrored を本気で直したい場合）

20. [ ] ESET ファイアウォールモジュールを**完全無効化**（保護一時停止ではなく、サービス停止 or アンインストール）→ `wsl --shutdown` → 再起動 → 再確認
21. [ ] それでも駄目なら受容するか、ESET 自体を別の AV に変える検討

### 継続改善: メタ層（Step 5、観測ベース着手）

22. [ ] `scripts/meta_layer_observation.py` 作成（social.db 週次集計）
23. [ ] 1 週間運用後、トリガー成立シグナルから着手

---

## 参考情報

### Critical Files for Implementation

- `/home/slmbrcat/projects/embodied-ai/.mcp.json` — tts エントリ完成、API キー（ElevenLabs）のみ置換待ち
- `/home/slmbrcat/projects/embodied-ai/docs/pal-openrouter-operations.md` — **新規。pal-mcp + OpenRouter の運用ナレッジ集積。今後の pal 利用時に参照**

### consensus 試行のスナップショット（2026-05-20 セッション）

問題: `0.0.0.0 バインドのセキュリティ判断` を 3 モデルで評価

| モデル | スタンス | 結果 |
|---|---|---|
| `openai/gpt-5.2` | for | ✅ 成功、信頼度 8/10、「Conditionally acceptable」と評価 |
| `google/gemini-3-pro-preview` | against | ❌ 404 No endpoints found |
| `openai/gpt-5.2-pro` | neutral | ❌ 402 max_tokens 予約超過 |

結論: GPT-5.2 + 独立分析で意思決定可能（`0.0.0.0` バインド + Windows Firewall scoping）。

### 推奨モデル選択（次回 consensus 時）

| 用途 | 第一候補 |
|---|---|
| 通常の chat | `openai/gpt-5.2` |
| 大量コンテキスト | `x-ai/grok-4.1-fast`（2M context） |
| consensus | OpenAI + Google + Anthropic 各 1（`gpt-5.2` / `gemini-2.5-pro` / `claude-opus-4.5`） |

詳細は `docs/pal-openrouter-operations.md` §6 参照。

### 当時の WSL / Windows 環境

- WSL バージョン: 2.4.12.0
- カーネル: 5.15.167.4-microsoft-standard-WSL2
- Windows ビルド: 26200.8246（24H2 系）
- ESET: 有効（保護一時停止後もネットワークフィルタドライバは動作）
- `.wslconfig`: `[wsl2]\nswap=8388608000\nnetworkingMode=mirrored\n`（中身は正、反映されない）

---
description: tts-mcp の say ツールと Claude Code 音声モード（/voice）連携の動作規約
paths: tts-mcp/**/*.py
---

TTS 統合サーバー（声）。ElevenLabs + VOICEVOX 切替対応。

### ツール

| ツール | パラメータ | 説明 |
|---|---|---|
| `say` | text, engine?, voice_id?, model_id?, output_format?, voicevox_speaker?, speed_scale?, pitch_scale?, play_audio?, speaker? | 音声合成して発話。`speaker`: `local` / `camera` / `both` |

### Claude Code 音声モード（/voice）連携

`/voice` で音声入力を有効化 → 認識 → tts-mcp で音声返答することで完全な音声対話が成立。

**動作規約**:
- ユーザーが話しかけてきたら、テキスト返答と同時に `say` で音声でも返答
- `speaker` は `local` を基本、go2rtc 設定済みなら `camera` も可
- 感情タグ（`[excited]` `[whispers]` 等）を積極的に使ってテンポよく
- 音声は **1〜3 文程度**に抑える

### `/voice` と wifi-cam `listen` の使い分け

| 機能 | 用途 |
|---|---|
| `/voice` | **PC のマイク**で話しかける。リアルタイム音声入力 |
| wifi-cam `listen` | **カメラ内蔵マイク**で周囲音を拾う。遠隔地確認用 |

### エンジン使い分け（ElevenLabs / VOICEVOX）

両エンジンが `.mcp.json` で利用可能。状況に応じて `say` の `engine` 引数で切替：

| エンジン | 強み | 弱み | 使う場面 |
|---|---|---|---|
| ElevenLabs | 感情タグ豊か、自然な日本語、声色多様 | 有料、API キー必要、API レイテンシ | 感情を乗せたい応答、相手との情緒的やり取り |
| VOICEVOX | 無料、ローカル動作、低レイテンシ | 感情タグなし（speaker ID で声色だけ） | 短い相槌、機械的な応答、深夜帯（API 課金回避） |

**既定**: `mcpBehavior.toml [tts] default_engine = ""`（auto-detect）の場合、ElevenLabs を優先（backward compat）。VOICEVOX を主軸にしたければ `default_engine = "voicevox"` か呼び出し時に `engine="voicevox"` 明示。

**VOICEVOX 起動前提**: VOICEVOX エンジン本体（GUI 版 or Docker 版）が `localhost:50021` で動いていること。未起動なら ElevenLabs に自動 fallback。

### アンチパターン

- ❌ **音声だけ返す / テキストだけ返す**（voice 入力時は text + voice を**並列に**返す。片方だけはトレース性が落ちる）
- ❌ `voice.speak=false` を勝手に true へ（quiet_hours / stay_silent 違反になる。SKILL.md の voice 例外条件を必ず確認）
- ❌ `max_sentences` を超えて喋る（plan の上限を厳守）
- ❌ ElevenLabs の感情タグ構文（`[excited]` 等）を VOICEVOX に渡す（無視されるか変な合成になる）

詳細な対話フロー（compose → plan → say → record）は `.claude/skills/interaction/SKILL.md` を参照。

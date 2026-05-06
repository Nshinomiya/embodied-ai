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

詳細な対話フロー（compose → plan → say → record）は `.claude/skills/interaction/SKILL.md` を参照。

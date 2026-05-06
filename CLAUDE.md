# Embodied AI

Claude に身体（目・首・耳・声・脳）を与え、その上に sociality（社会的中間層）を積む MCP サーバー群。

**質問に答える前・変更を加える前**: 必ず `docs/CHRONICLE.md` と `docs/HANDOVER.md` を読む。

## 設計原則: 身体メタファー三層モデル

| 層 | 性質 | 自動化 | 例 |
|---|---|---|---|
| **下位層**（不随意・知覚） | OK | interoception / auto-recall / heartbeat-daemon |
| **上位層**（随意・行動） | NG（Claude 判断） | ingest_interaction / record_agent_experience / append_daybook |
| **メタ層**（自己認識補助） | OK（行動は強制しない） | followup pending 警告 / 経過ターン注入 |

上位層をスクリプトで肩代わりしない。SKILL.md に書いて Claude 自身に呼ばせる。

## ディレクトリ

```
embodied-ai/
├── usb-webcam-mcp/         # 目（USB）
├── wifi-cam-mcp/           # 目・首・耳（Wi-Fi PTZ）
├── tts-mcp/                # 声（ElevenLabs / VOICEVOX）
├── memory-mcp/             # 脳（長期記憶）
├── system-temperature-mcp/ # 体温感覚
├── social-core/            # sociality 共通 DB
├── sociality-mcp/          # 統合 façade（packages/ に内部実装）
├── socialPolicy.toml       # boundary 既定ポリシー
└── .claude/
    ├── rules/              # パス別規約（自動注入）
    ├── skills/             # タスク別フロー
    └── hooks/              # 知覚層・メタ層
```

## 規約と運用

- 各サブプロジェクトの開発規約・ツール一覧は `.claude/rules/`（パス条件で自動注入される）
- 対話応答ループは `.claude/skills/interaction/SKILL.md`
- セキュリティ: `.env` は絶対コミットしない

## 関連リンク

- [MCP Protocol](https://modelcontextprotocol.io/)
- [go2rtc](https://github.com/AlexxIT/go2rtc) — RTSP / オーディオバックチャンネル
- [claude-code-webui](https://github.com/sugyan/claude-code-webui) — モバイル操作用

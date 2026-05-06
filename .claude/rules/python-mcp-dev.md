---
description: Python MCP サブパッケージ共通の開発規約（uv / pytest / ruff）
paths: usb-webcam-mcp/**/*.py,wifi-cam-mcp/**/*.py,tts-mcp/**/*.py,memory-mcp/**/*.py,system-temperature-mcp/**/*.py,sociality-mcp/**/*.py,social-core/**/*.py
---

- パッケージマネージャー: **uv**
- Python: 既存サーバー 3.10+、sociality MCP 群 3.12+
- テスト: pytest + pytest-asyncio
- リンター: ruff
- 非同期: asyncio ベース

```bash
uv sync --extra dev   # 依存（dev 含む）
uv run ruff check .   # lint
uv run pytest -v      # test
uv run <server-name>  # 起動
```

**コミット前必須**: 該当サブプロジェクトで `uv run ruff check .` と `uv run pytest -v` の両方を通すこと。

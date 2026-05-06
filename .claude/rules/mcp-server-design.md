---
description: MCP サーバー実装の設定分離（.env / mcpBehavior.toml）と jurigged ライブリロード
paths: usb-webcam-mcp/**/server.py,wifi-cam-mcp/**/server.py,tts-mcp/**/server.py,memory-mcp/**/server.py,system-temperature-mcp/**/server.py,sociality-mcp/**/server.py,mcpBehavior.toml
---

設定は **シークレット**（`.env`）と **行動設定**（`mcpBehavior.toml`）に分離する。

### `.env`（シークレット）
- API キー、パスワード、ホスト名など接続情報
- `.gitignore` 済み、コミットしない
- 各サーバーディレクトリに配置

### `mcpBehavior.toml`（行動設定）
- プロジェクトルートに配置
- Claude が直接編集可能な動作パラメータ
- **ツール呼び出しごとに最新の値を読み込む**（サーバー再起動不要）
- 優先度: TOML > 環境変数 > デフォルト値

### ライブリロード（jurigged）
- 各サーバーは `jurigged` 対応。**関数本体の変更は即反映**（シグネチャ変更は再起動必要）
- `jurigged` は optional dependency。未インストールでもサーバーは正常動作

### MCP サーバーログ確認
```bash
cd <server-dir> && uv run <server-name>   # 直接起動でログを見る
```

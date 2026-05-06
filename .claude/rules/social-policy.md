---
description: socialPolicy.toml の書き方と timezone 設定の必須化
paths: socialPolicy.toml
---

リポジトリ直下の `socialPolicy.toml` に timezone / quiet_hours / privacy_zones / posting_rules / person_rules を書く。boundary-mcp の既定ポリシー。

### 必須設定

```toml
[global]
timezone = "Asia/Tokyo"
```

v0.3 以降この `[global] timezone` は**必ず設定**する。未設定だと UTC で解釈され、JST 深夜帯の quiet-hour 判定がずれる。

### ポリシー解決

- ファイルは cwd から親ディレクトリへ **walk-up で自動検出**されるので、MCP サーバーを sub-package から起動しても拾える
- `SOCIAL_POLICY_PATH` 環境変数で明示パス指定可能（walk-up より優先）

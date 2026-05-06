---
description: system-temperature-mcp のツールと WSL2 制約
paths: system-temperature-mcp/**/*.py
---

体温感覚センサー。

| ツール | 説明 |
|---|---|
| `get_system_temperature` | システム温度 |
| `get_current_time` | 現在時刻 |

### WSL2 制約

WSL2 では `/sys/class/thermal/` にアクセスできない。Windows 側のセンサー API 経由か、フォールバック実装になる。

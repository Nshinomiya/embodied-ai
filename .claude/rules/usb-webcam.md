---
description: usb-webcam-mcp のツール一覧と WSL2 usbipd 注意事項
paths: usb-webcam-mcp/**/*.py
---

USB ウェブカメラ（目）。WSL2 では `usbipd` でカメラを WSL に転送する必要がある。

| ツール | パラメータ | 説明 |
|---|---|---|
| `list_cameras` | なし | 接続カメラ一覧 |
| `see` | camera_index?, width?, height? | 画像キャプチャ |

### デバッグ
```bash
v4l2-ctl --list-devices
```

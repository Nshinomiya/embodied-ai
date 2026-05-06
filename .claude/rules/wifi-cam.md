---
description: wifi-cam-mcp のツール一覧と Tapo / Imou カメラ設定差異
paths: wifi-cam-mcp/**/*.py,wifi-cam-mcp/**/*.toml
---

ONVIF 対応 Wi-Fi PTZ カメラ（目・首・耳）。複数メーカー対応。

### ツール（基本）

| ツール | パラメータ | 説明 |
|---|---|---|
| `see` | なし | 画像キャプチャ |
| `look_left/right` | degrees (1-90, default: 30) | 左右パン |
| `look_up/down` | degrees (1-90, default: 20) | 上下チルト |
| `look_around` | なし | 4方向スキャン |
| `camera_info` / `camera_presets` | なし | デバイス情報 / プリセット一覧 |
| `camera_go_to_preset` | preset_id | プリセット移動 |
| `listen` | duration (1-30秒), transcribe? | カメラ内蔵マイクで音声録音 |

### ステレオ視覚（右目がある場合）

`see_right` / `see_both` / `right_eye_look_*` / `both_eyes_look_*` / `get_eye_positions` / `align_eyes` / `reset_eye_positions`。基本ツールと同形式で右目・両眼を制御。

### Tapo カメラ（TP-Link）
- Tapo アプリで**ローカルアカウント**を作成（TP-Link アカウントではない）
- PTZ: ONVIF RelativeMove（`ptz_mode=auto` or `relative`）
- RTSP: `rtsp://{user}:{pass}@{host}:554/stream1`
- ONVIF ポート: 2020

### Imou カメラ（Dahua 系）
- Imou Life アプリでデバイスパスワードを設定
- PTZ: ContinuousMove のみ受理 → **`ptz_mode=continuous` 必須**
- RTSP: `rtsp://{user}:{pass}@{host}:554/cam/realmonitor?channel=1&subtype=0`（**`-rtsp_transport tcp` 必須**）
- ONVIF ポート: 80
- `TAPO_STREAM_URL` でカスタム RTSP URL を指定（既定 `/stream1` では繋がらない）
- stream_url 設定時は RTSP 優先キャプチャ（ONVIF snapshot=640x480、RTSP=最大 2304x1296）

### 共通
- カメラ IP は固定推奨
- `.env`: `TAPO_CAMERA_HOST` / `TAPO_USERNAME` / `TAPO_PASSWORD` / `TAPO_STREAM_URL` / `TAPO_PTZ_MODE` / `TAPO_ONVIF_PORT`

### デバッグ
```bash
ffplay rtsp://username:password@192.168.1.xxx:554/stream1
```

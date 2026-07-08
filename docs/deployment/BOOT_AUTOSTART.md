# 开机自启动部署记录

本文记录 2K1000LA 与 2K0301/301 的 systemd 自启动编排。原则是每个功能只保留一个常驻实例，避免多个采集程序同时向同一 MQTT topic 发布数据。

完整系统启动顺序、网页入口、语音/视觉/301 排障步骤见 [`FULL_SYSTEM_STARTUP_RUNBOOK.md`](FULL_SYSTEM_STARTUP_RUNBOOK.md)。

## 2K1000LA

已部署服务：

| 服务名 | 作用 |
| --- | --- |
| `mosquitto.service` | MQTT Broker，监听 `1883` |
| `xylt-cloud-client.service` | 读取 301 MQTT 数据，写入 `runtime/latest_evaluate_response.json`，并上传 SafeCloud |
| `xylt-vision.service` | USB 摄像头实时预览、定时/按需抓拍、云端/本地视觉模式 |
| `xylt-hmi.service` | Qt HMI；语音助手由 Qt 自动拉起 |

当前环境文件：

```bash
/etc/xylt/2k1000la.env
```

关键配置：

```bash
SAFECLOUD_BASE_URL=http://192.168.43.5:8010
XYLT_REPO_ROOT=/home/xylt/xylt
XYLT_ARCHIVE_DIR=/media/xylt/0403-0201/xylt_vision_archive
XYLT_HMI_GEOMETRY=780x450+10+10
VOICE_AUTOSTART=true
VOICE_AUTORESTART=true
VOICE_WAKE_REQUIRED=true
VOICE_TTS_MODE=baidu
```

常用命令：

```bash
sudo systemctl status xylt-cloud-client.service
sudo systemctl status xylt-vision.service
sudo systemctl status xylt-hmi.service

sudo journalctl -u xylt-cloud-client.service -f
sudo journalctl -u xylt-vision.service -f
sudo journalctl -u xylt-hmi.service -f

sudo systemctl restart xylt-cloud-client.service xylt-vision.service xylt-hmi.service
```

如现场网络变化，优先修改 `SAFECLOUD_BASE_URL`，然后重启：

```bash
sudo nano /etc/xylt/2k1000la.env
sudo systemctl restart xylt-cloud-client.service xylt-vision.service
```

## 2K0301/301

已部署服务：

| 服务名 | 作用 |
| --- | --- |
| `xylt-301-main.service` | 当前 301 传感器采集、风险计算、执行器控制、MQTT 上报程序 |

当前运行程序：

```bash
/home/root/main
```

注意：不要同时启动 `/root/xylt_301_main_nopaho` 和 `/home/root/main`。两者会向同一 MQTT topic 发布数据，导致 Qt/Web 状态在在线和离线之间跳变。

常用命令：

```bash
systemctl status xylt-301-main.service
journalctl -u xylt-301-main.service -f
systemctl restart xylt-301-main.service
```

301 原始 MQTT 检查可在 2K1000LA 上执行：

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -q 1 -v -t 'device/board_2k0301/#'
```

## 回滚

2K1000LA：

```bash
sudo systemctl disable --now xylt-cloud-client.service xylt-vision.service xylt-hmi.service
```

301：

```bash
systemctl disable --now xylt-301-main.service
```

# SafeCloud 云端原型

SafeCloud 是本项目的云端服务原型，负责设备管理、遥测接收、历史数据存储、阈值报警、控制命令下发、Dashboard 数据聚合，以及通过 analyzer 进行多 LLM 安全分析。

当前云端服务不直接接 GPIO、I2C、SPI 或传感器驱动，只接收端侧标准化后的 JSON。

## 功能

- 设备新增、查询和状态更新。
- 动态 `metrics` 遥测数据上传。
- SQLite 存储设备、遥测、报警和命令。
- 简单阈值报警。
- 控制命令创建、设备轮询和执行结果回传。
- Dashboard Summary 接口和静态 Web 大屏。
- `POST /api/evaluate`：调用 `modules/analyzer`，返回统一安全状态。

## 启动

安装依赖：

```bash
cd safecloud
python -m pip install -r requirements.txt
```

本机调试：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

给龙芯板访问时需要监听局域网地址：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## UDP 自动发现

比赛现场网络经常变化时，可以同时启动 UDP discovery responder：

```bash
cd safecloud
python discovery_responder.py --bind-host 0.0.0.0 --discovery-port 8011 --service-port 8010
```

板端 `app_2k1000la/cloud_client.py` 会广播 `SAFECLOUD_DISCOVER`，收到回复后自动得到类似：

```json
{
  "service": "SafeCloud",
  "base_url": "http://192.168.43.5:8010"
}
```

成功后地址会缓存在板端 `~/.xylt_safecloud.json`，换网络后会自动重新发现。

或使用脚本：

```bash
SAFECLOUD_HOST=0.0.0.0 SAFECLOUD_PORT=8000 ../scripts/run/run_safecloud.sh
```

发现服务脚本：

```bash
SAFECLOUD_PORT=8010 SAFECLOUD_DISCOVERY_PORT=8011 ../scripts/run/run_safecloud_discovery.sh
```

启动后访问：

- 健康检查：`http://127.0.0.1:8000/health`
- Swagger API：`http://127.0.0.1:8000/docs`
- Web 大屏：`http://127.0.0.1:8000/dashboard`

## Analyzer 评估接口

Mock 模式：

```bash
curl -X POST http://127.0.0.1:8000/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device_001",
    "metrics": {
      "temperature": 72.5,
      "humidity": 61.0,
      "gas": 0.25,
      "vibration": 1.82,
      "current": 2.3
    },
    "include_debug": true
  }'
```

真实 LLM 单模型调试：

```bash
curl -X POST http://127.0.0.1:8000/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "device_001",
    "metrics": {
      "temperature": 72.5,
      "humidity": 61.0,
      "gas": 0.25,
      "vibration": 1.82,
      "current": 2.3
    },
    "use_real_llm": true,
    "force_model": "deepseek",
    "include_debug": true
  }'
```

如果开启真实 LLM，需要在运行 SafeCloud 的进程环境中配置 analyzer 所需 API Key，或提供 `modules/analyzer/.env`。真实密钥不要提交到 git。

## 板端调用方式

假设 Windows/云端主机局域网 IP 为 `192.168.14.20`：

```bash
python3 - <<'PY'
import json
import urllib.request

payload = {
    "device_id": "board_2k1000la",
    "metrics": {
        "temperature": 86.0,
        "humidity": 60.0,
        "gas": 0.32,
        "vibration": 2.8,
        "current": 4.2,
    },
    "use_real_llm": False,
    "include_debug": True,
}
req = urllib.request.Request(
    "http://192.168.14.20:8000/api/evaluate",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
print(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
PY
```

## 测试

```bash
PYTHONPATH=safecloud python -m pytest safecloud/tests
python -m pytest modules/analyzer/tests
```

## 文档

- `docs/cloud_architecture.md`：云端架构设计。
- `docs/api_contract.md`：HTTP API 合约。
- `docs/database_schema.md`：数据库结构。
- `docs/mqtt_topics.md`：MQTT Topic 预留。
- `docs/hardware_integration_guide.md`：真实硬件接入指南。
- `docs/development_plan.md`：后续开发计划。

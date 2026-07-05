# 大模型调用与多模型协同分析模块

本模块是嵌赛项目的“LLM Model Pool + Intelligent Router”最小可运行版本，当前默认使用 Mock 模型跑通完整流程：

```text
SensorData/SystemState
  -> RuleEngine
  -> TaskClassifier
  -> ModelRouter
  -> MultiLLMAnalyzer(Mock)
  -> JudgeModel
  -> SafetyGuard
  -> runtime/system_status.json
```

真实 DeepSeek、Kimi、智谱、豆包、通义千问客户端已保留占位类和环境变量入口，但本阶段不发起真实网络请求，也不把 API Key 写入代码。

## 运行

从仓库根目录执行：

```bash
python modules/analyzer/src/main.py
```

输出文件：

```text
modules/analyzer/runtime/system_status.json
```

也可以传入自定义数据：

```bash
python modules/analyzer/src/main.py --input-json "{\"device_id\":\"device_002\",\"temperature\":80,\"humidity\":50,\"gas\":0.2,\"vibration\":1.0,\"current\":2.0,\"cloud_connected\":true,\"sensor_online\":true}"
```

## 测试

```bash
python -m pytest modules/analyzer/tests
```

如果没有 pytest，可先安装：

```bash
python -m pip install -r modules/analyzer/requirements.txt
```

## 报警等级

- `0`：正常
- `1`：预警
- `2`：报警

安全原则：大模型和裁判模型不能把 RuleEngine 的报警等级降级。

# 大模型调用与多模型协同分析模块

本模块是“LLM Model Pool + Intelligent Router”的最小可运行版本。传感器数据当前使用 mock/模拟输入，安全动作仍以本地 RuleEngine 和 SafetyGuard 兜底。

```text
SensorData/SystemState
  -> RuleEngine
  -> TaskClassifier
  -> ModelRouter
  -> MultiLLMAnalyzer(real LLM or mock fallback)
  -> JudgeModel
  -> SafetyGuard
  -> runtime/system_status.json
```

## 默认运行

默认不访问真实云端 API，方便离线开发和板端验证：

```bash
python modules/analyzer/src/main.py
```

传入模拟数据：

```bash
python modules/analyzer/src/main.py --input-json "{\"device_id\":\"device_002\",\"temperature\":80,\"humidity\":50,\"gas\":0.2,\"vibration\":1.0,\"current\":2.0,\"cloud_connected\":true,\"sensor_online\":true}"
```

输出文件：

```text
modules/analyzer/runtime/system_status.json
```

## 真实 API 调用

复制示例环境文件并填入自己的密钥：

```bash
cp modules/analyzer/.env.example modules/analyzer/.env
```

`modules/analyzer/.env` 已被仓库忽略，不要提交真实 API Key。启用真实调用：

```bash
python modules/analyzer/src/main.py --use-real-llm --force-model deepseek --print-debug
```

也可以用环境变量开启：

```bash
export ANALYZER_USE_REAL_LLM=true
python modules/analyzer/src/main.py --force-model qwen --print-debug
```

支持的 `--force-model`：

```text
deepseek / kimi / zhipu / doubao / qwen / mock
```

不指定 `--force-model` 时，路由器会根据任务类型选择模型：预警默认单模型，报警默认多模型仲裁。

## 环境变量

需要配置的变量见 `.env.example`。当前客户端使用 OpenAI 兼容的 Chat Completions 请求格式：

```text
DEEPSEEK_API_KEY / DEEPSEEK_API_URL / DEEPSEEK_MODEL
KIMI_API_KEY / KIMI_API_URL / KIMI_MODEL
ZHIPU_API_KEY / ZHIPU_API_URL / ZHIPU_MODEL
DOUBAO_API_KEY / DOUBAO_API_URL / DOUBAO_MODEL
QWEN_API_KEY / QWEN_API_URL / QWEN_MODEL
```

`ANALYZER_LLM_TIMEOUT` 可设置请求超时时间，默认 30 秒。

## 回退策略

- `ANALYZER_USE_REAL_LLM` 未开启时，全部使用 mock。
- 密钥、URL 或模型名缺失时，该 provider 自动回退 mock。
- HTTP、网络、JSON 解析失败时，该 provider 自动回退 mock，并在 `_debug.model_results[].error` 中记录原因。
- SafetyGuard 会保证云端模型不能降低本地规则判定出的报警等级。

## 龙芯板端联调记录

已在龙芯 2K1000LA 开发板上完成 analyzer 真实 API 调用验证：

- 板端路径：`/home/xylt/xylt/modules/analyzer`
- Python：3.7.3
- Mock 主流程：通过
- DeepSeek、Kimi、智谱、豆包、通义单模型真实调用：通过
- 报警场景自动路由 `deepseek + zhipu + qwen` 多模型仲裁：通过
- 最终报警等级保持 `alarm_level=2`，`need_voice_alert=true`，`need_cloud_upload=true`

## 测试

```bash
python -m pip install -r modules/analyzer/requirements.txt
python -m pytest modules/analyzer/tests
```

## 常见问题

- 返回 `已回退 mock`：检查 `ANALYZER_USE_REAL_LLM=true`、API Key、URL、模型名和网络。
- 返回 HTTP 401/403：通常是密钥、权限或模型服务未开通。
- 返回模型不存在：确认供应商控制台里的模型 ID 与 `.env` 一致。
- 输出不是 JSON：当前 prompt 已要求 JSON；若某模型仍返回解释文本，会自动回退 mock，可先用 `--force-model` 单独调试该模型。

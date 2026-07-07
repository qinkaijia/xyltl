# firmware_2k301

2K0301 采集与执行控制程序目录。

当前仅保留工程框架：

- `src/`：源文件。
- `include/`：头文件。
- `tests/`：单元测试。
- `CMakeLists.txt`：CMake 入口。

后续实现传感器采集、三色灯、蜂鸣器、TB6612 电机控制和本地安全兜底逻辑。

## 联调接口文档

2K0301 固件开发请先阅读：

- `docs/integration/2k0301_firmware_handoff.md`：约定 2K0301 与 2K1000LA 的 Wi-Fi + MQTT 通信、上行传感器包、下行执行命令、ACK、心跳和验收标准。

# 2K0301 当前运行与联调记录

更新时间：2026-07-08。

本文记录 2K0301 与 2K1000LA / 云端链路的当前真实状态，便于后续继续联调时不用重新摸网络和构建细节。

## 当前网络

| 节点 | 地址 | 登录 | 当前用途 |
| --- | --- | --- | --- |
| Windows 开发机 | 手机热点网段 | 本机 | 保存源码与文档，不直接在板端改源码 |
| Linux VM | `192.168.242.129` | `jia / 123456` | 交叉编译 2K0301 工程 |
| 龙芯 2K1000LA | `192.168.43.36` | `xylt / 123456` | Mosquitto Broker、Qt HMI、语音与云端通信 |
| 龙芯 2K0301 | `192.168.43.40` | `root / 123456` | 运行真实 301 C++ 传感器/MQTT 程序 |

2K0301 和 2K1000LA 当前在同一 `192.168.43.0/24` 手机热点网段内。

## MQTT Topic

当前真实链路使用以下 topic：

```text
device/board_2k0301/sensor
device/board_2k0301/heartbeat
device/board_2k0301/ack
device/board_2k0301/error
device/board_2k0301/command
```

注意：不要单独改回早期 `device/2k0301/...`，除非 301、2K1000LA、SafeCloud、测试脚本同步修改。

## 301 当前运行状态

301 上当前运行的是真实 C++ 主程序，不再是 mock bridge：

```text
/root/xylt_301_main_nopaho
```

启动命令：

```bash
XYLT_MQTT_TOOL_DIR=/root/xylt_mqtt_tools \
LD_LIBRARY_PATH=/root/xylt_mqtt_tools \
nohup /root/xylt_301_main_nopaho \
  >/tmp/xylt_301_main.out 2>/tmp/xylt_301_main.err &
echo $! > /tmp/xylt_301_main.pid
```

查看状态：

```bash
cat /tmp/xylt_301_main.pid
ps -ef | grep -E 'xylt_301_main_nopaho|mosquitto_sub' | grep -v grep
tail -n 80 /tmp/xylt_301_main.out
tail -n 80 /tmp/xylt_301_main.err
```

停止程序：

```bash
kill "$(cat /tmp/xylt_301_main.pid)" 2>/dev/null || true
```

301 上保留了 MQTT 工具目录：

```text
/root/xylt_mqtt_tools/
  mosquitto_pub
  mosquitto_sub
  libmosquitto.so.1
  xylt_301_mqtt_mock.sh
```

真实 C++ 程序的 MQTT 模块已去掉 Paho 依赖，运行时通过上述 `mosquitto_pub/sub` 工具发布与订阅。`xylt_301_mqtt_mock.sh` 仅作为回退调试工具，当前已停用。

## 编译方案

Windows 源码目录：

```text
D:\xylt\Loongson_2K300_301_LIB
```

Linux VM 构建目录：

```bash
cd ~/xylt_301/Loongson_2K300_301_LIB/main
./build.sh
```

本次对 301 工程做了两类改动：

1. `libraries/app/lq_mqtt.*`：移除 `MQTTClient.h/libpaho-mqtt3c`，改为调用板端 `mosquitto_pub/sub`。
2. `main/CMakeLists.txt` 与入口头文件：只编译传感器采集、I2C/GPIO/ADC、信号处理和 MQTT 所需文件，不再把 example、camera、OpenCV、NCNN 链接进主程序。

轻量版二进制依赖检查结果：

```text
NEEDED libpthread.so.0
NEEDED libstdc++.so.6
NEEDED libm.so.6
NEEDED libgcc_s.so.1
NEEDED libc.so.6
```

也就是说当前运行版本不再需要 OpenCV、NCNN、Paho MQTT C。

## 已验证结果

2026-07-08 已完成真实 301 程序联调：

1. 301 程序启动成功，并连接 `192.168.43.36:1883`。
2. 301 启动命令订阅子进程：

```text
/root/xylt_mqtt_tools/mosquitto_sub -h 192.168.43.36 -p 1883 -q 1 -t device/board_2k0301/command
```

3. 2K1000LA 侧订阅收到真实传感器上报：

```text
device/board_2k0301/sensor {"type":"sensor_packet","seq":8,"payload":{"device_id":"board_2k0301","timestamp":"2026-07-07 18:01:22","temperature":26.3,"humidity":39.0,"tvoc":0,"eco2":400,"mq3_value":0.002,"flame_detected":false,"risk_score":0}}
device/board_2k0301/heartbeat {"type":"heartbeat","seq":5,"device_id":"board_2k0301","uptime_ms":19000,"sensor_online":true,"actuator_online":true,"error_flags":[]}
```

4. 2K1000LA 下发命令，301 返回 ACK：

```bash
mosquitto_pub -h 127.0.0.1 -q 1 \
  -t 'device/board_2k0301/command' \
  -m '{"type":"command","seq":2301,"command":"fan_control","params":{"state":"off","speed":0,"duration_ms":1000}}'
```

收到：

```text
device/board_2k0301/ack {"type":"ack","seq":2301,"ok":true,"message":"fan_control off (未接硬件,命令已记录)"}
```

## 当前硬件观测

真实程序启动日志显示：

```text
SHT30 已连接，温度约 26.3~27.2℃，湿度约 39~41%RH
SGP30 初始化完成，eCO2/TVOC 读数在变化；湿度补偿写入仍有 I2C 失败提示
MQ-3 ADC 读取偶发 timeout，当前上报 mq3_value 约 0.02~0.06
火焰检测 false
risk_score 0
```

这些不影响 MQTT 链路验证，但后续接真实传感器稳定性时需要继续检查 SGP30 湿度补偿写入路径、I2C 可靠性和 ADC 通道。

## 后续建议

1. 保持当前真实 301 程序运行，做 30 分钟以上 MQTT 稳定性测试。
2. 观察 `/tmp/xylt_301_main.err` 中 SGP30 I2C 与 ADC timeout 是否持续出现。
3. 用 2K1000LA 的 `cloud_client.py --sensor-source 2k0301` 再跑一次云端评估闭环。
4. 若后续要恢复 mock，只在真实程序停止后启动 `/root/xylt_mqtt_tools/xylt_301_mqtt_mock.sh`，避免两个 301 数据源同时上报。

#ifndef __LQ_MQTT_HPP__
#define __LQ_MQTT_HPP__

#include <string>
#include <functional>
#include <MQTTClient.h>

/****************************************************************************************************
 * @brief   MQTT 通信模块 (基于 Eclipse Paho MQTT C)
 * @note    封装 2K0301 ↔ 2K1000LA 的 MQTT 通信，支持:
 *          - 连接/重连 MQTT Broker
 *          - 发布传感器数据 / 心跳 / ACK / 错误
 *          - 订阅并回调控制命令
 *
 * 配置:
 *   broker_ip   = 2K1000LA 的 IP 地址
 *   device_id   = 本机设备 ID, 默认 "board_2k0301"
 ****************************************************************************************************/

/* 默认配置 */
#define MQTT_DEFAULT_BROKER      "192.168.43.1"   /* 2K1000LA MQTT Broker IP */
#define MQTT_DEFAULT_PORT        1883
#define MQTT_DEFAULT_DEVICE_ID   "board_2k0301"
#define MQTT_QOS                 1
#define MQTT_TIMEOUT_MS          3000
#define MQTT_KEEPALIVE_S         10

/* MQTT Topic 模板 */
#define TOPIC_SENSOR    "device/%s/sensor"
#define TOPIC_HEARTBEAT "device/%s/heartbeat"
#define TOPIC_ACK       "device/%s/ack"
#define TOPIC_ERROR     "device/%s/error"
#define TOPIC_COMMAND   "device/%s/command"

/* 命令类型 */
enum MqttCommand {
    CMD_NONE = 0,
    CMD_FAN_CONTROL,
    CMD_BUZZER_CONTROL,
    CMD_ALARM_LIGHT,
    CMD_DEVICE_RESET,
    CMD_UNKNOWN
};

/* 解析后的命令参数 */
struct CommandParams {
    MqttCommand cmd;
    int    seq;            /* 命令序列号 (用于ACK) */
    /* fan_control */
    bool   fan_on;         int fan_speed;    int fan_duration_ms;
    /* buzzer_control */
    bool   buzzer_on;      char buzzer_pattern[16]; int buzzer_duration_ms;
    /* alarm_light */
    char   light_color[8]; char light_mode[8]; int light_duration_ms;
    /* device_reset */
    char   reset_target[32];
    /* 原始 JSON */
    char   raw_json[512];
};

/* 命令回调: 返回要发回的 ACK 消息 (由调用者填充) */
typedef std::function<void(const CommandParams &cmd, bool *exec_ok, char *ack_msg, size_t ack_size)> MqttCmdCallback;

/****************************************************************************************************
 * @brief   MQTT 通信管理类
 ****************************************************************************************************/
class lq_mqtt
{
public:
    /********************************************************************************
     * @brief   构造函数
     * @param   broker_ip : MQTT Broker IP (2K1000LA 地址)
     * @param   port      : MQTT 端口, 默认 1883
     * @param   device_id : 设备 ID
     ********************************************************************************/
    lq_mqtt(const char *broker_ip = MQTT_DEFAULT_BROKER,
            int port = MQTT_DEFAULT_PORT,
            const char *device_id = MQTT_DEFAULT_DEVICE_ID);
    ~lq_mqtt();

public:
    /********************************************************************************
     * @brief   连接到 MQTT Broker
     * @return  成功返回 true
     ********************************************************************************/
    bool connect(void);

    /********************************************************************************
     * @brief   断开连接
     ********************************************************************************/
    void disconnect(void);

    /********************************************************************************
     * @brief   检查是否已连接
     ********************************************************************************/
    bool is_connected(void) const { return _connected; }

    /********************************************************************************
     * @brief   获取运行时长 (秒)
     ********************************************************************************/
    long uptime_sec(void) const { return (long)(time(NULL) - _start_time); }

    /********************************************************************************
     * @brief   主循环调用: 处理接收消息 (每次约 100ms)
     *          必须在主循环中定期调用
     ********************************************************************************/
    void spin(void);

    /********************************************************************************
     * @brief   设置命令回调
     ********************************************************************************/
    void set_command_callback(MqttCmdCallback cb) { _cmd_callback = cb; }

public:
    /* ── 发布接口 ── */

    /********************************************************************************
     * @brief   发布传感器数据
     * @param   json : 完整的 JSON payload 字符串
     * @return  成功返回 true
     ********************************************************************************/
    bool publish_sensor(const char *json);

    /********************************************************************************
     * @brief   发布心跳
     * @param   seq, uptime_ms, sensor_ok, actuator_ok, error_flags
     * @return  成功返回 true
     ********************************************************************************/
    bool publish_heartbeat(int seq, long uptime_ms, bool sensor_ok,
                           bool actuator_ok, const char *error_flags);

    /********************************************************************************
     * @brief   发布 ACK
     * @param   seq    : 对应命令的序列号
     * @param   ok     : 执行是否成功
     * @param   message: 附加信息
     * @return  成功返回 true
     ********************************************************************************/
    bool publish_ack(int seq, bool ok, const char *message);

    /********************************************************************************
     * @brief   发布错误
     * @param   seq, error_code, message
     * @return  成功返回 true
     ********************************************************************************/
    bool publish_error(int seq, const char *error_code, const char *message);

private:
    /* 构造 topic 字符串 */
    void make_topic(char *buf, size_t n, const char *fmt);

    /* 发布 JSON 消息 */
    bool publish_json(const char *topic, const char *json);

    /* MQTT 消息到达回调 (静态) */
    static int  _on_message(void *ctx, char *topic, int tlen, MQTTClient_message *msg);

private:
    MQTTClient       _client;
    std::string      _broker_ip;
    int              _port;
    std::string      _device_id;
    bool             _connected;

    char             _topic_sensor[64];
    char             _topic_heartbeat[64];
    char             _topic_ack[64];
    char             _topic_error[64];
    char             _topic_command[64];

    MqttCmdCallback  _cmd_callback;

    /* 心跳计数器 */
    int              _hb_seq;
    time_t           _start_time;
};

#endif

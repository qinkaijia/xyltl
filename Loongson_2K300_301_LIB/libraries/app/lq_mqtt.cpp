/********************************************************************************
 * @file    lq_mqtt.cpp
 * @brief   MQTT 通信模块实现 (基于 Eclipse Paho MQTT C 同步客户端)
 * @note    参见通信技术文档.agent.md 的 Topic 和消息格式约定
 ********************************************************************************/

#include "lq_mqtt.hpp"
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <time.h>

/* JSON 格式化辅助宏 */
#define FMT_SENSOR \
    "{\"type\":\"sensor_packet\",\"seq\":%d,\"payload\":%s}"

#define FMT_HEARTBEAT \
    "{\"type\":\"heartbeat\",\"seq\":%d,\"device_id\":\"%s\"," \
    "\"uptime_ms\":%ld,\"sensor_online\":%s,\"actuator_online\":%s," \
    "\"error_flags\":[%s]}"

#define FMT_ACK \
    "{\"type\":\"ack\",\"seq\":%d,\"ok\":%s,\"message\":\"%s\"}"

#define FMT_ERROR \
    "{\"type\":\"error\",\"seq\":%d,\"device_id\":\"%s\"," \
    "\"error_code\":\"%s\",\"message\":\"%s\"}"

/********************************************************************************
 * @brief   构造函数
 ********************************************************************************/
lq_mqtt::lq_mqtt(const char *broker_ip, int port, const char *device_id)
    : _broker_ip(broker_ip), _port(port), _device_id(device_id),
      _connected(false), _cmd_callback(nullptr), _hb_seq(0)
{
    _start_time = time(NULL);

    make_topic(_topic_sensor,    sizeof(_topic_sensor),    TOPIC_SENSOR);
    make_topic(_topic_heartbeat, sizeof(_topic_heartbeat), TOPIC_HEARTBEAT);
    make_topic(_topic_ack,       sizeof(_topic_ack),       TOPIC_ACK);
    make_topic(_topic_error,     sizeof(_topic_error),     TOPIC_ERROR);
    make_topic(_topic_command,   sizeof(_topic_command),   TOPIC_COMMAND);

    MQTTClient_create(&_client, (std::string("tcp://") + _broker_ip + ":" +
                       std::to_string(_port)).c_str(),
                       _device_id.c_str(), MQTTCLIENT_PERSISTENCE_NONE, NULL);
    MQTTClient_setCallbacks(_client, this, NULL, _on_message, NULL);
}

/********************************************************************************
 * @brief   析构函数
 ********************************************************************************/
lq_mqtt::~lq_mqtt()
{
    disconnect();
    MQTTClient_destroy(&_client);
}

/********************************************************************************
 * @brief   连接到 MQTT Broker
 ********************************************************************************/
bool lq_mqtt::connect(void)
{
    MQTTClient_connectOptions opts = MQTTClient_connectOptions_initializer;
    opts.keepAliveInterval = MQTT_KEEPALIVE_S;
    opts.cleansession = 1;
    opts.connectTimeout = MQTT_TIMEOUT_MS / 1000;
    opts.retryInterval = 3000;  /* 断线重试间隔: 3s */

    int rc = MQTTClient_connect(_client, &opts);
    if (rc != MQTTCLIENT_SUCCESS) {
        fprintf(stderr, "[MQTT] 连接 Broker %s:%d 失败, rc=%d\n",
                _broker_ip.c_str(), _port, rc);
        _connected = false;
        return false;
    }

    /* 订阅命令 topic */
    rc = MQTTClient_subscribe(_client, _topic_command, MQTT_QOS);
    if (rc != MQTTCLIENT_SUCCESS) {
        fprintf(stderr, "[MQTT] 订阅 %s 失败, rc=%d\n", _topic_command, rc);
        MQTTClient_disconnect(_client, MQTT_TIMEOUT_MS);
        _connected = false;
        return false;
    }

    _connected = true;
    _start_time = time(NULL);
    printf("[MQTT] 已连接 Broker %s:%d, 设备ID=%s\n",
           _broker_ip.c_str(), _port, _device_id.c_str());
    return true;
}

/********************************************************************************
 * @brief   断开连接
 ********************************************************************************/
void lq_mqtt::disconnect(void)
{
    if (_connected) {
        MQTTClient_unsubscribe(_client, _topic_command);
        MQTTClient_disconnect(_client, MQTT_TIMEOUT_MS);
        _connected = false;
    }
}

/********************************************************************************
 * @brief   主循环调用: 处理接收
 ********************************************************************************/
void lq_mqtt::spin(void)
{
    if (!_connected) return;
    /* 非阻塞接收, timeout 100ms */
    MQTTClient_message *msg = NULL;
    char *topic = NULL;
    int tlen = 0;
    int rc = MQTTClient_receive(_client, &topic, &tlen, &msg, 100);
    if (rc == MQTTCLIENT_SUCCESS && msg) {
        _on_message(this, topic, tlen, msg);
        MQTTClient_freeMessage(&msg);
        MQTTClient_free(topic);
    } else if (rc != MQTTCLIENT_SUCCESS && rc != MQTTCLIENT_SSL_NOT_SUPPORTED) {
        /* 可能断连了 */
    }
}

/********************************************************************************
 * @brief   发布传感器数据
 ********************************************************************************/
bool lq_mqtt::publish_sensor(const char *json)
{
    char buf[2048];
    snprintf(buf, sizeof(buf), FMT_SENSOR, _hb_seq++, json);
    return publish_json(_topic_sensor, buf);
}

/********************************************************************************
 * @brief   发布心跳
 ********************************************************************************/
bool lq_mqtt::publish_heartbeat(int seq, long uptime_ms, bool sensor_ok,
                                 bool actuator_ok, const char *error_flags)
{
    char buf[512];
    snprintf(buf, sizeof(buf), FMT_HEARTBEAT, seq, _device_id.c_str(),
             uptime_ms,
             sensor_ok ? "true" : "false",
             actuator_ok ? "true" : "false",
             error_flags ? error_flags : "");
    return publish_json(_topic_heartbeat, buf);
}

/********************************************************************************
 * @brief   发布 ACK
 ********************************************************************************/
bool lq_mqtt::publish_ack(int seq, bool ok, const char *message)
{
    char buf[512];
    snprintf(buf, sizeof(buf), FMT_ACK, seq, ok ? "true" : "false", message);
    return publish_json(_topic_ack, buf);
}

/********************************************************************************
 * @brief   发布错误
 ********************************************************************************/
bool lq_mqtt::publish_error(int seq, const char *error_code, const char *message)
{
    char buf[512];
    snprintf(buf, sizeof(buf), FMT_ERROR, seq, _device_id.c_str(),
             error_code, message);
    return publish_json(_topic_error, buf);
}

/********************************************************************************
 * @brief   构造 topic 字符串
 ********************************************************************************/
void lq_mqtt::make_topic(char *buf, size_t n, const char *fmt)
{
    snprintf(buf, n, fmt, _device_id.c_str());
}

/********************************************************************************
 * @brief   发布 JSON 消息到指定 topic
 ********************************************************************************/
bool lq_mqtt::publish_json(const char *topic, const char *json)
{
    if (!_connected) return false;

    MQTTClient_message msg = MQTTClient_message_initializer;
    msg.payload = (void*)json;
    msg.payloadlen = (int)strlen(json);
    msg.qos = MQTT_QOS;
    msg.retained = 0;

    MQTTClient_deliveryToken token;
    int rc = MQTTClient_publishMessage(_client, topic, &msg, &token);
    if (rc != MQTTCLIENT_SUCCESS) {
        fprintf(stderr, "[MQTT] publish to %s 失败, rc=%d\n", topic, rc);
        return false;
    }
    MQTTClient_waitForCompletion(_client, token, MQTT_TIMEOUT_MS);
    return true;
}

/********************************************************************************
 * @brief   消息到达回调 (接收命令)
 ********************************************************************************/
int lq_mqtt::_on_message(void *ctx, char *topic, int tlen, MQTTClient_message *msg)
{
    lq_mqtt *self = (lq_mqtt*)ctx;
    if (!self || !msg || !self->_cmd_callback) return 0;

    char *payload = (char*)malloc(msg->payloadlen + 1);
    if (!payload) return 0;
    memcpy(payload, msg->payload, msg->payloadlen);
    payload[msg->payloadlen] = '\0';

    CommandParams cmd;
    memset(&cmd, 0, sizeof(cmd));
    cmd.cmd = CMD_UNKNOWN;
    strncpy(cmd.raw_json, payload, sizeof(cmd.raw_json) - 1);

    /* 简易 JSON 解析 (不用完整 JSON 库, 用 sscanf) */
    /* 解析 type, seq, command */
    char type[32] = {0}, command[32] = {0};
    sscanf(payload, "{\"type\":\"%31[^\"]\",\"seq\":%d,\"command\":\"%31[^\"]\"",
           type, &cmd.seq, command);

    /* 解析 params 子对象 */
    char params_block[512] = {0};
    const char *p = strstr(payload, "\"params\":{");
    if (p) {
        p += 10;  /* skip "params":{ */
        const char *end = strchr(p, '}');
        if (end && (end - p < (int)sizeof(params_block) - 1)) {
            memcpy(params_block, p, end - p);
        }
    }

    /* 根据 command 解析具体参数 */
    if (strcmp(command, "fan_control") == 0) {
        cmd.cmd = CMD_FAN_CONTROL;
        char state[8] = {0};
        sscanf(params_block, "\"state\":\"%7[^\"]\",\"speed\":%d,\"duration_ms\":%d",
               state, &cmd.fan_speed, &cmd.fan_duration_ms);
        cmd.fan_on = (strcmp(state, "on") == 0);
    } else if (strcmp(command, "buzzer_control") == 0) {
        cmd.cmd = CMD_BUZZER_CONTROL;
        char state[8] = {0};
        sscanf(params_block, "\"state\":\"%7[^\"]\",\"pattern\":\"%15[^\"]\",\"duration_ms\":%d",
               state, cmd.buzzer_pattern, &cmd.buzzer_duration_ms);
        cmd.buzzer_on = (strcmp(state, "on") == 0);
    } else if (strcmp(command, "alarm_light") == 0) {
        cmd.cmd = CMD_ALARM_LIGHT;
        sscanf(params_block, "\"color\":\"%7[^\"]\",\"mode\":\"%7[^\"]\",\"duration_ms\":%d",
               cmd.light_color, cmd.light_mode, &cmd.light_duration_ms);
    } else if (strcmp(command, "device_reset") == 0) {
        cmd.cmd = CMD_DEVICE_RESET;
        sscanf(params_block, "\"target\":\"%31[^\"]\"", cmd.reset_target);
    }

    /* 调用回调 */
    bool exec_ok = false;
    char ack_msg[128] = {0};
    self->_cmd_callback(cmd, &exec_ok, ack_msg, sizeof(ack_msg));

    /* 自动发送 ACK */
    self->publish_ack(cmd.seq, exec_ok, ack_msg[0] ? ack_msg :
                      (exec_ok ? "executed" : "rejected"));

    free(payload);
    return 1;
}

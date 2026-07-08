#ifndef __LQ_MQTT_HPP__
#define __LQ_MQTT_HPP__

#include <atomic>
#include <ctime>
#include <functional>
#include <mutex>
#include <string>
#include <thread>

/* Default MQTT configuration. */
#define MQTT_DEFAULT_BROKER      "192.168.43.36"
#define MQTT_DEFAULT_PORT        1883
#define MQTT_DEFAULT_DEVICE_ID   "board_2k0301"
#define MQTT_QOS                 1
#define MQTT_TIMEOUT_MS          3000
#define MQTT_KEEPALIVE_S         10

/* MQTT topic templates. */
#define TOPIC_SENSOR    "device/%s/sensor"
#define TOPIC_HEARTBEAT "device/%s/heartbeat"
#define TOPIC_ACK       "device/%s/ack"
#define TOPIC_ERROR     "device/%s/error"
#define TOPIC_COMMAND   "device/%s/command"

enum MqttCommand {
    CMD_NONE = 0,
    CMD_FAN_CONTROL,
    CMD_BUZZER_CONTROL,
    CMD_ALARM_LIGHT,
    CMD_DEVICE_RESET,
    CMD_UNKNOWN
};

struct CommandParams {
    MqttCommand cmd;
    int    seq;
    bool   fan_on;         int fan_speed;    int fan_duration_ms;
    bool   buzzer_on;      char buzzer_pattern[16]; int buzzer_duration_ms;
    char   light_color[8]; char light_mode[8]; int light_duration_ms;
    char   reset_target[32];
    char   raw_json[512];
};

typedef std::function<void(const CommandParams &cmd, bool *exec_ok, char *ack_msg, size_t ack_size)> MqttCmdCallback;

class lq_mqtt
{
public:
    lq_mqtt(const char *broker_ip = MQTT_DEFAULT_BROKER,
            int port = MQTT_DEFAULT_PORT,
            const char *device_id = MQTT_DEFAULT_DEVICE_ID);
    ~lq_mqtt();

    bool connect(void);
    void disconnect(void);
    bool is_connected(void) const { return _connected; }
    long uptime_sec(void) const { return (long)(time(NULL) - _start_time); }

    /* Commands are handled by a subscriber thread; spin is kept for API compatibility. */
    void spin(void);

    void set_command_callback(MqttCmdCallback cb) { _cmd_callback = cb; }

    bool publish_sensor(const char *json);
    bool publish_heartbeat(int seq, long uptime_ms, bool sensor_ok,
                           bool actuator_ok, const char *error_flags);
    bool publish_ack(int seq, bool ok, const char *message);
    bool publish_error(int seq, const char *error_code, const char *message);

private:
    void make_topic(char *buf, size_t n, const char *fmt);
    bool publish_json(const char *topic, const char *json);
    void subscriber_loop(void);
    bool start_subscriber_process(void);
    void stop_subscriber_process(void);
    void handle_command_payload(const char *payload);

private:
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
    int              _hb_seq;
    time_t           _start_time;

    std::string      _tool_dir;
    std::string      _pub_path;
    std::string      _sub_path;
    std::thread      _sub_thread;
    std::atomic<bool> _stop_subscriber;
    std::mutex       _process_mutex;
    int              _sub_pid;
    int              _sub_fd;
};

#endif

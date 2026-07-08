#include "lq_mqtt.hpp"

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

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

static bool file_exists(const std::string &path)
{
    return access(path.c_str(), X_OK) == 0;
}

static std::string select_tool(const std::string &tool_dir, const char *name)
{
    std::string path = tool_dir + "/" + name;
    if (file_exists(path)) {
        return path;
    }
    return name;
}

static void setup_tool_env(const std::string &tool_dir)
{
    const char *old_env = getenv("LD_LIBRARY_PATH");
    std::string value = tool_dir;
    if (old_env && old_env[0]) {
        value += ":";
        value += old_env;
    }
    setenv("LD_LIBRARY_PATH", value.c_str(), 1);
}

static bool read_line_from_fd(int fd, std::string &line)
{
    line.clear();
    char c = '\0';
    while (true) {
        ssize_t n = read(fd, &c, 1);
        if (n == 1) {
            if (c == '\n') {
                return true;
            }
            if (c != '\r') {
                line.push_back(c);
            }
            continue;
        }
        if (n == 0) {
            return !line.empty();
        }
        if (errno == EINTR) {
            continue;
        }
        return false;
    }
}

lq_mqtt::lq_mqtt(const char *broker_ip, int port, const char *device_id)
    : _broker_ip(broker_ip), _port(port), _device_id(device_id),
      _connected(false), _cmd_callback(nullptr), _hb_seq(0),
      _stop_subscriber(false), _sub_pid(-1), _sub_fd(-1)
{
    _start_time = time(NULL);

    const char *tool_dir_env = getenv("XYLT_MQTT_TOOL_DIR");
    _tool_dir = (tool_dir_env && tool_dir_env[0]) ? tool_dir_env : "/root/xylt_mqtt_tools";
    _pub_path = select_tool(_tool_dir, "mosquitto_pub");
    _sub_path = select_tool(_tool_dir, "mosquitto_sub");

    make_topic(_topic_sensor,    sizeof(_topic_sensor),    TOPIC_SENSOR);
    make_topic(_topic_heartbeat, sizeof(_topic_heartbeat), TOPIC_HEARTBEAT);
    make_topic(_topic_ack,       sizeof(_topic_ack),       TOPIC_ACK);
    make_topic(_topic_error,     sizeof(_topic_error),     TOPIC_ERROR);
    make_topic(_topic_command,   sizeof(_topic_command),   TOPIC_COMMAND);
}

lq_mqtt::~lq_mqtt()
{
    disconnect();
}

bool lq_mqtt::connect(void)
{
    setup_tool_env(_tool_dir);

    if (!file_exists(_pub_path) && _pub_path.find('/') != std::string::npos) {
        fprintf(stderr, "[MQTT] missing mosquitto_pub: %s\n", _pub_path.c_str());
        _connected = false;
        return false;
    }
    if (!file_exists(_sub_path) && _sub_path.find('/') != std::string::npos) {
        fprintf(stderr, "[MQTT] missing mosquitto_sub: %s\n", _sub_path.c_str());
        _connected = false;
        return false;
    }

    _stop_subscriber = false;
    _connected = true;
    _start_time = time(NULL);
    _sub_thread = std::thread(&lq_mqtt::subscriber_loop, this);

    printf("[MQTT] mosquitto tools enabled, broker=%s:%d, device_id=%s\n",
           _broker_ip.c_str(), _port, _device_id.c_str());
    printf("[MQTT] command topic: %s\n", _topic_command);
    return true;
}

void lq_mqtt::disconnect(void)
{
    if (!_connected && !_sub_thread.joinable()) {
        return;
    }

    _stop_subscriber = true;
    stop_subscriber_process();

    if (_sub_thread.joinable()) {
        _sub_thread.join();
    }
    _connected = false;
}

void lq_mqtt::spin(void)
{
    /* Command handling is done by subscriber_loop(). */
}

bool lq_mqtt::publish_sensor(const char *json)
{
    char buf[2048];
    snprintf(buf, sizeof(buf), FMT_SENSOR, _hb_seq++, json);
    return publish_json(_topic_sensor, buf);
}

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

bool lq_mqtt::publish_ack(int seq, bool ok, const char *message)
{
    char buf[512];
    snprintf(buf, sizeof(buf), FMT_ACK, seq, ok ? "true" : "false", message ? message : "");
    return publish_json(_topic_ack, buf);
}

bool lq_mqtt::publish_error(int seq, const char *error_code, const char *message)
{
    char buf[512];
    snprintf(buf, sizeof(buf), FMT_ERROR, seq, _device_id.c_str(),
             error_code ? error_code : "UNKNOWN", message ? message : "");
    return publish_json(_topic_error, buf);
}

void lq_mqtt::make_topic(char *buf, size_t n, const char *fmt)
{
    snprintf(buf, n, fmt, _device_id.c_str());
}

bool lq_mqtt::publish_json(const char *topic, const char *json)
{
    if (!_connected || !topic || !json) {
        return false;
    }

    pid_t pid = fork();
    if (pid < 0) {
        fprintf(stderr, "[MQTT] fork mosquitto_pub failed: %s\n", strerror(errno));
        return false;
    }

    if (pid == 0) {
        setup_tool_env(_tool_dir);
        char port_buf[16];
        snprintf(port_buf, sizeof(port_buf), "%d", _port);
        execl(_pub_path.c_str(), _pub_path.c_str(),
              "-h", _broker_ip.c_str(),
              "-p", port_buf,
              "-q", "1",
              "-t", topic,
              "-m", json,
              (char*)NULL);
        execlp(_pub_path.c_str(), _pub_path.c_str(),
               "-h", _broker_ip.c_str(),
               "-p", port_buf,
               "-q", "1",
               "-t", topic,
               "-m", json,
               (char*)NULL);
        _exit(127);
    }

    int status = 0;
    if (waitpid(pid, &status, 0) < 0) {
        fprintf(stderr, "[MQTT] wait mosquitto_pub failed: %s\n", strerror(errno));
        return false;
    }

    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        fprintf(stderr, "[MQTT] publish to %s failed, status=%d\n", topic, status);
        return false;
    }
    return true;
}

void lq_mqtt::subscriber_loop(void)
{
    while (!_stop_subscriber) {
        if (!start_subscriber_process()) {
            sleep(1);
            continue;
        }

        while (!_stop_subscriber) {
            int fd = -1;
            {
                std::lock_guard<std::mutex> lock(_process_mutex);
                fd = _sub_fd;
            }
            if (fd < 0) {
                break;
            }

            std::string line;
            if (!read_line_from_fd(fd, line)) {
                break;
            }
            if (!line.empty()) {
                handle_command_payload(line.c_str());
            }
        }

        stop_subscriber_process();
        if (!_stop_subscriber) {
            sleep(1);
        }
    }
}

bool lq_mqtt::start_subscriber_process(void)
{
    int fds[2];
    if (pipe(fds) != 0) {
        fprintf(stderr, "[MQTT] pipe failed: %s\n", strerror(errno));
        return false;
    }

    pid_t pid = fork();
    if (pid < 0) {
        close(fds[0]);
        close(fds[1]);
        fprintf(stderr, "[MQTT] fork mosquitto_sub failed: %s\n", strerror(errno));
        return false;
    }

    if (pid == 0) {
        close(fds[0]);
        dup2(fds[1], STDOUT_FILENO);
        close(fds[1]);
        int devnull = open("/dev/null", O_WRONLY);
        if (devnull >= 0) {
            dup2(devnull, STDERR_FILENO);
            close(devnull);
        }
        setup_tool_env(_tool_dir);
        char port_buf[16];
        snprintf(port_buf, sizeof(port_buf), "%d", _port);
        execl(_sub_path.c_str(), _sub_path.c_str(),
              "-h", _broker_ip.c_str(),
              "-p", port_buf,
              "-q", "1",
              "-t", _topic_command,
              (char*)NULL);
        execlp(_sub_path.c_str(), _sub_path.c_str(),
               "-h", _broker_ip.c_str(),
               "-p", port_buf,
               "-q", "1",
               "-t", _topic_command,
               (char*)NULL);
        _exit(127);
    }

    close(fds[1]);
    {
        std::lock_guard<std::mutex> lock(_process_mutex);
        _sub_pid = (int)pid;
        _sub_fd = fds[0];
    }
    return true;
}

void lq_mqtt::stop_subscriber_process(void)
{
    int pid = -1;
    int fd = -1;
    {
        std::lock_guard<std::mutex> lock(_process_mutex);
        pid = _sub_pid;
        fd = _sub_fd;
        _sub_pid = -1;
        _sub_fd = -1;
    }

    if (fd >= 0) {
        close(fd);
    }
    if (pid > 0) {
        kill((pid_t)pid, SIGTERM);
        waitpid((pid_t)pid, NULL, 0);
    }
}

void lq_mqtt::handle_command_payload(const char *payload)
{
    if (!payload || !_cmd_callback) {
        return;
    }

    CommandParams cmd;
    memset(&cmd, 0, sizeof(cmd));
    cmd.cmd = CMD_UNKNOWN;
    strncpy(cmd.raw_json, payload, sizeof(cmd.raw_json) - 1);

    char type[32] = {0};
    char command[32] = {0};
    sscanf(payload, "{\"type\":\"%31[^\"]\",\"seq\":%d,\"command\":\"%31[^\"]\"",
           type, &cmd.seq, command);

    char params_block[512] = {0};
    const char *p = strstr(payload, "\"params\":{");
    if (p) {
        p += 10;
        const char *end = strchr(p, '}');
        if (end && (end - p < (int)sizeof(params_block) - 1)) {
            memcpy(params_block, p, end - p);
        }
    }

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

    bool exec_ok = false;
    char ack_msg[128] = {0};
    _cmd_callback(cmd, &exec_ok, ack_msg, sizeof(ack_msg));

    publish_ack(cmd.seq, exec_ok, ack_msg[0] ? ack_msg : (exec_ok ? "executed" : "rejected"));
}

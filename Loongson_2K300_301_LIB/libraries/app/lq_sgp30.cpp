/********************************************************************************
 * @file    lq_sgp30.cpp
 * @brief   SGP30 空气质量传感器驱动实现
 * @note    基于 ls_fs_i2c 硬件 I2C 通信
 *
 * 数据手册参考: Sensirion SGP30 Datasheet
 *   - eCO2: 等效 CO2 浓度，范围 400~60000 ppm
 *   - TVOC: 总挥发性有机物，范围 0~60000 ppb
 *   - 上电后需 ~15s 初始化时间
 *   - 必须以 ≥1Hz 频率周期读取以维持内部基线算法
 ********************************************************************************/

#include "lq_sgp30.hpp"
#include <fstream>
#include <cmath>
#include <time.h>

/********************************************************************************
 * @brief   CRC-8 校验 (多项式 0x31, 初值 0xFF)
 ********************************************************************************/
uint8_t lq_sgp30::crc8(const uint8_t *data, int len)
{
    uint8_t crc = 0xFF;
    for (int i = 0; i < len; i++) {
        crc ^= data[i];
        for (int b = 0; b < 8; b++) {
            crc = (crc & 0x80) ? ((crc << 1) ^ 0x31) : (crc << 1);
        }
    }
    return crc;
}

/********************************************************************************
 * @brief   计算绝对湿度 (g/m³)
 *          使用 August-Roche-Magnus 近似公式
 ********************************************************************************/
float lq_sgp30::calc_absolute_humidity(float temperature, float humidity)
{
    /* 饱和水汽压 (hPa) */
    float es = 6.112f * expf((17.67f * temperature) / (temperature + 243.5f));
    /* 实际水汽压 (hPa) */
    float ea = es * humidity / 100.0f;
    /* 绝对湿度 (g/m³) */
    return (216.7f * ea) / (temperature + 273.15f);
}

/********************************************************************************
 * @brief   发送命令并读取响应（SGP30 标准通信模式）
 * @param   cmd     : 16位命令码
 * @param   cmd_ms  : 命令后等待时间
 * @param   buf     : 读取缓冲区
 * @param   buf_len : 读取字节数
 * @return  成功返回 0
 ********************************************************************************/
int lq_sgp30::cmd_read(uint16_t cmd, int cmd_ms, uint8_t *buf, int buf_len)
{
    if (!initialized || !i2c_dev) return -1;

    /* 发送命令 */
    uint8_t cmd_buf[2];
    cmd_buf[0] = (cmd >> 8) & 0xFF;
    cmd_buf[1] = cmd & 0xFF;

    if (i2c_dev->i2c_write_bytes(cmd_buf, 2) != 2) {
        fprintf(stderr, "[SGP30] 发送命令 0x%04X 失败\n", cmd);
        return -1;
    }

    /* 等待传感器处理 */
    if (cmd_ms > 0) usleep(cmd_ms * 1000);

    /* 读取响应 */
    if (buf_len > 0) {
        ssize_t ret = i2c_dev->i2c_read_bytes(buf, buf_len);
        if (ret != buf_len) {
            fprintf(stderr, "[SGP30] 读取响应失败: 期望%d字节, 实际%zd字节\n", buf_len, ret);
            return -1;
        }
    }
    return 0;
}

/********************************************************************************
 * @brief   构造函数
 ********************************************************************************/
lq_sgp30::lq_sgp30(std::string _bus, uint8_t _addr)
    : i2c_addr(_addr), initialized(false), init_time(0),
      baseline_eco2(0), baseline_tvoc(0), has_baseline(false)
{
    i2c_dev = new ls_fs_i2c(_bus, _addr);
    if (i2c_dev && i2c_dev->get_i2c_fd() >= 0) {
        initialized = true;
    } else {
        fprintf(stderr, "[SGP30] I2C 初始化失败: bus=%s, addr=0x%02X\n",
                _bus.c_str(), _addr);
    }
}

/********************************************************************************
 * @brief   析构函数 — 退出前保存基线
 ********************************************************************************/
lq_sgp30::~lq_sgp30()
{
    if (initialized) {
        save_baseline();
    }
    if (i2c_dev) {
        delete i2c_dev;
        i2c_dev = nullptr;
    }
}

/********************************************************************************
 * @brief   初始化传感器
 * @note    发送 init_air_quality 命令，加载已保存基线
 * @return  成功返回 0
 ********************************************************************************/
int lq_sgp30::init(void)
{
    if (!initialized) return -1;

    printf("[SGP30] 正在初始化空气质量传感器...\n");

    /* 发送 init_air_quality 命令 (无响应数据) */
    if (cmd_read(SGP30_CMD_INIT_AIR_QUALITY, 0, nullptr, 0) != 0) {
        fprintf(stderr, "[SGP30] init_air_quality 失败\n");
        return -1;
    }

    /* 记录初始化时间 */
    init_time = time(NULL);

    /* 尝试加载基线 */
    load_baseline();

    printf("[SGP30] 初始化完成 (预热约需 %d 秒)\n",
           has_baseline ? SGP30_INIT_AIR_QUALITY_MS / 1000 : SGP30_INIT_WARMUP_MS / 1000);
    return 0;
}

/********************************************************************************
 * @brief   检查传感器是否预热完成
 ********************************************************************************/
bool lq_sgp30::is_ready(void)
{
    if (!initialized || init_time == 0) return false;
    int elapsed = time(NULL) - init_time;
    int needed = has_baseline ? (SGP30_INIT_AIR_QUALITY_MS / 1000)
                              : (SGP30_INIT_WARMUP_MS / 1000);
    return elapsed >= needed;
}

/********************************************************************************
 * @brief   读取 eCO2 和 TVOC 浓度
 * @param   eco2 : [out] eCO2 (ppm)
 * @param   tvoc : [out] TVOC (ppb)
 * @return  成功返回 0
 ********************************************************************************/
int lq_sgp30::read(uint16_t *eco2, uint16_t *tvoc)
{
    if (!initialized || !i2c_dev || !eco2 || !tvoc) return -1;

    /* 发送测量命令，等待 12ms */
    uint8_t buf[6] = {0};
    if (cmd_read(SGP30_CMD_MEASURE_AIR_QUALITY, 12, buf, 6) != 0)
        return -1;

    /* CRC 校验 */
    if (crc8(buf, 2) != buf[2]) {
        fprintf(stderr, "[SGP30] eCO2 CRC 校验失败\n");
        return -1;
    }
    if (crc8(buf + 3, 2) != buf[5]) {
        fprintf(stderr, "[SGP30] TVOC CRC 校验失败\n");
        return -1;
    }

    *eco2 = ((uint16_t)buf[0] << 8) | buf[1];
    *tvoc = ((uint16_t)buf[3] << 8) | buf[4];

    return 0;
}

/********************************************************************************
 * @brief   读取原始信号
 ********************************************************************************/
int lq_sgp30::read_raw(uint16_t *ethanol_raw, uint16_t *h2_raw)
{
    if (!initialized || !i2c_dev) return -1;

    uint8_t buf[6] = {0};
    if (cmd_read(SGP30_CMD_MEASURE_RAW, 25, buf, 6) != 0)
        return -1;

    if (crc8(buf, 2) != buf[2] || crc8(buf + 3, 2) != buf[5])
        return -1;

    *ethanol_raw = ((uint16_t)buf[0] << 8) | buf[1];
    *h2_raw      = ((uint16_t)buf[3] << 8) | buf[4];
    return 0;
}

/********************************************************************************
 * @brief   设置湿度补偿
 *          需要先用 SHT30 测得温湿度，再调用此函数设置补偿值
 ********************************************************************************/
int lq_sgp30::set_humidity_compensation(float temperature, float humidity)
{
    if (!initialized || !i2c_dev) return -1;

    float abs_hum = calc_absolute_humidity(temperature, humidity);

    /* 绝对湿度转换为定点数 (g/m³ → ticks, 1 tick = 1/512 g/m³) */
    uint16_t ticks = (uint16_t)(abs_hum * 512.0f);
    if (ticks > 65535) ticks = 65535;

    uint8_t buf[3];
    buf[0] = (ticks >> 8) & 0xFF;
    buf[1] = ticks & 0xFF;
    buf[2] = crc8(buf, 2);

    if (cmd_read(SGP30_CMD_SET_HUMIDITY, 10, nullptr, 0) != 0)
        return -1;

    /* 写入补偿值 */
    ssize_t ret = i2c_dev->i2c_write_bytes(buf, 3);
    if (ret != 3) {
        fprintf(stderr, "[SGP30] 写入湿度补偿失败\n");
        return -1;
    }

    return 0;
}

/********************************************************************************
 * @brief   保存基线到文件
 ********************************************************************************/
int lq_sgp30::save_baseline(void)
{
    if (!initialized || !is_ready()) return -1;

    /* 读取当前基线 */
    uint8_t buf[6] = {0};
    if (cmd_read(SGP30_CMD_GET_BASELINE, 10, buf, 6) != 0)
        return -1;

    if (crc8(buf, 2) != buf[2] || crc8(buf + 3, 2) != buf[5])
        return -1;

    uint16_t eco2_base = ((uint16_t)buf[0] << 8) | buf[1];
    uint16_t tvoc_base = ((uint16_t)buf[3] << 8) | buf[4];

    /* 只保存有效的基线 (非初始值) */
    if (eco2_base == 0 && tvoc_base == 0) return 0;

    std::ofstream f(SGP30_BASELINE_FILE);
    if (!f.is_open()) {
        fprintf(stderr, "[SGP30] 无法打开基线文件: %s\n", SGP30_BASELINE_FILE);
        return -1;
    }
    f << eco2_base << " " << tvoc_base << std::endl;
    f.close();

    printf("[SGP30] 基线已保存: eCO2=%u, TVOC=%u\n", eco2_base, tvoc_base);
    return 0;
}

/********************************************************************************
 * @brief   从文件加载基线
 ********************************************************************************/
int lq_sgp30::load_baseline(void)
{
    std::ifstream f(SGP30_BASELINE_FILE);
    if (!f.is_open()) {
        printf("[SGP30] 无已保存基线，将进行完整预热\n");
        return -1;
    }

    f >> baseline_eco2 >> baseline_tvoc;
    f.close();

    if (baseline_eco2 == 0 || baseline_tvoc == 0) {
        has_baseline = false;
        return -1;
    }

    has_baseline = true;

    /* 设置基线 */
    uint8_t buf[6];
    buf[0] = (baseline_eco2 >> 8) & 0xFF;
    buf[1] = baseline_eco2 & 0xFF;
    buf[2] = crc8(buf, 2);
    buf[3] = (baseline_tvoc >> 8) & 0xFF;
    buf[4] = baseline_tvoc & 0xFF;
    buf[5] = crc8(buf + 3, 2);

    if (cmd_read(SGP30_CMD_SET_BASELINE, 10, nullptr, 0) != 0)
        return -1;

    ssize_t ret = i2c_dev->i2c_write_bytes(buf, 6);
    if (ret == 6) {
        printf("[SGP30] 已加载基线: eCO2=%u, TVOC=%u\n", baseline_eco2, baseline_tvoc);
        return 0;
    }

    has_baseline = false;
    return -1;
}

/********************************************************************************
 * @brief   自检
 ********************************************************************************/
int lq_sgp30::self_test(void)
{
    if (!initialized || !i2c_dev) return -1;

    uint8_t buf[3] = {0};
    if (cmd_read(SGP30_CMD_MEASURE_TEST, 220, buf, 3) != 0)
        return -1;

    if (crc8(buf, 2) != buf[2]) {
        fprintf(stderr, "[SGP30] 自检 CRC 失败\n");
        return -1;
    }

    uint16_t result = ((uint16_t)buf[0] << 8) | buf[1];
    if (result == 0xD400) {
        printf("[SGP30] 自检通过 ✓\n");
        return 0;
    } else {
        fprintf(stderr, "[SGP30] 自检失败! 返回: 0x%04X\n", result);
        return -1;
    }
}

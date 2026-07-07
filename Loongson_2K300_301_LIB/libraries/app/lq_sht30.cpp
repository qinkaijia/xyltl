/********************************************************************************
 * @file    lq_sht30.cpp
 * @brief   SHT30 温湿度传感器驱动实现
 * @note    基于 ls_fs_i2c 硬件 I2C 通信，支持单次测量模式
 *
 * 数据手册参考: Sensirion SHT3x-DIS Datasheet
 *   - 温度公式: T[℃] = -45 + 175 × (S_T / (2^16 - 1))
 *   - 湿度公式: H[%]  = 100 × (S_RH / (2^16 - 1))
 *   - 每次测量返回 6 字节: [Temp_MSB, Temp_LSB, Temp_CRC, Hum_MSB, Hum_LSB, Hum_CRC]
 ********************************************************************************/

#include "lq_sht30.hpp"

/* 命令表 */
static const uint16_t CMD_TABLE[] = {
    0x2C06,     /* SHT30_REPEAT_HIGH   — 高重复性 */
    0x2C10,     /* SHT30_REPEAT_MEDIUM — 中重复性 */
    0x2400,     /* SHT30_REPEAT_LOW    — 低重复性 */
};

/********************************************************************************
 * @brief   CRC-8 校验实现（多项式 0x31, 初值 0xFF）
 * @param   data : 数据指针
 * @param   len  : 字节数
 * @return  计算出的 CRC 值
 ********************************************************************************/
uint8_t lq_sht30::crc8(const uint8_t *data, int len)
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
 * @brief   构造函数：初始化 I2C 设备
 * @param   _bus  : I2C 总线路径
 * @param   _addr : 从设备地址
 ********************************************************************************/
lq_sht30::lq_sht30(std::string _bus, uint8_t _addr)
    : i2c_addr(_addr), initialized(false)
{
    i2c_dev = new ls_fs_i2c(_bus, _addr);
    if (i2c_dev && i2c_dev->get_i2c_fd() >= 0) {
        initialized = true;
        /* 发送软复位确保传感器处于已知状态 */
        send_command(SHT30_CMD_SOFT_RESET);
        usleep(1000);  /* 复位后等待 1ms */
    } else {
        fprintf(stderr, "[SHT30] I2C 初始化失败: bus=%s, addr=0x%02X\n",
                _bus.c_str(), _addr);
    }
}

/********************************************************************************
 * @brief   析构函数
 ********************************************************************************/
lq_sht30::~lq_sht30()
{
    if (i2c_dev) {
        delete i2c_dev;
        i2c_dev = nullptr;
    }
}

/********************************************************************************
 * @brief   发送 16 位命令码
 * @param   cmd : 命令码
 * @return  成功返回 0
 ********************************************************************************/
int lq_sht30::send_command(uint16_t cmd)
{
    if (!initialized || !i2c_dev) return -1;
    uint8_t buf[2];
    buf[0] = (cmd >> 8) & 0xFF;
    buf[1] = cmd & 0xFF;
    ssize_t ret = i2c_dev->i2c_write_bytes(buf, 2);
    return (ret == 2) ? 0 : -1;
}

/********************************************************************************
 * @brief   单次温湿度测量
 * @param   temperature : [out] 温度 (℃)
 * @param   humidity    : [out] 相对湿度 (%RH)
 * @param   repeat      : 重复性 0=高 1=中 2=低
 * @return  成功返回 0，失败返回 -1
 ********************************************************************************/
int lq_sht30::read_sensor(float *temperature, float *humidity, uint8_t repeat)
{
    if (!initialized || !i2c_dev || !temperature || !humidity) return -1;

    if (repeat > 2) repeat = 0;

    /* 1. 发送测量命令 */
    if (send_command(CMD_TABLE[repeat]) != 0) {
        fprintf(stderr, "[SHT30] 发送测量命令失败\n");
        return -1;
    }

    /* 2. 等待测量完成: 高/中重复性 ~15ms, 低 ~5ms */
    int wait_ms = (repeat == SHT30_REPEAT_LOW) ? 5 : 15;
    usleep(wait_ms * 1000);

    /* 3. 读取 6 字节测量数据 */
    uint8_t buf[6] = {0};
    ssize_t ret = i2c_dev->i2c_read_bytes(buf, 6);
    if (ret != 6) {
        fprintf(stderr, "[SHT30] 读取数据失败: 期望6字节, 实际%zd字节\n", ret);
        return -1;
    }

    /* 4. CRC 校验 */
    if (crc8(buf, 2) != buf[2]) {
        fprintf(stderr, "[SHT30] 温度 CRC 校验失败\n");
        return -1;
    }
    if (crc8(buf + 3, 2) != buf[5]) {
        fprintf(stderr, "[SHT30] 湿度 CRC 校验失败\n");
        return -1;
    }

    /* 5. 计算物理量 */
    uint16_t t_raw = ((uint16_t)buf[0] << 8) | buf[1];
    uint16_t h_raw = ((uint16_t)buf[3] << 8) | buf[4];

    *temperature = -45.0f + 175.0f * ((float)t_raw / 65535.0f);
    *humidity    = 100.0f * ((float)h_raw / 65535.0f);

    /* 钳位湿度到 [0, 100] */
    if (*humidity > 100.0f) *humidity = 100.0f;
    if (*humidity < 0.0f)   *humidity = 0.0f;

    return 0;
}

/********************************************************************************
 * @brief   软复位传感器
 * @return  成功返回 0
 ********************************************************************************/
int lq_sht30::soft_reset(void)
{
    if (send_command(SHT30_CMD_SOFT_RESET) != 0) return -1;
    usleep(1000);
    return 0;
}

/********************************************************************************
 * @brief   读取状态寄存器
 * @param   status : [out] 16位状态字
 * @return  成功返回 0
 ********************************************************************************/
int lq_sht30::read_status(uint16_t *status)
{
    if (!initialized || !i2c_dev || !status) return -1;

    if (send_command(SHT30_CMD_STATUS) != 0) return -1;

    uint8_t buf[3] = {0};
    ssize_t ret = i2c_dev->i2c_read_bytes(buf, 3);
    if (ret != 3) return -1;

    if (crc8(buf, 2) != buf[2]) return -1;

    *status = ((uint16_t)buf[0] << 8) | buf[1];
    return 0;
}

/********************************************************************************
 * @brief   控制加热器
 * @param   enable : true 开启, false 关闭
 * @return  成功返回 0
 ********************************************************************************/
int lq_sht30::heater(bool enable)
{
    uint16_t cmd = enable ? SHT30_CMD_HEATER_ON : SHT30_CMD_HEATER_OFF;
    return send_command(cmd);
}

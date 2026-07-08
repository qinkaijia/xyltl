#ifndef __LQ_SHT30_HPP__
#define __LQ_SHT30_HPP__

#include "lq_fs_i2c.hpp"

/****************************************************************************************************
 * @brief   SHT30 温湿度传感器类，硬件 I2C 驱动
 * @note    使用 ls_fs_i2c 与传感器通信，支持单次测量模式
 ****************************************************************************************************/

/* SHT30 I2C 默认地址 (ADDR 引脚接 GND) */
#define SHT30_I2C_ADDR          ( 0x44 )

/* SHT30 单次测量命令 */
#define SHT30_CMD_SINGLE_H      ( 0x2C06 )  // 高重复性，时钟拉伸使能
#define SHT30_CMD_SINGLE_M      ( 0x2C10 )  // 中重复性，时钟拉伸使能
#define SHT30_CMD_SINGLE_L      ( 0x2400 )  // 低重复性，时钟拉伸禁用
#define SHT30_CMD_HEATER_ON     ( 0x306D )  // 开启加热器
#define SHT30_CMD_HEATER_OFF    ( 0x3066 )  // 关闭加热器
#define SHT30_CMD_STATUS        ( 0xF32D )  // 读取状态寄存器
#define SHT30_CMD_CLEAR_STATUS  ( 0x3041 )  // 清除状态寄存器
#define SHT30_CMD_SOFT_RESET    ( 0x30A2 )  // 软复位
#define SHT30_CMD_BREAK         ( 0x3093 )  // 停止周期测量

/* 测量模式 */
#define SHT30_REPEAT_HIGH       ( 0 )
#define SHT30_REPEAT_MEDIUM     ( 1 )
#define SHT30_REPEAT_LOW        ( 2 )

/* 默认总线 */
#define SHT30_DEFAULT_BUS       ( LS_I2C_BUS1 )

class lq_sht30
{
public:
    /********************************************************************************
     * @brief   构造函数：初始化 SHT30 传感器
     * @param   _bus  : I2C 总线路径，默认 /dev/i2c-5
     * @param   _addr : I2C 设备地址，默认 0x44
     ********************************************************************************/
    lq_sht30(std::string _bus = SHT30_DEFAULT_BUS, uint8_t _addr = SHT30_I2C_ADDR);
    ~lq_sht30();

public:
    /********************************************************************************
     * @brief   执行单次温湿度测量
     * @param   temperature : [out] 温度值 (℃)
     * @param   humidity    : [out] 相对湿度 (%RH)
     * @param   repeat      : 重复性等级 (0=高, 1=中, 2=低), 默认高
     * @return  成功返回 0，失败返回 -1
     ********************************************************************************/
    int read_sensor(float *temperature, float *humidity, uint8_t repeat = SHT30_REPEAT_HIGH);

    /********************************************************************************
     * @brief   软复位传感器
     * @return  成功返回 0
     ********************************************************************************/
    int soft_reset(void);

    /********************************************************************************
     * @brief   读取传感器状态寄存器
     * @param   status : [out] 16位状态字
     * @return  成功返回 0
     ********************************************************************************/
    int read_status(uint16_t *status);

    /********************************************************************************
     * @brief   控制芯片内部加热器（用于自检/除湿）
     * @param   enable : true 开启, false 关闭
     * @return  成功返回 0
     ********************************************************************************/
    int heater(bool enable);

private:
    /********************************************************************************
     * @brief   发送 16 位命令
     * @param   cmd : 命令码
     * @return  成功返回 0
     ********************************************************************************/
    int send_command(uint16_t cmd);

    /********************************************************************************
     * @brief   CRC-8 校验 (多项式 0x31, 初值 0xFF)
     * @param   data : 待校验数据
     * @param   len  : 数据长度
     * @return  CRC 值
     ********************************************************************************/
    static uint8_t crc8(const uint8_t *data, int len);

private:
    ls_fs_i2c  *i2c_dev;         // I2C 设备对象
    uint8_t     i2c_addr;        // I2C 从设备地址
    bool        initialized;     // 初始化状态
};

#endif

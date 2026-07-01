#ifndef SYSTEMSTATUS_H
#define SYSTEMSTATUS_H

#include <QString>
#include <QDateTime>

// ============================================================================
// SystemStatus —— 显示模块统一使用的系统状态快照
//
// 说明：
//   本结构体是“显示层内部”使用的数据模型，与 protocol/ 下的通信协议
//   (sensor_packet / risk_packet / judge_result) 解耦。
//   后续接入真实数据源时，由具体的 IDataProvider 实现负责把协议 JSON
//   转换成 SystemStatus，界面层无需关心数据来源。
// ============================================================================

// 状态等级：气体、振动、总体系统状态统一使用
enum StatusLevel {
    LEVEL_NORMAL  = 0,  // 正常（绿色）
    LEVEL_WARNING = 1,  // 预警（黄色/橙色）
    LEVEL_ALARM   = 2   // 报警（红色）
};

// 语音助手状态
enum VoiceState {
    VOICE_IDLE       = 0,  // 待唤醒
    VOICE_AWAKE      = 1,  // 已唤醒
    VOICE_LISTENING  = 2   // 识别中
};

// 系统状态快照：每次数据刷新对应一份完整快照
struct SystemStatus {
    double    temperature   = 0.0;    // 温度，单位 ℃
    double    humidity      = 0.0;    // 湿度，单位 %
    int       gasLevel      = LEVEL_NORMAL;   // 气体状态等级（见 StatusLevel）
    int       vibrationLevel= LEVEL_NORMAL;   // 振动状态等级（见 StatusLevel）
    bool      cloudConnected= true;   // 云端连接状态：true=已连接，false=已断开
    int       voiceState    = VOICE_IDLE;     // 语音助手状态（见 VoiceState）
    int       alarmLevel    = LEVEL_NORMAL;   // 总体系统状态等级（见 StatusLevel）
    QString   alarmMessage;           // 本次快照对应的报警/提示信息（可为空）
    QDateTime timestamp;              // 数据产生时间
};

// -------- 辅助函数：把枚举值转换为中文文本，供界面显示 --------

inline QString levelToText(int level)
{
    switch (level) {
    case LEVEL_NORMAL:  return QStringLiteral("正常");
    case LEVEL_WARNING: return QStringLiteral("预警");
    case LEVEL_ALARM:   return QStringLiteral("报警");
    default:            return QStringLiteral("未知");
    }
}

inline QString voiceStateToText(int state)
{
    switch (state) {
    case VOICE_IDLE:      return QStringLiteral("待唤醒");
    case VOICE_AWAKE:     return QStringLiteral("已唤醒");
    case VOICE_LISTENING: return QStringLiteral("识别中");
    default:              return QStringLiteral("未知");
    }
}

inline QString cloudStateToText(bool connected)
{
    return connected ? QStringLiteral("已连接") : QStringLiteral("已断开");
}

// 声明为 Qt 元类型，便于跨线程队列连接传递（供将来的线程化数据源使用）
Q_DECLARE_METATYPE(SystemStatus)

#endif // SYSTEMSTATUS_H

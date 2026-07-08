#ifndef SYSTEMSTATUS_H
#define SYSTEMSTATUS_H

#include <QDateTime>
#include <QString>

enum StatusLevel {
    LEVEL_NORMAL = 0,
    LEVEL_WARNING = 1,
    LEVEL_ALARM = 2
};

enum VoiceState {
    VOICE_IDLE = 0,
    VOICE_AWAKE = 1,
    VOICE_LISTENING = 2,
    VOICE_THINKING = 3,
    VOICE_EXECUTING = 4,
    VOICE_SPEAKING = 5,
    VOICE_ERROR = 6
};

struct SystemStatus {
    QString deviceId;
    double temperature = 0.0;
    double humidity = 0.0;
    double gasValue = 0.0;
    double vibrationValue = 0.0;
    double currentValue = 0.0;
    double tvoc = 0.0;
    double eco2 = 0.0;
    double mq3Value = 0.0;
    bool flameDetected = false;
    double riskScore = 0.0;
    int gasLevel = LEVEL_NORMAL;
    int vibrationLevel = LEVEL_NORMAL;
    int tvocLevel = LEVEL_NORMAL;
    int eco2Level = LEVEL_NORMAL;
    int mq3Level = LEVEL_NORMAL;
    int flameLevel = LEVEL_NORMAL;
    int riskLevel = LEVEL_NORMAL;
    bool cloudConnected = true;
    bool sensorOnline = true;
    bool actuatorOnline = true;
    int voiceState = VOICE_IDLE;
    int alarmLevel = LEVEL_NORMAL;
    QString statusText;
    QString alarmMessage;
    QString suggestion;
    QString voiceText;
    QString assistantStateText;
    QString assistantUserText;
    QString assistantReply;
    QString assistantIntent;
    QString assistantSafetyMessage;
    QString assistantExecuteMessage;
    QString assistantProvider;
    QString analysisMode;
    QString sensorSource;
    QString modelSource;
    QString modelDetails;
    int cloudLatencyMs = -1;
    QDateTime timestamp;
};

inline QString levelToText(int level)
{
    switch (level) {
    case LEVEL_NORMAL: return QStringLiteral("正常");
    case LEVEL_WARNING: return QStringLiteral("预警");
    case LEVEL_ALARM: return QStringLiteral("报警");
    default: return QStringLiteral("未知");
    }
}

inline QString voiceStateToText(int state)
{
    switch (state) {
    case VOICE_IDLE: return QStringLiteral("待唤醒");
    case VOICE_AWAKE: return QStringLiteral("已唤醒");
    case VOICE_LISTENING: return QStringLiteral("识别中");
    case VOICE_THINKING: return QStringLiteral("思考中");
    case VOICE_EXECUTING: return QStringLiteral("执行中");
    case VOICE_SPEAKING: return QStringLiteral("回复中");
    case VOICE_ERROR: return QStringLiteral("异常");
    default: return QStringLiteral("未知");
    }
}

inline QString cloudStateToText(bool connected)
{
    return connected ? QStringLiteral("已连接") : QStringLiteral("已断开");
}

Q_DECLARE_METATYPE(SystemStatus)

#endif // SYSTEMSTATUS_H

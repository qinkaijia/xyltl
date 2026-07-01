#include "MockDataProvider.h"

#include <QTimer>
#include <QRandomGenerator>
#include <algorithm>

// 刷新间隔：1 秒
static const int kRefreshIntervalMs = 1000;

// 把数值限制在 [lo, hi] 区间内
static double clampd(double v, double lo, double hi)
{
    return std::max(lo, std::min(hi, v));
}

MockDataProvider::MockDataProvider(QObject *parent)
    : IDataProvider(parent)
{
    m_timer = new QTimer(this);
    m_timer->setInterval(kRefreshIntervalMs);
    connect(m_timer, &QTimer::timeout, this, &MockDataProvider::generate);
}

MockDataProvider::~MockDataProvider() = default;

void MockDataProvider::start()
{
    if (!m_timer->isActive()) {
        m_timer->start();
    }
    // 启动时立即产生一份数据，避免界面停留在初始空值
    generate();
}

void MockDataProvider::stop()
{
    m_timer->stop();
}

void MockDataProvider::generate()
{
    QRandomGenerator *rng = QRandomGenerator::global();

    SystemStatus s;

    // ---- 温度：在上次基础上小幅波动，范围约束在 15~45 ℃ ----
    m_temperature += (rng->bounded(100) - 50) / 50.0;   // 约 ±1.0 ℃ 抖动
    m_temperature = clampd(m_temperature, 15.0, 45.0);
    s.temperature = m_temperature;

    // ---- 湿度：小幅波动，范围约束在 20~90 % ----
    m_humidity += (rng->bounded(100) - 50) / 25.0;      // 约 ±2 % 抖动
    m_humidity = clampd(m_humidity, 20.0, 90.0);
    s.humidity = m_humidity;

    // ---- 气体状态：大概率正常，偶尔预警/报警 ----
    int gasRoll = rng->bounded(100);
    if (gasRoll < 85)      s.gasLevel = LEVEL_NORMAL;
    else if (gasRoll < 96) s.gasLevel = LEVEL_WARNING;
    else                   s.gasLevel = LEVEL_ALARM;

    // ---- 振动状态：大概率正常，偶尔预警/报警 ----
    int vibRoll = rng->bounded(100);
    if (vibRoll < 88)      s.vibrationLevel = LEVEL_NORMAL;
    else if (vibRoll < 97) s.vibrationLevel = LEVEL_WARNING;
    else                   s.vibrationLevel = LEVEL_ALARM;

    // ---- 云端连接：偶尔断开再恢复（约 3% 概率翻转状态）----
    if (rng->bounded(100) < 3) {
        m_cloud = !m_cloud;
    }
    s.cloudConnected = m_cloud;

    // ---- 语音状态：在三种状态间随机切换 ----
    s.voiceState = rng->bounded(3);   // 0/1/2

    // ---- 总体系统状态：取气体与振动的较高等级 ----
    s.alarmLevel = std::max(s.gasLevel, s.vibrationLevel);

    // ---- 报警信息：仅在出现预警/报警时填写，供上层写入日志 ----
    if (s.gasLevel == LEVEL_ALARM) {
        s.alarmMessage = QStringLiteral("气体报警");
    } else if (s.vibrationLevel == LEVEL_ALARM) {
        s.alarmMessage = QStringLiteral("振动报警");
    } else if (s.gasLevel == LEVEL_WARNING) {
        s.alarmMessage = QStringLiteral("气体预警");
    } else if (s.vibrationLevel == LEVEL_WARNING) {
        s.alarmMessage = QStringLiteral("振动预警");
    } else {
        s.alarmMessage.clear();
    }

    s.timestamp = QDateTime::currentDateTime();

    emit statusUpdated(s);
}

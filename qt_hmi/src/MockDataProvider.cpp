#include "MockDataProvider.h"

#include <QRandomGenerator>
#include <QTimer>
#include <algorithm>

static const int kRefreshIntervalMs = 1000;

static double clampd(double value, double low, double high)
{
    return std::max(low, std::min(high, value));
}

static int levelFromHighThreshold(double value, double warning, double alarm)
{
    if (value >= alarm) {
        return LEVEL_ALARM;
    }
    if (value >= warning) {
        return LEVEL_WARNING;
    }
    return LEVEL_NORMAL;
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
    generate();
}

void MockDataProvider::stop()
{
    m_timer->stop();
}

void MockDataProvider::generate()
{
    QRandomGenerator *rng = QRandomGenerator::global();

    m_temperature += (rng->bounded(100) - 50) / 50.0;
    m_temperature = clampd(m_temperature, 15.0, 45.0);

    m_humidity += (rng->bounded(100) - 50) / 25.0;
    m_humidity = clampd(m_humidity, 20.0, 90.0);

    m_gas += (rng->bounded(100) - 48) / 2000.0;
    m_gas = clampd(m_gas, 0.05, 0.7);

    m_vibration += (rng->bounded(100) - 48) / 220.0;
    m_vibration = clampd(m_vibration, 0.2, 2.8);

    if (rng->bounded(100) < 3) {
        m_cloud = !m_cloud;
    }

    SystemStatus status;
    status.deviceId = QStringLiteral("mock_hmi");
    status.temperature = m_temperature;
    status.humidity = m_humidity;
    status.gasValue = m_gas;
    status.vibrationValue = m_vibration;
    status.currentValue = 1.8;
    status.gasLevel = levelFromHighThreshold(m_gas, 0.3, 0.6);
    status.vibrationLevel = levelFromHighThreshold(m_vibration, 1.5, 2.5);
    status.cloudConnected = m_cloud;
    status.voiceState = rng->bounded(3);
    status.alarmLevel = std::max(status.gasLevel, status.vibrationLevel);
    status.statusText = levelToText(status.alarmLevel);
    status.analysisMode = QStringLiteral("hmi_mock");
    status.timestamp = QDateTime::currentDateTime();

    if (status.gasLevel == LEVEL_ALARM) {
        status.alarmMessage = QStringLiteral("气体浓度达到报警阈值");
    } else if (status.vibrationLevel == LEVEL_ALARM) {
        status.alarmMessage = QStringLiteral("振动达到报警阈值");
    } else if (status.gasLevel == LEVEL_WARNING) {
        status.alarmMessage = QStringLiteral("气体浓度达到预警阈值");
    } else if (status.vibrationLevel == LEVEL_WARNING) {
        status.alarmMessage = QStringLiteral("振动达到预警阈值");
    }

    if (status.alarmLevel == LEVEL_NORMAL) {
        status.suggestion = QStringLiteral("保持常规监测");
        status.voiceText = QStringLiteral("当前设备运行正常。");
    } else {
        status.suggestion = QStringLiteral("请检查现场状态，重点关注异常指标。");
        status.voiceText = QStringLiteral("当前设备处于预警或报警状态，请检查现场。");
    }

    emit statusUpdated(status);
}

#include "MockDataProvider.h"

#include <QRandomGenerator>
#include <QTimer>
#include <algorithm>
#include <initializer_list>

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

    m_tvoc += (rng->bounded(100) - 45) * 6.0;
    m_tvoc = clampd(m_tvoc, 0.0, 2600.0);

    m_eco2 += (rng->bounded(100) - 45) * 8.0;
    m_eco2 = clampd(m_eco2, 400.0, 2400.0);

    m_mq3Value += (rng->bounded(100) - 48) / 500.0;
    m_mq3Value = clampd(m_mq3Value, 0.0, 0.9);

    if (rng->bounded(100) < 2) {
        m_flameDetected = !m_flameDetected;
    }

    const double gasScore = std::max({
        m_tvoc / 2000.0,
        (m_eco2 - 400.0) / 1600.0,
        m_mq3Value / 1.0,
        m_flameDetected ? 1.0 : 0.0,
    });
    m_gas = clampd(gasScore, 0.0, 1.0);
    m_vibration = 0.0;
    m_riskScore = clampd(m_gas * 100.0, 0.0, 100.0);

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
    status.tvoc = m_tvoc;
    status.eco2 = m_eco2;
    status.mq3Value = m_mq3Value;
    status.flameDetected = m_flameDetected;
    status.riskScore = m_riskScore;
    status.gasLevel = levelFromHighThreshold(m_gas, 0.3, 0.6);
    status.vibrationLevel = levelFromHighThreshold(m_vibration, 1.5, 2.5);
    status.tvocLevel = levelFromHighThreshold(m_tvoc, 600.0, 2000.0);
    status.eco2Level = levelFromHighThreshold(m_eco2, 1000.0, 2000.0);
    status.mq3Level = levelFromHighThreshold(m_mq3Value, 0.3, 0.8);
    status.flameLevel = m_flameDetected ? LEVEL_ALARM : LEVEL_NORMAL;
    status.riskLevel = levelFromHighThreshold(m_riskScore, 30.0, 60.0);
    status.cloudConnected = m_cloud;
    status.sensorOnline = true;
    status.actuatorOnline = true;
    status.voiceState = rng->bounded(3);
    status.alarmLevel = std::max({status.tvocLevel, status.eco2Level, status.mq3Level, status.flameLevel, status.riskLevel});
    status.statusText = levelToText(status.alarmLevel);
    status.analysisMode = QStringLiteral("hmi_mock");
    status.sensorSource = QStringLiteral("mock_2k0301");
    status.timestamp = QDateTime::currentDateTime();

    if (status.flameLevel == LEVEL_ALARM) {
        status.alarmMessage = QStringLiteral("火焰检测触发报警");
    } else if (status.riskLevel == LEVEL_ALARM) {
        status.alarmMessage = QStringLiteral("综合风险达到报警阈值");
    } else if (status.tvocLevel == LEVEL_ALARM || status.eco2Level == LEVEL_ALARM || status.mq3Level == LEVEL_ALARM) {
        status.alarmMessage = QStringLiteral("气体相关指标达到报警阈值");
    } else if (status.alarmLevel == LEVEL_WARNING) {
        status.alarmMessage = QStringLiteral("环境指标达到预警阈值");
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

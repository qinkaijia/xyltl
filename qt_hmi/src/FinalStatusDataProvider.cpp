#include "FinalStatusDataProvider.h"

#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTimer>

static const int kPollIntervalMs = 1000;

FinalStatusDataProvider::FinalStatusDataProvider(const QString &statusFile, QObject *parent)
    : IDataProvider(parent), m_statusFile(statusFile)
{
    m_timer = new QTimer(this);
    m_timer->setInterval(kPollIntervalMs);
    connect(m_timer, &QTimer::timeout, this, &FinalStatusDataProvider::poll);
}

FinalStatusDataProvider::~FinalStatusDataProvider() = default;

void FinalStatusDataProvider::start()
{
    if (!m_timer->isActive()) {
        m_timer->start();
    }
    poll();
}

void FinalStatusDataProvider::stop()
{
    m_timer->stop();
}

void FinalStatusDataProvider::poll()
{
    QFileInfo info(m_statusFile);
    if (!info.exists() || !info.isFile()) {
        return;
    }
    if (info.lastModified() == m_lastModified) {
        return;
    }

    SystemStatus status;
    if (loadStatus(&status)) {
        m_lastModified = info.lastModified();
        emit statusUpdated(status);
    }
}

bool FinalStatusDataProvider::loadStatus(SystemStatus *status)
{
    QFile file(m_statusFile);
    if (!file.open(QIODevice::ReadOnly)) {
        return false;
    }

    const QJsonDocument doc = QJsonDocument::fromJson(file.readAll());
    if (!doc.isObject()) {
        return false;
    }

    QJsonObject obj = doc.object();
    if (obj.contains(QStringLiteral("final_status")) && obj.value(QStringLiteral("final_status")).isObject()) {
        obj = obj.value(QStringLiteral("final_status")).toObject();
    }

    status->deviceId = obj.value(QStringLiteral("device_id")).toString();
    status->temperature = obj.value(QStringLiteral("temperature")).toDouble();
    status->humidity = obj.value(QStringLiteral("humidity")).toDouble();
    status->gasValue = obj.value(QStringLiteral("gas")).toDouble();
    status->vibrationValue = obj.value(QStringLiteral("vibration")).toDouble();
    status->currentValue = obj.value(QStringLiteral("current")).toDouble();
    status->alarmLevel = obj.value(QStringLiteral("alarm_level")).toInt(LEVEL_NORMAL);
    status->statusText = obj.value(QStringLiteral("status_text")).toString(levelToText(status->alarmLevel));
    status->cloudConnected = obj.value(QStringLiteral("cloud_connected")).toBool(true);
    status->alarmMessage = obj.value(QStringLiteral("reason")).toString();
    status->suggestion = obj.value(QStringLiteral("suggestion")).toString();
    status->voiceText = obj.value(QStringLiteral("voice_text")).toString();
    status->analysisMode = obj.value(QStringLiteral("analysis_mode")).toString();

    const QString timestampText = obj.value(QStringLiteral("timestamp")).toString();
    status->timestamp = QDateTime::fromString(timestampText, Qt::ISODate);
    if (!status->timestamp.isValid()) {
        status->timestamp = QDateTime::currentDateTime();
    }

    status->gasLevel = levelFromHighThreshold(status->gasValue, 0.3, 0.6);
    status->vibrationLevel = levelFromHighThreshold(status->vibrationValue, 1.5, 2.5);
    return true;
}

int FinalStatusDataProvider::levelFromHighThreshold(double value, double warning, double alarm)
{
    if (value >= alarm) {
        return LEVEL_ALARM;
    }
    if (value >= warning) {
        return LEVEL_WARNING;
    }
    return LEVEL_NORMAL;
}

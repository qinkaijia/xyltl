#include "StatusModel.h"
#include "IDataProvider.h"

StatusModel::StatusModel(QObject *parent)
    : QObject(parent)
{
}

void StatusModel::setProvider(IDataProvider *provider)
{
    // 断开旧数据源
    if (m_provider) {
        disconnect(m_provider, &IDataProvider::statusUpdated,
                   this, &StatusModel::onStatusUpdated);
    }

    m_provider = provider;

    // 连接新数据源
    if (m_provider) {
        connect(m_provider, &IDataProvider::statusUpdated,
                this, &StatusModel::onStatusUpdated);
    }
}

void StatusModel::onStatusUpdated(const SystemStatus &status)
{
    m_current = status;

    // 出现预警/报警时写入日志；同一条持续报警只记录一次，避免刷屏。
    const QString alarmSignature = QString::number(status.alarmLevel)
                                   + QStringLiteral("|")
                                   + status.alarmMessage;
    if (status.alarmLevel != LEVEL_NORMAL
        && !status.alarmMessage.isEmpty()
        && alarmSignature != m_lastAlarmSignature) {
        const QString line = status.timestamp.toString("HH:mm:ss")
                             + QStringLiteral("  ") + status.alarmMessage;
        m_alarmLog.append(line);
        m_lastAlarmSignature = alarmSignature;

        // 限制日志长度
        while (m_alarmLog.size() > kMaxLogLines) {
            m_alarmLog.removeFirst();
        }

        emit alarmLogged(line);
    } else if (status.alarmLevel == LEVEL_NORMAL) {
        m_lastAlarmSignature.clear();
    }

    emit statusChanged(status);
}

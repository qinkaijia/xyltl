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

    // 出现预警/报警时写入日志（正常状态不记录，避免刷屏）
    if (status.alarmLevel != LEVEL_NORMAL && !status.alarmMessage.isEmpty()) {
        const QString line = status.timestamp.toString("HH:mm:ss")
                             + QStringLiteral("  ") + status.alarmMessage;
        m_alarmLog.append(line);

        // 限制日志长度
        while (m_alarmLog.size() > kMaxLogLines) {
            m_alarmLog.removeFirst();
        }

        emit alarmLogged(line);
    }

    emit statusChanged(status);
}

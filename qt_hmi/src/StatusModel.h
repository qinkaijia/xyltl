#ifndef STATUSMODEL_H
#define STATUSMODEL_H

#include <QObject>
#include <QStringList>
#include "SystemStatus.h"

class IDataProvider;

// ============================================================================
// StatusModel —— 界面与数据源之间的中间模型
//
// 职责：
//   1. 订阅某个 IDataProvider 的 statusUpdated 信号；
//   2. 保存“当前最新状态”，供界面查询；
//   3. 维护报警日志历史（出现预警/报警时追加一条带时间戳的记录）；
//   4. 通过信号通知界面刷新，界面无需直接接触数据源。
//
// 这样即使后续更换数据源（Mock -> 真实传感器），界面代码保持不变。
// ============================================================================
class StatusModel : public QObject
{
    Q_OBJECT
public:
    explicit StatusModel(QObject *parent = nullptr);

    // 绑定数据源（可在运行期切换，例如从 Mock 切到真实数据源）
    void setProvider(IDataProvider *provider);

    const SystemStatus &current() const { return m_current; }
    const QStringList &alarmLog() const { return m_alarmLog; }

signals:
    // 每次收到新状态后发出，携带完整快照
    void statusChanged(const SystemStatus &status);

    // 新增一条报警日志时发出，携带已格式化好的日志文本
    void alarmLogged(const QString &line);

private slots:
    // 接收数据源推送的新状态
    void onStatusUpdated(const SystemStatus &status);

private:
    IDataProvider *m_provider = nullptr;   // 不拥有所有权
    SystemStatus   m_current;
    QStringList    m_alarmLog;

    static const int kMaxLogLines = 200;   // 日志最大保留条数，防止无限增长
};

#endif // STATUSMODEL_H

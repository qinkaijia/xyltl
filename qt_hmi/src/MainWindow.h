#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include "SystemStatus.h"

class QLabel;
class QFrame;
class QListWidget;
class StatusModel;

// ============================================================================
// MainWindow —— 智能工业环境监测系统 仪表盘主界面
//
// 纯 C++ 手写界面（不使用 .ui 文件），方便后续脚本/Agent 直接修改。
// 只依赖 StatusModel 提供的信号刷新，不直接接触任何数据源或硬件。
// ============================================================================
class MainWindow : public QMainWindow
{
    Q_OBJECT
public:
    explicit MainWindow(StatusModel *model, QWidget *parent = nullptr);

private slots:
    // 收到新状态，刷新所有卡片
    void onStatusChanged(const SystemStatus &status);
    // 收到新报警日志，追加到日志列表
    void onAlarmLogged(const QString &line);

private:
    // ---- 界面构建辅助 ----
    QWidget *buildCentral();                          // 组装中央控件
    QFrame  *createCard(const QString &title,         // 创建一张状态卡片
                        QLabel **valueLabelOut);
    // 根据状态等级设置某张卡片的配色（绿/黄/红）
    void applyLevelStyle(QFrame *card, QLabel *value, int level);

    StatusModel *m_model = nullptr;    // 不拥有所有权

    // ---- 卡片值标签，便于刷新 ----
    QFrame *m_tempCard   = nullptr;  QLabel *m_tempValue   = nullptr;
    QFrame *m_humiCard   = nullptr;  QLabel *m_humiValue   = nullptr;
    QFrame *m_sysCard    = nullptr;  QLabel *m_sysValue    = nullptr;
    QFrame *m_gasCard    = nullptr;  QLabel *m_gasValue    = nullptr;
    QFrame *m_vibCard    = nullptr;  QLabel *m_vibValue    = nullptr;
    QFrame *m_cloudCard  = nullptr;  QLabel *m_cloudValue  = nullptr;

    QLabel      *m_infoLabel   = nullptr;   // 中部状态信息/趋势占位
    QListWidget *m_alarmList   = nullptr;   // 报警日志列表
    QLabel      *m_bottomLabel = nullptr;   // 底部：语音助手 | 云端
};

#endif // MAINWINDOW_H

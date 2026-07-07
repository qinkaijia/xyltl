#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>

#include "SystemStatus.h"

class QLabel;
class QFrame;
class QListWidget;
class QPushButton;
class StatusModel;

class MainWindow : public QMainWindow
{
    Q_OBJECT
public:
    explicit MainWindow(StatusModel *model, bool compactMode = false, QWidget *parent = nullptr);

private slots:
    void onStatusChanged(const SystemStatus &status);
    void onAlarmLogged(const QString &line);
    void showModelDetails();

private:
    QWidget *buildCentral();
    QFrame *createCard(const QString &title, QLabel **valueLabelOut);
    void applyLevelStyle(QFrame *card, QLabel *value, int level);

    StatusModel *m_model = nullptr;
    bool m_compactMode = false;

    QFrame *m_tempCard = nullptr; QLabel *m_tempValue = nullptr;
    QFrame *m_humiCard = nullptr; QLabel *m_humiValue = nullptr;
    QFrame *m_sysCard = nullptr; QLabel *m_sysValue = nullptr;
    QFrame *m_gasCard = nullptr; QLabel *m_gasValue = nullptr;
    QFrame *m_vibCard = nullptr; QLabel *m_vibValue = nullptr;
    QFrame *m_cloudCard = nullptr; QLabel *m_cloudValue = nullptr;

    QLabel *m_infoLabel = nullptr;
    QPushButton *m_modelDetailsButton = nullptr;
    QListWidget *m_alarmList = nullptr;
    QLabel *m_bottomLabel = nullptr;
    QString m_modelDetailsText;
};

#endif // MAINWINDOW_H

#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include <QDateTime>

#include "SystemStatus.h"

class QLabel;
class QFrame;
class QListWidget;
class QProcess;
class QPushButton;
class QTabWidget;
class QTimer;
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
    void toggleVoiceAssistant();
    void onVoiceProcessFinished(int exitCode, int exitStatus);
    void onVoiceProcessError();
    void updateVoiceAnimation();
    void setVisionModeCloud();
    void setVisionModeLocal();
    void setVisionModeOff();
    void requestVisionCapture();

private:
    QWidget *buildCentral();
    QWidget *createOverviewPage();
    QWidget *createMetricsPage();
    QWidget *createMetricPage(const QString &title, const QString &unit, QLabel **valueLabelOut, QLabel **detailLabelOut);
    QWidget *createAnalysisPage();
    QWidget *createCameraPage();
    QWidget *createLogPage();
    QWidget *createVoicePage();
    QFrame *createCard(const QString &title, QLabel **valueLabelOut);
    void applyLevelStyle(QFrame *card, QLabel *value, int level);
    void applyValueStyle(QLabel *value, int level);
    QString repoRootPath() const;
    bool startVoiceAssistant();
    void stopVoiceAssistant();
    void setVoiceButtonRunning(bool running);
    void writeVisionModeRequest(const QString &mode);
    void updateVisionImage(const SystemStatus &status);
    void appendLogLine(const QString &line);

    StatusModel *m_model = nullptr;
    bool m_compactMode = false;

    QTabWidget *m_tabs = nullptr;

    QLabel *m_overviewStatusLabel = nullptr;
    QLabel *m_overviewSensorLabel = nullptr;
    QLabel *m_overviewCloudLabel = nullptr;
    QLabel *m_metricsNoteLabel = nullptr;

    QFrame *m_tempCard = nullptr; QLabel *m_tempValue = nullptr; QLabel *m_tempDetail = nullptr;
    QFrame *m_humiCard = nullptr; QLabel *m_humiValue = nullptr; QLabel *m_humiDetail = nullptr;
    QFrame *m_sysCard = nullptr; QLabel *m_sysValue = nullptr;
    QFrame *m_tvocCard = nullptr; QLabel *m_tvocValue = nullptr; QLabel *m_tvocDetail = nullptr;
    QFrame *m_eco2Card = nullptr; QLabel *m_eco2Value = nullptr; QLabel *m_eco2Detail = nullptr;
    QFrame *m_mq3Card = nullptr; QLabel *m_mq3Value = nullptr; QLabel *m_mq3Detail = nullptr;
    QFrame *m_flameCard = nullptr; QLabel *m_flameValue = nullptr; QLabel *m_flameDetail = nullptr;
    QFrame *m_riskCard = nullptr; QLabel *m_riskValue = nullptr; QLabel *m_riskDetail = nullptr;
    QFrame *m_cloudCard = nullptr; QLabel *m_cloudValue = nullptr;

    QLabel *m_infoLabel = nullptr;
    QLabel *m_visionImageLabel = nullptr;
    QLabel *m_visionModeLabel = nullptr;
    QLabel *m_visionStatusLabel = nullptr;
    QLabel *m_visionSummaryLabel = nullptr;
    QLabel *m_visionPpeLabel = nullptr;
    QLabel *m_visionBackendLabel = nullptr;
    QPushButton *m_visionCloudButton = nullptr;
    QPushButton *m_visionLocalButton = nullptr;
    QPushButton *m_visionOffButton = nullptr;
    QPushButton *m_visionCaptureButton = nullptr;
    QLabel *m_voiceAssistantLabel = nullptr;
    QLabel *m_voiceStatusLabel = nullptr;
    QLabel *m_voiceQuestionLabel = nullptr;
    QLabel *m_voiceReplyLabel = nullptr;
    QLabel *m_voiceAnimationLabel = nullptr;
    QPushButton *m_voiceToggleButton = nullptr;
    QPushButton *m_modelDetailsButton = nullptr;
    QProcess *m_voiceProcess = nullptr;
    QListWidget *m_alarmList = nullptr;
    QLabel *m_bottomLabel = nullptr;
    QString m_modelDetailsText;
    QString m_lastSystemLogSignature;
    QString m_lastVoiceLogSignature;
    QString m_lastVisionLogSignature;
    QTimer *m_voiceAnimationTimer = nullptr;
    int m_voiceAnimationFrame = 0;
    int m_lastVoiceState = VOICE_IDLE;
    bool m_voiceManualStop = false;
    QDateTime m_lastVisionTimestamp;
    QDateTime m_showVisionKeyframeUntil;
};

#endif // MAINWINDOW_H

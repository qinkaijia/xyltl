#include "MainWindow.h"
#include "StatusModel.h"

#include <QCoreApplication>
#include <QDateTime>
#include <QDialog>
#include <QDialogButtonBox>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QFrame>
#include <QGridLayout>
#include <QHBoxLayout>
#include <QIODevice>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QList>
#include <QListWidget>
#include <QPixmap>
#include <QProcess>
#include <QProcessEnvironment>
#include <QPushButton>
#include <QSize>
#include <QTabWidget>
#include <QTextEdit>
#include <QTimer>
#include <QVBoxLayout>
#include <QWidget>

static const char *kBgColor = "#f5f7f2";
static const char *kCardColor = "#ffffff";
static const char *kPanelColor = "#eef5f1";
static const char *kTextColor = "#17211d";
static const char *kMutedColor = "#64726b";
static const char *kLineColor = "#d9e2dc";
static const char *kNormalColor = "#1f6f58";
static const char *kWarningColor = "#b3822c";
static const char *kAlarmColor = "#b7463f";
static const char *kAccentColor = "#1f7885";

static const char *levelColor(int level)
{
    switch (level) {
    case LEVEL_NORMAL: return kNormalColor;
    case LEVEL_WARNING: return kWarningColor;
    case LEVEL_ALARM: return kAlarmColor;
    default: return kTextColor;
    }
}

static int levelFromHumidity(double value)
{
    if (value <= 10.0 || value >= 90.0) {
        return LEVEL_ALARM;
    }
    if (value <= 20.0 || value >= 80.0) {
        return LEVEL_WARNING;
    }
    return LEVEL_NORMAL;
}

static int levelFromHigh(double value, double warning, double alarm)
{
    if (value >= alarm) {
        return LEVEL_ALARM;
    }
    if (value >= warning) {
        return LEVEL_WARNING;
    }
    return LEVEL_NORMAL;
}

static QString flameStatusText(bool detected)
{
    return detected ? QStringLiteral("检测到") : QStringLiteral("未检测");
}

static QString temperatureText(double value)
{
    return value <= -900.0 ? QStringLiteral("--") : QStringLiteral("%1 ℃").arg(value, 0, 'f', 1);
}

static QString humidityText(double value)
{
    return value < 0.0 ? QStringLiteral("--") : QStringLiteral("%1 %RH").arg(value, 0, 'f', 0);
}

static QString onlineText(bool online)
{
    return online ? QStringLiteral("在线") : QStringLiteral("离线");
}

static QString optionalStateText(int state)
{
    if (state > 0) {
        return QStringLiteral("已佩戴");
    }
    if (state == 0) {
        return QStringLiteral("未佩戴");
    }
    return QStringLiteral("未确认");
}

static QString ppeStatusText(const QString &status)
{
    if (status == QStringLiteral("pass")) {
        return QStringLiteral("防护合规");
    }
    if (status == QStringLiteral("fail")) {
        return QStringLiteral("防护缺失");
    }
    if (status == QStringLiteral("error")) {
        return QStringLiteral("视觉异常");
    }
    return QStringLiteral("等待识别");
}

static int ppeStatusLevel(const QString &status)
{
    if (status == QStringLiteral("fail") || status == QStringLiteral("error")) {
        return LEVEL_ALARM;
    }
    if (status == QStringLiteral("unknown")) {
        return LEVEL_WARNING;
    }
    return LEVEL_NORMAL;
}

static QString timestampText(const QDateTime &time)
{
    return time.isValid() ? time.toString(QStringLiteral("HH:mm:ss")) : QStringLiteral("--");
}

static bool envFlagEnabled(const char *name, bool defaultValue)
{
    const QString value = qEnvironmentVariable(name).trimmed().toLower();
    if (value.isEmpty()) {
        return defaultValue;
    }
    return value == QStringLiteral("1")
        || value == QStringLiteral("true")
        || value == QStringLiteral("yes")
        || value == QStringLiteral("on");
}

MainWindow::MainWindow(StatusModel *model, bool compactMode, QWidget *parent)
    : QMainWindow(parent), m_model(model), m_compactMode(compactMode)
{
    setWindowTitle(QStringLiteral("智能工业环境监测系统"));
    resize(m_compactMode ? QSize(780, 450) : QSize(1024, 600));
    setCentralWidget(buildCentral());

    m_voiceProcess = new QProcess(this);
    connect(m_voiceProcess, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
            this, [this](int exitCode, QProcess::ExitStatus exitStatus) {
                onVoiceProcessFinished(exitCode, static_cast<int>(exitStatus));
            });
    connect(m_voiceProcess, &QProcess::errorOccurred, this, &MainWindow::onVoiceProcessError);
    connect(m_voiceProcess, &QProcess::readyRead, this, [this]() {
        if (m_voiceProcess) {
            m_voiceProcess->readAll();
        }
    });

    m_voiceAnimationTimer = new QTimer(this);
    m_voiceAnimationTimer->setInterval(450);
    connect(m_voiceAnimationTimer, &QTimer::timeout, this, &MainWindow::updateVoiceAnimation);
    m_voiceAnimationTimer->start();

    if (m_model) {
        connect(m_model, &StatusModel::statusChanged, this, &MainWindow::onStatusChanged);
        connect(m_model, &StatusModel::alarmLogged, this, &MainWindow::onAlarmLogged);
    }

    if (envFlagEnabled("VOICE_AUTOSTART", true)) {
        QTimer::singleShot(1200, this, [this]() {
            startVoiceAssistant();
        });
    }
}

QFrame *MainWindow::createCard(const QString &title, QLabel **valueLabelOut)
{
    QFrame *card = new QFrame;
    card->setFrameShape(QFrame::StyledPanel);
    card->setMinimumHeight(m_compactMode ? 56 : 92);

    QLabel *titleLabel = new QLabel(title);
    titleLabel->setStyleSheet(
        QStringLiteral("color:%1; font-size:%2px; font-weight:700; background:transparent;")
            .arg(kMutedColor)
            .arg(m_compactMode ? 12 : 16));

    QLabel *valueLabel = new QLabel(QStringLiteral("--"));
    valueLabel->setWordWrap(false);
    valueLabel->setStyleSheet(
        QStringLiteral("color:%1; font-size:%2px; font-weight:bold; background:transparent;")
            .arg(kTextColor)
            .arg(m_compactMode ? 19 : 30));

    QVBoxLayout *layout = new QVBoxLayout(card);
    layout->setContentsMargins(m_compactMode ? 8 : 14, m_compactMode ? 6 : 10,
                               m_compactMode ? 8 : 14, m_compactMode ? 6 : 10);
    layout->setSpacing(m_compactMode ? 2 : 6);
    layout->addWidget(titleLabel);
    layout->addWidget(valueLabel);
    layout->addStretch();

    card->setStyleSheet(
        QStringLiteral("QFrame{background:%1; border-radius:8px; border:1px solid %2;}").arg(kCardColor).arg(kLineColor));

    if (valueLabelOut) {
        *valueLabelOut = valueLabel;
    }
    return card;
}

QWidget *MainWindow::buildCentral()
{
    QWidget *central = new QWidget;
    central->setStyleSheet(QStringLiteral("background:%1; color:%2;").arg(kBgColor).arg(kTextColor));

    QVBoxLayout *root = new QVBoxLayout(central);
    root->setContentsMargins(m_compactMode ? 8 : 18, m_compactMode ? 6 : 14,
                             m_compactMode ? 8 : 18, m_compactMode ? 6 : 14);
    root->setSpacing(m_compactMode ? 6 : 12);

    QHBoxLayout *topBar = new QHBoxLayout;
    topBar->setSpacing(12);

    QLabel *title = new QLabel(QStringLiteral("龙芯密闭空间智能安全监护仪"));
    title->setAlignment(Qt::AlignLeft | Qt::AlignVCenter);
    title->setStyleSheet(
        QStringLiteral("color:%1; font-size:%2px; font-weight:bold; padding:%3px; background:transparent;")
            .arg(kAccentColor)
            .arg(m_compactMode ? 19 : 30)
            .arg(m_compactMode ? 2 : 6));
    topBar->addWidget(title, 1);

    m_voiceToggleButton = new QPushButton(QStringLiteral("启动语音"));
    m_voiceToggleButton->setMinimumHeight(m_compactMode ? 34 : 42);
    m_voiceToggleButton->setStyleSheet(
        QStringLiteral("QPushButton{background:#1f7885; color:white; border:1px solid #1f7885; "
                       "border-radius:6px; padding:4px 10px; font-size:%1px; font-weight:700;}"
                       "QPushButton:disabled{background:#eef2ef; color:#9aa6a0; border-color:#d9e2dc;}")
            .arg(m_compactMode ? 13 : 18));
    connect(m_voiceToggleButton, &QPushButton::clicked, this, &MainWindow::toggleVoiceAssistant);
    topBar->addWidget(m_voiceToggleButton);

    m_modelDetailsButton = new QPushButton(QStringLiteral("模型详情"));
    m_modelDetailsButton->setMinimumHeight(m_compactMode ? 34 : 42);
    m_modelDetailsButton->setEnabled(false);
    m_modelDetailsButton->setStyleSheet(
        QStringLiteral("QPushButton{background:#e6f3f5; color:%1; border:1px solid %1; "
                       "border-radius:6px; padding:4px 10px; font-size:%2px;}"
                       "QPushButton:disabled{background:#eef2ef; color:#9aa6a0; border-color:#d9e2dc;}")
            .arg(kAccentColor)
            .arg(m_compactMode ? 13 : 18));
    connect(m_modelDetailsButton, &QPushButton::clicked, this, &MainWindow::showModelDetails);
    topBar->addWidget(m_modelDetailsButton);

    root->addLayout(topBar);

    m_tabs = new QTabWidget;
    m_tabs->setDocumentMode(true);
    m_tabs->setUsesScrollButtons(true);
    m_tabs->setElideMode(Qt::ElideRight);
    m_tabs->setStyleSheet(
        QStringLiteral(
            "QTabWidget::pane{border:1px solid %1; border-radius:8px; background:%2;}"
            "QTabBar::tab{background:#eef2ef; color:%3; border:1px solid %1; "
            "border-bottom:none; border-top-left-radius:6px; border-top-right-radius:6px; "
            "padding:%4px %5px; font-size:%6px; min-width:%7px;}"
            "QTabBar::tab:selected{background:%2; color:%8; font-weight:700;}")
            .arg(kLineColor)
            .arg(kCardColor)
            .arg(kMutedColor)
            .arg(m_compactMode ? 5 : 8)
            .arg(m_compactMode ? 8 : 14)
            .arg(m_compactMode ? 12 : 17)
            .arg(m_compactMode ? 48 : 78)
            .arg(kAccentColor));

    m_tabs->addTab(createOverviewPage(), QStringLiteral("总览"));
    m_tabs->addTab(createMetricsPage(), QStringLiteral("环境监测"));
    m_tabs->addTab(createAnalysisPage(), QStringLiteral("AI分析"));
    m_tabs->addTab(createCameraPage(), QStringLiteral("视觉"));
    m_tabs->addTab(createLogPage(), QStringLiteral("日志"));
    m_tabs->addTab(createVoicePage(), QStringLiteral("语音"));
    m_tabs->setCurrentIndex(1);
    root->addWidget(m_tabs, 1);

    m_bottomLabel = new QLabel;
    m_bottomLabel->setAlignment(Qt::AlignCenter);
    m_bottomLabel->setStyleSheet(
        QStringLiteral("color:%1; font-size:%2px; padding:%3px; background:transparent;")
            .arg(kTextColor)
            .arg(m_compactMode ? 14 : 20)
            .arg(m_compactMode ? 3 : 6));
    m_bottomLabel->setText(QStringLiteral("语音助手：待唤醒   |   云端：已连接"));
    root->addWidget(m_bottomLabel);

    return central;
}

QWidget *MainWindow::createOverviewPage()
{
    QWidget *page = new QWidget;
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(m_compactMode ? 12 : 22, m_compactMode ? 10 : 20,
                               m_compactMode ? 12 : 22, m_compactMode ? 10 : 20);
    layout->setSpacing(m_compactMode ? 8 : 14);

    m_overviewStatusLabel = new QLabel(QStringLiteral("系统状态：等待数据"));
    m_overviewStatusLabel->setAlignment(Qt::AlignCenter);
    m_overviewStatusLabel->setWordWrap(true);
    m_overviewStatusLabel->setStyleSheet(
        QStringLiteral("QLabel{background:%1; border:1px solid %2; border-radius:8px; "
                       "padding:%3px; font-size:%4px; font-weight:700; color:%5;}")
            .arg(kPanelColor)
            .arg(kLineColor)
            .arg(m_compactMode ? 10 : 18)
            .arg(m_compactMode ? 24 : 36)
            .arg(kAccentColor));
    layout->addWidget(m_overviewStatusLabel, 2);

    m_overviewSensorLabel = new QLabel(QStringLiteral("2K0301：--"));
    m_overviewSensorLabel->setWordWrap(true);
    m_overviewSensorLabel->setAlignment(Qt::AlignVCenter | Qt::AlignLeft);
    m_overviewSensorLabel->setStyleSheet(
        QStringLiteral("QLabel{background:%1; border:1px solid %2; border-radius:8px; "
                       "padding:%3px; font-size:%4px; color:%5;}")
            .arg(kCardColor)
            .arg(kLineColor)
            .arg(m_compactMode ? 8 : 14)
            .arg(m_compactMode ? 14 : 20)
            .arg(kTextColor));
    layout->addWidget(m_overviewSensorLabel, 1);

    m_overviewCloudLabel = new QLabel(QStringLiteral("云端：--"));
    m_overviewCloudLabel->setWordWrap(true);
    m_overviewCloudLabel->setAlignment(Qt::AlignVCenter | Qt::AlignLeft);
    m_overviewCloudLabel->setStyleSheet(
        QStringLiteral("QLabel{background:%1; border:1px solid %2; border-radius:8px; "
                       "padding:%3px; font-size:%4px; color:%5;}")
            .arg(kCardColor)
            .arg(kLineColor)
            .arg(m_compactMode ? 8 : 14)
            .arg(m_compactMode ? 14 : 20)
            .arg(kTextColor));
    layout->addWidget(m_overviewCloudLabel, 1);
    return page;
}

QWidget *MainWindow::createMetricsPage()
{
    QWidget *page = new QWidget;
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(m_compactMode ? 10 : 18, m_compactMode ? 8 : 14,
                               m_compactMode ? 10 : 18, m_compactMode ? 8 : 14);
    layout->setSpacing(m_compactMode ? 6 : 10);

    QGridLayout *grid = new QGridLayout;
    grid->setSpacing(m_compactMode ? 6 : 12);

    m_tempCard = createCard(QStringLiteral("温度"), &m_tempValue);
    m_humiCard = createCard(QStringLiteral("湿度"), &m_humiValue);
    m_tvocCard = createCard(QStringLiteral("TVOC"), &m_tvocValue);
    m_eco2Card = createCard(QStringLiteral("eCO2"), &m_eco2Value);
    m_mq3Card = createCard(QStringLiteral("MQ-3"), &m_mq3Value);
    m_flameCard = createCard(QStringLiteral("火焰"), &m_flameValue);
    m_riskCard = createCard(QStringLiteral("风险"), &m_riskValue);

    grid->addWidget(m_tempCard, 0, 0);
    grid->addWidget(m_humiCard, 0, 1);
    grid->addWidget(m_tvocCard, 0, 2);
    grid->addWidget(m_eco2Card, 0, 3);
    grid->addWidget(m_mq3Card, 1, 0);
    grid->addWidget(m_flameCard, 1, 1);
    grid->addWidget(m_riskCard, 1, 2, 1, 2);
    layout->addLayout(grid, 1);

    m_metricsNoteLabel = new QLabel(QStringLiteral("等待 2K0301 数据刷新"));
    m_metricsNoteLabel->setWordWrap(true);
    m_metricsNoteLabel->setAlignment(Qt::AlignVCenter | Qt::AlignLeft);
    m_metricsNoteLabel->setStyleSheet(
        QStringLiteral("QLabel{background:%1; border:1px solid %2; border-radius:8px; "
                       "padding:%3px; font-size:%4px; color:%5;}")
            .arg(kPanelColor)
            .arg(kLineColor)
            .arg(m_compactMode ? 7 : 12)
            .arg(m_compactMode ? 13 : 18)
            .arg(kTextColor));
    layout->addWidget(m_metricsNoteLabel);
    return page;
}

QWidget *MainWindow::createMetricPage(const QString &title, const QString &unit, QLabel **valueLabelOut, QLabel **detailLabelOut)
{
    QWidget *page = new QWidget;
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(m_compactMode ? 12 : 22, m_compactMode ? 10 : 20,
                               m_compactMode ? 12 : 22, m_compactMode ? 10 : 20);
    layout->setSpacing(m_compactMode ? 8 : 14);

    QLabel *titleLabel = new QLabel(unit.isEmpty() ? title : QStringLiteral("%1（%2）").arg(title, unit));
    titleLabel->setStyleSheet(
        QStringLiteral("color:%1; font-size:%2px; font-weight:700; background:transparent;")
            .arg(kMutedColor)
            .arg(m_compactMode ? 15 : 22));
    layout->addWidget(titleLabel);

    QLabel *valueLabel = new QLabel(QStringLiteral("--"));
    valueLabel->setAlignment(Qt::AlignCenter);
    valueLabel->setWordWrap(true);
    valueLabel->setStyleSheet(
        QStringLiteral("QLabel{background:%1; border:2px solid %2; border-radius:8px; "
                       "padding:%3px; font-size:%4px; font-weight:800; color:%5;}")
            .arg(kPanelColor)
            .arg(kLineColor)
            .arg(m_compactMode ? 8 : 16)
            .arg(m_compactMode ? 36 : 56)
            .arg(kTextColor));
    layout->addWidget(valueLabel, 2);

    QLabel *detailLabel = new QLabel(QStringLiteral("等待数据刷新"));
    detailLabel->setWordWrap(true);
    detailLabel->setAlignment(Qt::AlignVCenter | Qt::AlignLeft);
    detailLabel->setStyleSheet(
        QStringLiteral("QLabel{background:%1; border:1px solid %2; border-radius:8px; "
                       "padding:%3px; font-size:%4px; color:%5;}")
            .arg(kCardColor)
            .arg(kLineColor)
            .arg(m_compactMode ? 8 : 14)
            .arg(m_compactMode ? 14 : 20)
            .arg(kTextColor));
    layout->addWidget(detailLabel, 1);

    if (valueLabelOut) {
        *valueLabelOut = valueLabel;
    }
    if (detailLabelOut) {
        *detailLabelOut = detailLabel;
    }
    return page;
}

QWidget *MainWindow::createAnalysisPage()
{
    QWidget *page = new QWidget;
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(m_compactMode ? 12 : 22, m_compactMode ? 10 : 20,
                               m_compactMode ? 12 : 22, m_compactMode ? 10 : 20);
    layout->setSpacing(m_compactMode ? 8 : 14);

    m_infoLabel = new QLabel(QStringLiteral("等待 AI 分析结果。"));
    m_infoLabel->setWordWrap(true);
    m_infoLabel->setAlignment(Qt::AlignTop | Qt::AlignLeft);
    m_infoLabel->setStyleSheet(
        QStringLiteral("QLabel{background:%1; border-radius:8px; border:1px solid %2; "
                       "padding:%3px; font-size:%4px; color:%5;}")
            .arg(kPanelColor)
            .arg(kLineColor)
            .arg(m_compactMode ? 10 : 16)
            .arg(m_compactMode ? 15 : 21)
            .arg(kTextColor));
    layout->addWidget(m_infoLabel, 1);
    return page;
}

QWidget *MainWindow::createCameraPage()
{
    QWidget *page = new QWidget;
    QHBoxLayout *layout = new QHBoxLayout(page);
    layout->setContentsMargins(m_compactMode ? 10 : 18, m_compactMode ? 8 : 14,
                               m_compactMode ? 10 : 18, m_compactMode ? 8 : 14);
    layout->setSpacing(m_compactMode ? 8 : 14);

    QFrame *imagePanel = new QFrame;
    imagePanel->setStyleSheet(
        QStringLiteral("QFrame{background:%1; border:1px solid %2; border-radius:8px;}").arg(kCardColor).arg(kLineColor));
    QVBoxLayout *imageLayout = new QVBoxLayout(imagePanel);
    imageLayout->setContentsMargins(m_compactMode ? 8 : 12, m_compactMode ? 8 : 12,
                                    m_compactMode ? 8 : 12, m_compactMode ? 8 : 12);
    QLabel *imageTitle = new QLabel(QStringLiteral("USB 摄像头实时画面 / 检测关键帧"));
    imageTitle->setStyleSheet(
        QStringLiteral("color:%1; font-size:%2px; font-weight:800; background:transparent;")
            .arg(kMutedColor)
            .arg(m_compactMode ? 13 : 18));
    imageLayout->addWidget(imageTitle);

    m_visionImageLabel = new QLabel(QStringLiteral("等待摄像头画面"));
    m_visionImageLabel->setMinimumSize(m_compactMode ? QSize(300, 190) : QSize(520, 320));
    m_visionImageLabel->setAlignment(Qt::AlignCenter);
    m_visionImageLabel->setScaledContents(false);
    m_visionImageLabel->setStyleSheet(
        QStringLiteral("QLabel{background:#111b18; color:#d9e2dc; border-radius:8px; "
                       "font-size:%1px; font-weight:700;}").arg(m_compactMode ? 14 : 18));
    imageLayout->addWidget(m_visionImageLabel, 1);

    QFrame *statusPanel = new QFrame;
    statusPanel->setMinimumWidth(m_compactMode ? 220 : 320);
    statusPanel->setStyleSheet(
        QStringLiteral("QFrame{background:%1; border:1px solid %2; border-radius:8px;}").arg(kPanelColor).arg(kLineColor));
    QVBoxLayout *statusLayout = new QVBoxLayout(statusPanel);
    statusLayout->setContentsMargins(m_compactMode ? 10 : 16, m_compactMode ? 8 : 14,
                                     m_compactMode ? 10 : 16, m_compactMode ? 8 : 14);
    statusLayout->setSpacing(m_compactMode ? 6 : 10);

    m_visionStatusLabel = new QLabel(QStringLiteral("视觉状态：等待识别"));
    m_visionStatusLabel->setWordWrap(true);
    m_visionStatusLabel->setAlignment(Qt::AlignCenter);
    m_visionStatusLabel->setStyleSheet(
        QStringLiteral("QLabel{background:white; border:2px solid %1; border-radius:8px; "
                       "padding:%2px; font-size:%3px; font-weight:900; color:%1;}")
            .arg(kWarningColor)
            .arg(m_compactMode ? 8 : 12)
            .arg(m_compactMode ? 17 : 24));
    statusLayout->addWidget(m_visionStatusLabel);

    m_visionModeLabel = new QLabel(QStringLiteral("模式：--"));
    m_visionBackendLabel = new QLabel(QStringLiteral("后端：--"));
    m_visionPpeLabel = new QLabel(QStringLiteral("人员：--\n安全帽：--  口罩：--  反光背心：--"));
    m_visionSummaryLabel = new QLabel(QStringLiteral("结论：等待视觉模块启动"));
    QList<QLabel *> labels = {m_visionModeLabel, m_visionBackendLabel, m_visionPpeLabel, m_visionSummaryLabel};
    for (QLabel *label : labels) {
        label->setWordWrap(true);
        label->setStyleSheet(
            QStringLiteral("QLabel{background:white; border:1px solid %1; border-radius:8px; "
                           "padding:%2px; font-size:%3px; color:%4;}")
                .arg(kLineColor)
                .arg(m_compactMode ? 7 : 10)
                .arg(m_compactMode ? 13 : 18)
                .arg(kTextColor));
        statusLayout->addWidget(label);
    }

    m_visionCaptureButton = new QPushButton(QStringLiteral("拍照检测"));
    m_visionCaptureButton->setMinimumHeight(m_compactMode ? 34 : 42);
    m_visionCaptureButton->setStyleSheet(
        QStringLiteral("QPushButton{background:%1; color:white; border:1px solid %1; "
                       "border-radius:6px; padding:5px 12px; font-size:%2px; font-weight:900;}"
                       "QPushButton:pressed{background:#185d66;}")
            .arg(kAccentColor)
            .arg(m_compactMode ? 14 : 18));
    connect(m_visionCaptureButton, &QPushButton::clicked, this, &MainWindow::requestVisionCapture);
    statusLayout->addWidget(m_visionCaptureButton);

    QHBoxLayout *buttons = new QHBoxLayout;
    m_visionCloudButton = new QPushButton(QStringLiteral("云端"));
    m_visionLocalButton = new QPushButton(QStringLiteral("本地"));
    m_visionOffButton = new QPushButton(QStringLiteral("关闭"));
    QList<QPushButton *> modeButtons = {m_visionCloudButton, m_visionLocalButton, m_visionOffButton};
    for (QPushButton *button : modeButtons) {
        button->setMinimumHeight(m_compactMode ? 32 : 40);
        button->setStyleSheet(
            QStringLiteral("QPushButton{background:#ffffff; color:%1; border:1px solid %2; "
                           "border-radius:6px; padding:4px 10px; font-size:%3px; font-weight:800;}")
                .arg(kAccentColor)
                .arg(kLineColor)
                .arg(m_compactMode ? 13 : 17));
        buttons->addWidget(button);
    }
    connect(m_visionCloudButton, &QPushButton::clicked, this, &MainWindow::setVisionModeCloud);
    connect(m_visionLocalButton, &QPushButton::clicked, this, &MainWindow::setVisionModeLocal);
    connect(m_visionOffButton, &QPushButton::clicked, this, &MainWindow::setVisionModeOff);
    statusLayout->addLayout(buttons);
    statusLayout->addStretch();

    layout->addWidget(imagePanel, 3);
    layout->addWidget(statusPanel, 2);
    return page;
}

QWidget *MainWindow::createLogPage()
{
    QWidget *page = new QWidget;
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(m_compactMode ? 10 : 18, m_compactMode ? 8 : 14,
                               m_compactMode ? 10 : 18, m_compactMode ? 8 : 14);
    layout->setSpacing(m_compactMode ? 6 : 10);

    QLabel *logTitle = new QLabel(QStringLiteral("报警与事件日志"));
    logTitle->setStyleSheet(
        QStringLiteral("color:%1; font-size:%2px; font-weight:700; background:transparent;")
            .arg(kMutedColor)
            .arg(m_compactMode ? 15 : 22));
    layout->addWidget(logTitle);

    m_alarmList = new QListWidget;
    m_alarmList->setStyleSheet(
        QStringLiteral("QListWidget{background:%1; border-radius:8px; border:1px solid %2; "
                       "font-size:%3px; color:%4; padding:%5px;}")
            .arg(kCardColor)
            .arg(kLineColor)
            .arg(m_compactMode ? 14 : 20)
            .arg(kAlarmColor)
            .arg(m_compactMode ? 6 : 10));
    layout->addWidget(m_alarmList, 1);
    return page;
}

QWidget *MainWindow::createVoicePage()
{
    QWidget *page = new QWidget;
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(m_compactMode ? 12 : 22, m_compactMode ? 10 : 20,
                               m_compactMode ? 12 : 22, m_compactMode ? 10 : 20);
    layout->setSpacing(m_compactMode ? 8 : 14);

    m_voiceStatusLabel = new QLabel(QStringLiteral("语音助手：待唤醒"));
    m_voiceStatusLabel->setAlignment(Qt::AlignCenter);
    m_voiceStatusLabel->setStyleSheet(
        QStringLiteral("QLabel{background:#e6f3f5; border:1px solid %1; border-radius:8px; "
                       "padding:%2px; font-size:%3px; font-weight:700; color:#20333a;}")
            .arg(kAccentColor)
            .arg(m_compactMode ? 8 : 14)
            .arg(m_compactMode ? 21 : 32));
    layout->addWidget(m_voiceStatusLabel);

    m_voiceAnimationLabel = new QLabel(QStringLiteral("○ ○ ○"));
    m_voiceAnimationLabel->setAlignment(Qt::AlignCenter);
    m_voiceAnimationLabel->setStyleSheet(
        QStringLiteral("color:%1; font-size:%2px; font-weight:800; background:transparent;")
            .arg(kAccentColor)
            .arg(m_compactMode ? 24 : 36));
    layout->addWidget(m_voiceAnimationLabel);

    m_voiceQuestionLabel = new QLabel(QStringLiteral("问：--"));
    m_voiceQuestionLabel->setWordWrap(true);
    m_voiceQuestionLabel->setStyleSheet(
        QStringLiteral("QLabel{background:%1; border:1px solid %2; border-radius:8px; "
                       "padding:%3px; font-size:%4px; color:%5;}")
            .arg(kCardColor)
            .arg(kLineColor)
            .arg(m_compactMode ? 8 : 12)
            .arg(m_compactMode ? 14 : 20)
            .arg(kTextColor));
    layout->addWidget(m_voiceQuestionLabel);

    m_voiceReplyLabel = new QLabel(QStringLiteral("答：--"));
    m_voiceReplyLabel->setWordWrap(true);
    m_voiceReplyLabel->setAlignment(Qt::AlignTop | Qt::AlignLeft);
    m_voiceReplyLabel->setStyleSheet(
        QStringLiteral("QLabel{background:%1; border:1px solid %2; border-radius:8px; "
                       "padding:%3px; font-size:%4px; color:%5;}")
            .arg(kPanelColor)
            .arg(kLineColor)
            .arg(m_compactMode ? 8 : 12)
            .arg(m_compactMode ? 15 : 21)
            .arg(kTextColor));
    layout->addWidget(m_voiceReplyLabel, 1);
    return page;
}

void MainWindow::applyLevelStyle(QFrame *card, QLabel *value, int level)
{
    const char *color = levelColor(level);
    card->setStyleSheet(
        QStringLiteral("QFrame{background:%1; border-radius:8px; border:2px solid %2;}").arg(kCardColor).arg(color));
    value->setStyleSheet(
        QStringLiteral("color:%1; font-size:%2px; font-weight:bold; background:transparent;")
            .arg(color)
            .arg(m_compactMode ? 19 : 30));
}

void MainWindow::applyValueStyle(QLabel *value, int level)
{
    if (!value) {
        return;
    }
    const char *color = levelColor(level);
    value->setStyleSheet(
        QStringLiteral("QLabel{background:%1; border:2px solid %2; border-radius:8px; "
                       "padding:%3px; font-size:%4px; font-weight:800; color:%2;}")
            .arg(kPanelColor)
            .arg(color)
            .arg(m_compactMode ? 8 : 16)
            .arg(m_compactMode ? 36 : 56));
}


void MainWindow::onStatusChanged(const SystemStatus &s)
{
    const QString reason = s.alarmMessage.isEmpty() ? QStringLiteral("暂无异常说明") : s.alarmMessage;
    const QString suggestion = s.suggestion.isEmpty() ? QStringLiteral("保持常规监测") : s.suggestion;
    const QString latency = s.cloudLatencyMs >= 0 ? QStringLiteral("%1 ms").arg(s.cloudLatencyMs) : QStringLiteral("--");
    const QString models = s.modelSource.isEmpty() ? QStringLiteral("--") : s.modelSource;
    const QString source = s.sensorSource.isEmpty() ? QStringLiteral("2K0301") : s.sensorSource;
    const QString timeText = timestampText(s.timestamp);
    const bool tempValid = s.sensorOnline && s.temperature > -900.0;
    const bool humiValid = s.sensorOnline && s.humidity >= 0.0;
    const int sensorDisplayLevel = s.sensorOnline ? LEVEL_NORMAL : LEVEL_ALARM;

    m_modelDetailsText = s.modelDetails;
    if (m_modelDetailsButton) {
        m_modelDetailsButton->setEnabled(!m_modelDetailsText.isEmpty());
    }

    if (m_overviewStatusLabel) {
        const char *color = levelColor(s.alarmLevel);
        m_overviewStatusLabel->setText(
            QStringLiteral("%1\n%2").arg(s.statusText.isEmpty() ? levelToText(s.alarmLevel) : s.statusText, reason));
        m_overviewStatusLabel->setStyleSheet(
            QStringLiteral("QLabel{background:%1; border:2px solid %2; border-radius:8px; "
                           "padding:%3px; font-size:%4px; font-weight:800; color:%2;}")
                .arg(kPanelColor)
                .arg(color)
                .arg(m_compactMode ? 10 : 18)
                .arg(m_compactMode ? 24 : 36));
    }
    if (m_overviewSensorLabel) {
        m_overviewSensorLabel->setText(
            QStringLiteral("设备：%1\n采集板：%2  执行器：%3  来源：%4  更新时间：%5\n温度：%6  湿度：%7  TVOC：%8 ppb  eCO2：%9 ppm  MQ-3：%10 mg/L")
                .arg(s.deviceId.isEmpty() ? QStringLiteral("--") : s.deviceId)
                .arg(onlineText(s.sensorOnline))
                .arg(onlineText(s.actuatorOnline))
                .arg(source)
                .arg(timeText)
                .arg(tempValid ? temperatureText(s.temperature) : QStringLiteral("离线"))
                .arg(humiValid ? humidityText(s.humidity) : QStringLiteral("离线"))
                .arg(s.tvoc, 0, 'f', 0)
                .arg(s.eco2, 0, 'f', 0)
                .arg(s.mq3Value, 0, 'f', 3));
    }
    if (m_overviewCloudLabel) {
        m_overviewCloudLabel->setText(
            QStringLiteral("云端：%1  延迟：%2  分析模式：%3\n模型：%4\n建议：%5")
                .arg(cloudStateToText(s.cloudConnected))
                .arg(latency)
                .arg(s.analysisMode.isEmpty() ? QStringLiteral("mock") : s.analysisMode)
                .arg(models)
                .arg(suggestion));
    }

    if (m_tempValue) {
        m_tempValue->setText(tempValid ? temperatureText(s.temperature) : QStringLiteral("离线"));
        const int level = tempValid ? levelFromHigh(s.temperature, 60.0, 75.0) : sensorDisplayLevel;
        if (m_tempCard) {
            applyLevelStyle(m_tempCard, m_tempValue, level);
        } else {
            applyValueStyle(m_tempValue, level);
        }
    }
    if (m_tempDetail) {
        m_tempDetail->setText(
            QStringLiteral("采集板：%1\n阈值：60 ℃预警 / 75 ℃报警\n原始值：%2  更新时间：%3")
                .arg(onlineText(s.sensorOnline))
                .arg(s.temperature, 0, 'f', 1)
                .arg(timeText));
    }

    if (m_humiValue) {
        m_humiValue->setText(humiValid ? humidityText(s.humidity) : QStringLiteral("离线"));
        const int level = humiValid ? levelFromHumidity(s.humidity) : sensorDisplayLevel;
        if (m_humiCard) {
            applyLevelStyle(m_humiCard, m_humiValue, level);
        } else {
            applyValueStyle(m_humiValue, level);
        }
    }
    if (m_humiDetail) {
        m_humiDetail->setText(
            QStringLiteral("采集板：%1\n阈值：20-80 %RH 预警，10-90 %RH 外报警\n原始值：%2  更新时间：%3")
                .arg(onlineText(s.sensorOnline))
                .arg(s.humidity, 0, 'f', 1)
                .arg(timeText));
    }

    if (m_tvocValue) {
        m_tvocValue->setText(s.sensorOnline ? QStringLiteral("%1 ppb").arg(s.tvoc, 0, 'f', 0) : QStringLiteral("离线"));
        const int level = s.sensorOnline ? s.tvocLevel : sensorDisplayLevel;
        if (m_tvocCard) {
            applyLevelStyle(m_tvocCard, m_tvocValue, level);
        } else {
            applyValueStyle(m_tvocValue, level);
        }
    }
    if (m_tvocDetail) {
        m_tvocDetail->setText(QStringLiteral("总挥发性有机物。采集板：%1\n当前原始值：%2 ppb").arg(onlineText(s.sensorOnline)).arg(s.tvoc, 0, 'f', 0));
    }

    if (m_eco2Value) {
        m_eco2Value->setText(s.sensorOnline ? QStringLiteral("%1 ppm").arg(s.eco2, 0, 'f', 0) : QStringLiteral("离线"));
        const int level = s.sensorOnline ? s.eco2Level : sensorDisplayLevel;
        if (m_eco2Card) {
            applyLevelStyle(m_eco2Card, m_eco2Value, level);
        } else {
            applyValueStyle(m_eco2Value, level);
        }
    }
    if (m_eco2Detail) {
        m_eco2Detail->setText(QStringLiteral("等效二氧化碳浓度。采集板：%1\n当前原始值：%2 ppm").arg(onlineText(s.sensorOnline)).arg(s.eco2, 0, 'f', 0));
    }

    if (m_mq3Value) {
        m_mq3Value->setText(s.sensorOnline ? QStringLiteral("%1 mg/L").arg(s.mq3Value, 0, 'f', 3) : QStringLiteral("离线"));
        const int level = s.sensorOnline ? s.mq3Level : sensorDisplayLevel;
        if (m_mq3Card) {
            applyLevelStyle(m_mq3Card, m_mq3Value, level);
        } else {
            applyValueStyle(m_mq3Value, level);
        }
    }
    if (m_mq3Detail) {
        m_mq3Detail->setText(QStringLiteral("MQ-3 乙醇浓度。采集板：%1\n当前原始值：%2 mg/L").arg(onlineText(s.sensorOnline)).arg(s.mq3Value, 0, 'f', 3));
    }

    if (m_flameValue) {
        m_flameValue->setText(s.sensorOnline ? flameStatusText(s.flameDetected) : QStringLiteral("离线"));
        const int level = s.sensorOnline ? s.flameLevel : sensorDisplayLevel;
        if (m_flameCard) {
            applyLevelStyle(m_flameCard, m_flameValue, level);
        } else {
            applyValueStyle(m_flameValue, level);
        }
    }
    if (m_flameDetail) {
        m_flameDetail->setText(QStringLiteral("火焰传感器状态：%1\n采集板：%2").arg(flameStatusText(s.flameDetected), onlineText(s.sensorOnline)));
    }

    if (m_riskValue) {
        m_riskValue->setText(s.sensorOnline ? QStringLiteral("%1 / 100").arg(s.riskScore, 0, 'f', 0) : QStringLiteral("离线"));
        const int level = s.sensorOnline ? s.riskLevel : sensorDisplayLevel;
        if (m_riskCard) {
            applyLevelStyle(m_riskCard, m_riskValue, level);
        } else {
            applyValueStyle(m_riskValue, level);
        }
    }
    if (m_riskDetail) {
        m_riskDetail->setText(QStringLiteral("301 综合风险指数。采集板：%1\n当前原始值：%2/100").arg(onlineText(s.sensorOnline)).arg(s.riskScore, 0, 'f', 0));
    }

    if (m_metricsNoteLabel) {
        m_metricsNoteLabel->setText(
            QStringLiteral("2K0301：%1  执行器：%2  来源：%3  更新时间：%4  原始温湿度：%5 / %6")
                .arg(onlineText(s.sensorOnline))
                .arg(onlineText(s.actuatorOnline))
                .arg(source)
                .arg(timeText)
                .arg(s.temperature, 0, 'f', 1)
                .arg(s.humidity, 0, 'f', 1));
    }

    if (m_infoLabel) {
        m_infoLabel->setText(
            QStringLiteral("状态：%1\n分析模式：%2\n模型：%3\n延迟：%4\n\n原因：%5\n\n建议：%6")
                .arg(s.statusText.isEmpty() ? levelToText(s.alarmLevel) : s.statusText)
                .arg(s.analysisMode.isEmpty() ? QStringLiteral("mock") : s.analysisMode)
                .arg(models)
                .arg(latency)
                .arg(reason)
                .arg(suggestion));
    }

    updateVisionImage(s);
    if (m_visionStatusLabel) {
        const int visionLevel = ppeStatusLevel(s.visionStatus);
        const char *color = levelColor(visionLevel);
        m_visionStatusLabel->setText(QStringLiteral("视觉状态：%1").arg(ppeStatusText(s.visionStatus)));
        m_visionStatusLabel->setStyleSheet(
            QStringLiteral("QLabel{background:white; border:2px solid %1; border-radius:8px; "
                           "padding:%2px; font-size:%3px; font-weight:900; color:%1;}")
                .arg(color)
                .arg(m_compactMode ? 8 : 12)
                .arg(m_compactMode ? 17 : 24));
    }
    if (m_visionModeLabel) {
        const QString visionMode = s.visionMode.isEmpty() ? QStringLiteral("--") : s.visionMode;
        const QString latencyText = s.visionLatencyMs >= 0 ? QStringLiteral("%1 ms").arg(s.visionLatencyMs) : QStringLiteral("--");
        m_visionModeLabel->setText(
            QStringLiteral("模式：%1\n摄像头：%2  延迟：%3")
                .arg(visionMode)
                .arg(s.visionCameraOnline ? QStringLiteral("在线") : QStringLiteral("离线"))
                .arg(latencyText));
    }
    if (m_visionBackendLabel) {
        m_visionBackendLabel->setText(
            QStringLiteral("后端：%1\n火焰：%2")
                .arg(s.visionBackend.isEmpty() ? QStringLiteral("--") : s.visionBackend)
                .arg(s.visionFireDetected ? QStringLiteral("疑似存在") : QStringLiteral("未检测到")));
    }
    if (m_visionPpeLabel) {
        m_visionPpeLabel->setText(
            QStringLiteral("人员：%1\n安全帽：%2  口罩：%3  反光背心：%4\n缺失：%5")
                .arg(s.visionPersonDetected ? QStringLiteral("检测到") : QStringLiteral("未检测到"))
                .arg(optionalStateText(s.visionHelmetState))
                .arg(optionalStateText(s.visionMaskState))
                .arg(optionalStateText(s.visionVestState))
                .arg(s.visionMissingPpe.isEmpty() || s.visionMissingPpe == QStringLiteral("--")
                         ? QStringLiteral("无")
                         : s.visionMissingPpe));
    }
    if (m_visionSummaryLabel) {
        const QString visionText = !s.visionError.isEmpty()
            ? QStringLiteral("错误：%1").arg(s.visionError)
            : QStringLiteral("结论：%1").arg(s.visionSummary.isEmpty() ? QStringLiteral("等待视觉结果") : s.visionSummary);
        m_visionSummaryLabel->setText(visionText);
    }

    m_bottomLabel->setText(
        QStringLiteral("语音助手:%1   |   云端:%2   |   播报:%3")
            .arg(voiceStateToText(s.voiceState))
            .arg(cloudStateToText(s.cloudConnected))
            .arg(s.voiceText.isEmpty() ? QStringLiteral("无") : s.voiceText.left(m_compactMode ? 24 : 36)));

    m_lastVoiceState = s.voiceState;
    const QString assistantState = s.assistantStateText.isEmpty()
        ? voiceStateToText(s.voiceState)
        : s.assistantStateText;
    const QString provider = s.assistantProvider.isEmpty() ? QStringLiteral("local") : s.assistantProvider;
    const QString userText = s.assistantUserText.isEmpty()
        ? QStringLiteral("--")
        : s.assistantUserText.left(m_compactMode ? 34 : 72);
    const QString reply = s.assistantReply.isEmpty()
        ? QStringLiteral("--")
        : s.assistantReply.left(m_compactMode ? 46 : 96);
    const QString exec = s.assistantExecuteMessage.isEmpty()
        ? QString()
        : QStringLiteral("\n执行：%1").arg(s.assistantExecuteMessage.left(m_compactMode ? 38 : 80));
    if (m_voiceStatusLabel) {
        m_voiceStatusLabel->setText(QStringLiteral("语音助手：%1  模型：%2").arg(assistantState, provider));
    }
    if (m_voiceQuestionLabel) {
        m_voiceQuestionLabel->setText(QStringLiteral("问：%1").arg(userText));
    }
    if (m_voiceReplyLabel) {
        m_voiceReplyLabel->setText(QStringLiteral("答：%1%2").arg(reply, exec));
    }
    updateVoiceAnimation();
}

void MainWindow::onAlarmLogged(const QString &line)
{
    if (m_alarmList) {
        m_alarmList->addItem(line);
        m_alarmList->scrollToBottom();
    }
}

void MainWindow::updateVoiceAnimation()
{
    if (!m_voiceAnimationLabel) {
        return;
    }
    const bool active = m_lastVoiceState == VOICE_LISTENING
        || m_lastVoiceState == VOICE_THINKING
        || m_lastVoiceState == VOICE_EXECUTING;
    if (!active) {
        m_voiceAnimationLabel->setText(QStringLiteral("○ ○ ○"));
        return;
    }
    static const char *frames[] = {"● ○ ○", "○ ● ○", "○ ○ ●", "○ ● ○"};
    m_voiceAnimationLabel->setText(QString::fromUtf8(frames[m_voiceAnimationFrame % 4]));
    ++m_voiceAnimationFrame;
}

void MainWindow::updateVisionImage(const SystemStatus &s)
{
    if (!m_visionImageLabel) {
        return;
    }

    const QDateTime now = QDateTime::currentDateTime();
    if (s.visionTimestamp.isValid() && s.visionTimestamp != m_lastVisionTimestamp) {
        m_lastVisionTimestamp = s.visionTimestamp;
        m_showVisionKeyframeUntil = now.addSecs(8);
    }

    const bool preferKeyframe = m_showVisionKeyframeUntil.isValid()
        && now < m_showVisionKeyframeUntil
        && !s.visionImagePath.isEmpty();
    QString imagePath = preferKeyframe ? s.visionImagePath : s.visionLiveImagePath;
    if (imagePath.isEmpty() && !s.visionImagePath.isEmpty()) {
        imagePath = s.visionImagePath;
    }

    QPixmap image;
    if (!imagePath.isEmpty()) {
        image.load(imagePath);
    }
    if (!image.isNull()) {
        m_visionImageLabel->setText(QString());
        m_visionImageLabel->setPixmap(
            image.scaled(m_visionImageLabel->size(), Qt::KeepAspectRatio, Qt::SmoothTransformation));
        return;
    }

    m_visionImageLabel->setPixmap(QPixmap());
    m_visionImageLabel->setText(preferKeyframe ? QStringLiteral("等待检测关键帧") : QStringLiteral("等待实时画面"));
}

void MainWindow::showModelDetails()
{
    QDialog dialog(this);
    dialog.setWindowTitle(QStringLiteral("模型结果详情"));
    dialog.resize(760, 520);

    QVBoxLayout *layout = new QVBoxLayout(&dialog);
    layout->setContentsMargins(14, 14, 14, 14);
    layout->setSpacing(10);

    QTextEdit *text = new QTextEdit;
    text->setReadOnly(true);
    text->setPlainText(m_modelDetailsText.isEmpty()
                           ? QStringLiteral("暂无模型详情。请确认 cloud_client.py 已使用 --include-debug。")
                           : m_modelDetailsText);
    text->setStyleSheet(
        QStringLiteral("QTextEdit{background:%1; color:%2; border:1px solid %3; "
                       "border-radius:8px; font-size:17px; padding:8px;}")
            .arg(kCardColor)
            .arg(kTextColor)
            .arg(kLineColor));
    layout->addWidget(text, 1);

    QDialogButtonBox *buttons = new QDialogButtonBox(QDialogButtonBox::Close);
    buttons->button(QDialogButtonBox::Close)->setText(QStringLiteral("关闭"));
    connect(buttons, &QDialogButtonBox::rejected, &dialog, &QDialog::reject);
    layout->addWidget(buttons);

    dialog.exec();
}

QString MainWindow::repoRootPath() const
{
    const QString envRoot = qEnvironmentVariable("XYLT_REPO_ROOT");
    if (!envRoot.isEmpty()) {
        QDir dir(envRoot);
        if (QFileInfo(dir.filePath(QStringLiteral("voice_llm_demo/main.py"))).isFile()) {
            return dir.absolutePath();
        }
    }

    QDir current(QDir::currentPath());
    if (QFileInfo(current.filePath(QStringLiteral("voice_llm_demo/main.py"))).isFile()) {
        return current.absolutePath();
    }

    QDir appDir(QCoreApplication::applicationDirPath());
    for (int i = 0; i < 4; ++i) {
        if (QFileInfo(appDir.filePath(QStringLiteral("voice_llm_demo/main.py"))).isFile()) {
            return appDir.absolutePath();
        }
        if (!appDir.cdUp()) {
            break;
        }
    }
    return QDir::currentPath();
}

void MainWindow::setVisionModeCloud()
{
    writeVisionModeRequest(QStringLiteral("cloud"));
}

void MainWindow::setVisionModeLocal()
{
    writeVisionModeRequest(QStringLiteral("local"));
}

void MainWindow::setVisionModeOff()
{
    writeVisionModeRequest(QStringLiteral("off"));
}

void MainWindow::writeVisionModeRequest(const QString &mode)
{
    const QString root = repoRootPath();
    QDir runtimeDir(QDir(root).filePath(QStringLiteral("runtime/vision")));
    if (!runtimeDir.exists()) {
        runtimeDir.mkpath(QStringLiteral("."));
    }
    QJsonObject payload;
    payload.insert(QStringLiteral("mode"), mode);
    payload.insert(QStringLiteral("updated_at"), QDateTime::currentDateTime().toString(Qt::ISODate));
    QFile file(runtimeDir.filePath(QStringLiteral("mode_request.json")));
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        if (m_visionSummaryLabel) {
            m_visionSummaryLabel->setText(QStringLiteral("错误：无法写入视觉模式请求文件"));
        }
        return;
    }
    file.write(QJsonDocument(payload).toJson(QJsonDocument::Compact));
    file.write("\n");
    if (m_visionModeLabel) {
        m_visionModeLabel->setText(QStringLiteral("模式：%1\n请求已写入，等待视觉服务切换").arg(mode));
    }
}

void MainWindow::requestVisionCapture()
{
    const QString root = repoRootPath();
    QDir runtimeDir(QDir(root).filePath(QStringLiteral("runtime/vision")));
    if (!runtimeDir.exists()) {
        runtimeDir.mkpath(QStringLiteral("."));
    }

    const QString requestId = QStringLiteral("qt-%1").arg(QDateTime::currentMSecsSinceEpoch());
    QJsonObject payload;
    payload.insert(QStringLiteral("type"), QStringLiteral("vision_capture_request"));
    payload.insert(QStringLiteral("request_id"), requestId);
    payload.insert(QStringLiteral("trigger"), QStringLiteral("qt_manual"));
    payload.insert(QStringLiteral("question"), QStringLiteral("Qt 手动拍照检测"));
    payload.insert(QStringLiteral("force"), true);
    payload.insert(QStringLiteral("created_at"), QDateTime::currentDateTime().toString(Qt::ISODate));

    QFile file(runtimeDir.filePath(QStringLiteral("capture_request.json")));
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        if (m_visionSummaryLabel) {
            m_visionSummaryLabel->setText(QStringLiteral("错误：无法写入拍照检测请求文件"));
        }
        return;
    }
    file.write(QJsonDocument(payload).toJson(QJsonDocument::Compact));
    file.write("\n");

    if (m_visionCaptureButton) {
        m_visionCaptureButton->setText(QStringLiteral("检测中..."));
        QTimer::singleShot(2500, this, [this]() {
            if (m_visionCaptureButton) {
                m_visionCaptureButton->setText(QStringLiteral("拍照检测"));
            }
        });
    }
    if (m_visionSummaryLabel) {
        m_visionSummaryLabel->setText(QStringLiteral("结论：已请求拍照检测，等待视觉服务返回结果。"));
    }
}

void MainWindow::toggleVoiceAssistant()
{
    if (m_voiceProcess && m_voiceProcess->state() != QProcess::NotRunning) {
        stopVoiceAssistant();
        return;
    }
    startVoiceAssistant();
}

bool MainWindow::startVoiceAssistant()
{
    if (!m_voiceProcess || m_voiceProcess->state() != QProcess::NotRunning) {
        return true;
    }

    const QString root = repoRootPath();
    QDir rootDir(root);
    const QString script = rootDir.filePath(QStringLiteral("voice_llm_demo/main.py"));
    if (!QFileInfo(script).isFile()) {
        if (m_bottomLabel) {
            m_bottomLabel->setText(QStringLiteral("语音助手启动失败：未找到 voice_llm_demo/main.py"));
        }
        return false;
    }

    QString provider = qEnvironmentVariable("VOICE_LLM_PROVIDER");
    if (provider.isEmpty()) {
        provider = QStringLiteral("doubao");
    }
    QString mqttHost = qEnvironmentVariable("VOICE_MQTT_HOST");
    if (mqttHost.isEmpty()) {
        mqttHost = QStringLiteral("127.0.0.1");
    }
    QString ackTimeout = qEnvironmentVariable("VOICE_MQTT_ACK_TIMEOUT");
    if (ackTimeout.isEmpty()) {
        ackTimeout = QStringLiteral("3");
    }
    QString maxReplyChars = qEnvironmentVariable("VOICE_MAX_REPLY_CHARS");
    if (maxReplyChars.isEmpty()) {
        maxReplyChars = QStringLiteral("180");
    }

    QString program = qEnvironmentVariable("VOICE_PYTHON");
    if (program.isEmpty()) {
#ifdef Q_OS_WIN
        program = QStringLiteral("python");
#else
        program = QStringLiteral("python3");
#endif
    }

    QStringList args;
    args << script
         << QStringLiteral("--continuous")
         << QStringLiteral("--real-llm")
         << QStringLiteral("--llm-provider") << provider
         << QStringLiteral("--assistant-state-file") << rootDir.filePath(QStringLiteral("runtime/voice_assistant_state.json"))
         << QStringLiteral("--context-status-file") << rootDir.filePath(QStringLiteral("runtime/latest_evaluate_response.json"))
         << QStringLiteral("--mqtt-control")
         << QStringLiteral("--mqtt-host") << mqttHost
         << QStringLiteral("--mqtt-ack-timeout") << ackTimeout
         << QStringLiteral("--max-reply-chars") << maxReplyChars;

    QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
    env.insert(QStringLiteral("PYTHONPATH"), root);
    env.insert(QStringLiteral("PYTHONIOENCODING"), QStringLiteral("utf-8"));
    env.insert(QStringLiteral("PYTHONUNBUFFERED"), QStringLiteral("1"));
    env.insert(QStringLiteral("VOICE_USE_REAL_LLM"), QStringLiteral("true"));
    env.insert(QStringLiteral("VOICE_LLM_PROVIDER"), provider);
    env.insert(QStringLiteral("ASR_FALLBACK_MANUAL"), QStringLiteral("false"));
    if (!env.contains(QStringLiteral("VOICE_WAKE_REQUIRED"))) {
        env.insert(QStringLiteral("VOICE_WAKE_REQUIRED"), QStringLiteral("true"));
    }
    if (!env.contains(QStringLiteral("VOICE_WAKE_WORDS"))) {
        env.insert(QStringLiteral("VOICE_WAKE_WORDS"), QStringLiteral("小龙,你好小龙,龙芯助手,小龙在吗,在吗"));
    }
    if (!env.contains(QStringLiteral("VOICE_TTS_MODE"))) {
        env.insert(QStringLiteral("VOICE_TTS_MODE"), QStringLiteral("baidu"));
    }
    m_voiceProcess->setProcessEnvironment(env);
    m_voiceProcess->setWorkingDirectory(root);
    m_voiceProcess->setProcessChannelMode(QProcess::SeparateChannels);
    m_voiceProcess->setStandardOutputFile(rootDir.filePath(QStringLiteral("runtime/voice_assistant_process.log")), QIODevice::Append);
    m_voiceProcess->setStandardErrorFile(rootDir.filePath(QStringLiteral("runtime/voice_assistant_process.log")), QIODevice::Append);

    m_voiceProcess->start(program, args);
    if (!m_voiceProcess->waitForStarted(2500)) {
        if (m_bottomLabel) {
            m_bottomLabel->setText(QStringLiteral("语音助手启动失败：请检查 python3 与依赖。"));
        }
        setVoiceButtonRunning(false);
        return false;
    }

    setVoiceButtonRunning(true);
    if (m_bottomLabel) {
        m_bottomLabel->setText(QStringLiteral("语音助手已启动：正在监听麦克风。"));
    }
    return true;
}

void MainWindow::stopVoiceAssistant()
{
    if (!m_voiceProcess || m_voiceProcess->state() == QProcess::NotRunning) {
        setVoiceButtonRunning(false);
        return;
    }
    if (m_bottomLabel) {
        m_bottomLabel->setText(QStringLiteral("语音助手正在停止..."));
    }
    m_voiceProcess->terminate();
    QTimer::singleShot(1500, this, [this]() {
        if (m_voiceProcess && m_voiceProcess->state() != QProcess::NotRunning) {
            m_voiceProcess->kill();
        }
    });
}

void MainWindow::setVoiceButtonRunning(bool running)
{
    if (!m_voiceToggleButton) {
        return;
    }
    m_voiceToggleButton->setText(running ? QStringLiteral("停止语音") : QStringLiteral("启动语音"));
}

void MainWindow::onVoiceProcessFinished(int exitCode, int exitStatus)
{
    setVoiceButtonRunning(false);
    if (!m_bottomLabel) {
        return;
    }
    if (exitStatus == QProcess::NormalExit && exitCode == 0) {
        m_bottomLabel->setText(QStringLiteral("语音助手已退出。"));
    } else {
        m_bottomLabel->setText(QStringLiteral("语音助手已停止，退出码：%1").arg(exitCode));
    }
}

void MainWindow::onVoiceProcessError()
{
    setVoiceButtonRunning(false);
    if (m_bottomLabel) {
        m_bottomLabel->setText(QStringLiteral("语音助手进程异常，请检查 Python、依赖和麦克风。"));
    }
}

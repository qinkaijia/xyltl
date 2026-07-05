#include "MainWindow.h"
#include "StatusModel.h"

#include <QFrame>
#include <QGridLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QListWidget>
#include <QVBoxLayout>
#include <QWidget>

static const char *kBgColor = "#1a1a24";
static const char *kCardColor = "#262633";
static const char *kTextColor = "#e6e6e6";
static const char *kNormalColor = "#2ecc71";
static const char *kWarningColor = "#f1c40f";
static const char *kAlarmColor = "#e74c3c";
static const char *kAccentColor = "#3aa0ff";

static const char *levelColor(int level)
{
    switch (level) {
    case LEVEL_NORMAL: return kNormalColor;
    case LEVEL_WARNING: return kWarningColor;
    case LEVEL_ALARM: return kAlarmColor;
    default: return kTextColor;
    }
}

MainWindow::MainWindow(StatusModel *model, QWidget *parent)
    : QMainWindow(parent), m_model(model)
{
    setWindowTitle(QStringLiteral("智能工业环境监测系统"));
    resize(1024, 600);
    setCentralWidget(buildCentral());

    if (m_model) {
        connect(m_model, &StatusModel::statusChanged, this, &MainWindow::onStatusChanged);
        connect(m_model, &StatusModel::alarmLogged, this, &MainWindow::onAlarmLogged);
    }
}

QFrame *MainWindow::createCard(const QString &title, QLabel **valueLabelOut)
{
    QFrame *card = new QFrame;
    card->setFrameShape(QFrame::StyledPanel);
    card->setMinimumHeight(110);

    QLabel *titleLabel = new QLabel(title);
    titleLabel->setStyleSheet(QStringLiteral("color:#9aa0b0; font-size:20px; background:transparent;"));

    QLabel *valueLabel = new QLabel(QStringLiteral("--"));
    valueLabel->setStyleSheet(
        QStringLiteral("color:%1; font-size:38px; font-weight:bold; background:transparent;").arg(kTextColor));

    QVBoxLayout *layout = new QVBoxLayout(card);
    layout->setContentsMargins(16, 12, 16, 12);
    layout->addWidget(titleLabel);
    layout->addWidget(valueLabel);
    layout->addStretch();

    card->setStyleSheet(
        QStringLiteral("QFrame{background:%1; border-radius:8px; border:2px solid #3a3a4a;}").arg(kCardColor));

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
    root->setContentsMargins(18, 14, 18, 14);
    root->setSpacing(12);

    QLabel *title = new QLabel(QStringLiteral("智能工业环境监测系统"));
    title->setAlignment(Qt::AlignCenter);
    title->setStyleSheet(
        QStringLiteral("color:%1; font-size:34px; font-weight:bold; padding:6px; background:transparent;")
            .arg(kAccentColor));
    root->addWidget(title);

    QGridLayout *grid = new QGridLayout;
    grid->setSpacing(12);

    m_tempCard = createCard(QStringLiteral("温度"), &m_tempValue);
    m_humiCard = createCard(QStringLiteral("湿度"), &m_humiValue);
    m_sysCard = createCard(QStringLiteral("系统状态"), &m_sysValue);
    m_gasCard = createCard(QStringLiteral("气体"), &m_gasValue);
    m_vibCard = createCard(QStringLiteral("振动"), &m_vibValue);
    m_cloudCard = createCard(QStringLiteral("云端"), &m_cloudValue);

    grid->addWidget(m_tempCard, 0, 0);
    grid->addWidget(m_humiCard, 0, 1);
    grid->addWidget(m_sysCard, 0, 2);
    grid->addWidget(m_gasCard, 1, 0);
    grid->addWidget(m_vibCard, 1, 1);
    grid->addWidget(m_cloudCard, 1, 2);
    root->addLayout(grid);

    m_infoLabel = new QLabel(QStringLiteral("系统就绪，等待数据刷新。"));
    m_infoLabel->setMinimumHeight(74);
    m_infoLabel->setWordWrap(true);
    m_infoLabel->setAlignment(Qt::AlignVCenter | Qt::AlignLeft);
    m_infoLabel->setStyleSheet(
        QStringLiteral("QLabel{background:%1; border-radius:8px; border:1px solid #3a3a4a; "
                       "padding:10px; font-size:18px; color:#c0c6d4;}")
            .arg(kCardColor));
    root->addWidget(m_infoLabel);

    QLabel *logTitle = new QLabel(QStringLiteral("报警日志"));
    logTitle->setStyleSheet(QStringLiteral("color:#9aa0b0; font-size:20px; background:transparent;"));
    root->addWidget(logTitle);

    m_alarmList = new QListWidget;
    m_alarmList->setStyleSheet(
        QStringLiteral("QListWidget{background:%1; border-radius:8px; border:1px solid #3a3a4a; "
                       "font-size:18px; color:#e6b0b0; padding:6px;}")
            .arg(kCardColor));
    root->addWidget(m_alarmList, 1);

    m_bottomLabel = new QLabel;
    m_bottomLabel->setAlignment(Qt::AlignCenter);
    m_bottomLabel->setStyleSheet(
        QStringLiteral("color:%1; font-size:20px; padding:6px; background:transparent;").arg(kTextColor));
    m_bottomLabel->setText(QStringLiteral("语音助手：待唤醒   |   云端：已连接"));
    root->addWidget(m_bottomLabel);

    return central;
}

void MainWindow::applyLevelStyle(QFrame *card, QLabel *value, int level)
{
    const char *color = levelColor(level);
    card->setStyleSheet(
        QStringLiteral("QFrame{background:%1; border-radius:8px; border:2px solid %2;}").arg(kCardColor).arg(color));
    value->setStyleSheet(
        QStringLiteral("color:%1; font-size:38px; font-weight:bold; background:transparent;").arg(color));
}

void MainWindow::onStatusChanged(const SystemStatus &s)
{
    m_tempValue->setText(QStringLiteral("%1 C").arg(s.temperature, 0, 'f', 1));
    m_humiValue->setText(QStringLiteral("%1 %").arg(s.humidity, 0, 'f', 0));

    m_sysValue->setText(s.statusText.isEmpty() ? levelToText(s.alarmLevel) : s.statusText);
    applyLevelStyle(m_sysCard, m_sysValue, s.alarmLevel);

    m_gasValue->setText(levelToText(s.gasLevel));
    applyLevelStyle(m_gasCard, m_gasValue, s.gasLevel);

    m_vibValue->setText(levelToText(s.vibrationLevel));
    applyLevelStyle(m_vibCard, m_vibValue, s.vibrationLevel);

    m_cloudValue->setText(cloudStateToText(s.cloudConnected));
    applyLevelStyle(m_cloudCard, m_cloudValue, s.cloudConnected ? LEVEL_NORMAL : LEVEL_ALARM);

    const QString reason = s.alarmMessage.isEmpty() ? QStringLiteral("暂无异常说明") : s.alarmMessage;
    const QString suggestion = s.suggestion.isEmpty() ? QStringLiteral("保持常规监测") : s.suggestion;
    const QString latency = s.cloudLatencyMs >= 0 ? QStringLiteral("%1 ms").arg(s.cloudLatencyMs) : QStringLiteral("--");
    const QString models = s.modelSource.isEmpty() ? QStringLiteral("--") : s.modelSource;
    m_infoLabel->setText(
        QStringLiteral("%1  设备:%2  温度:%3 C  湿度:%4 %  模式:%5  延迟:%6  模型:%7\n原因:%8\n建议:%9")
            .arg(s.timestamp.toString("HH:mm:ss"))
            .arg(s.deviceId.isEmpty() ? QStringLiteral("--") : s.deviceId)
            .arg(s.temperature, 0, 'f', 1)
            .arg(s.humidity, 0, 'f', 0)
            .arg(s.analysisMode.isEmpty() ? QStringLiteral("mock") : s.analysisMode)
            .arg(latency)
            .arg(models)
            .arg(reason)
            .arg(suggestion));

    m_bottomLabel->setText(
        QStringLiteral("语音助手:%1   |   云端:%2   |   播报:%3")
            .arg(voiceStateToText(s.voiceState))
            .arg(cloudStateToText(s.cloudConnected))
            .arg(s.voiceText.isEmpty() ? QStringLiteral("无") : s.voiceText.left(36)));
}

void MainWindow::onAlarmLogged(const QString &line)
{
    m_alarmList->addItem(line);
    m_alarmList->scrollToBottom();
}

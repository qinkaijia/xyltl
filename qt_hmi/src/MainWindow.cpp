#include "MainWindow.h"
#include "StatusModel.h"

#include <QDialog>
#include <QDialogButtonBox>
#include <QFrame>
#include <QGridLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QListWidget>
#include <QPushButton>
#include <QTextEdit>
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

MainWindow::MainWindow(StatusModel *model, bool compactMode, QWidget *parent)
    : QMainWindow(parent), m_model(model), m_compactMode(compactMode)
{
    setWindowTitle(QStringLiteral("智能工业环境监测系统"));
    resize(m_compactMode ? QSize(780, 450) : QSize(1024, 600));
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
    card->setMinimumHeight(m_compactMode ? 70 : 110);

    QLabel *titleLabel = new QLabel(title);
    titleLabel->setStyleSheet(
        QStringLiteral("color:#9aa0b0; font-size:%1px; background:transparent;")
            .arg(m_compactMode ? 15 : 20));

    QLabel *valueLabel = new QLabel(QStringLiteral("--"));
    valueLabel->setStyleSheet(
        QStringLiteral("color:%1; font-size:%2px; font-weight:bold; background:transparent;")
            .arg(kTextColor)
            .arg(m_compactMode ? 26 : 38));

    QVBoxLayout *layout = new QVBoxLayout(card);
    layout->setContentsMargins(m_compactMode ? 10 : 16, m_compactMode ? 8 : 12,
                               m_compactMode ? 10 : 16, m_compactMode ? 8 : 12);
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
    root->setContentsMargins(m_compactMode ? 8 : 18, m_compactMode ? 6 : 14,
                             m_compactMode ? 8 : 18, m_compactMode ? 6 : 14);
    root->setSpacing(m_compactMode ? 6 : 12);

    QHBoxLayout *topBar = new QHBoxLayout;
    topBar->setSpacing(12);

    QLabel *title = new QLabel(QStringLiteral("智能工业环境监测系统"));
    title->setAlignment(Qt::AlignCenter);
    title->setStyleSheet(
        QStringLiteral("color:%1; font-size:%2px; font-weight:bold; padding:%3px; background:transparent;")
            .arg(kAccentColor)
            .arg(m_compactMode ? 24 : 34)
            .arg(m_compactMode ? 2 : 6));
    topBar->addStretch();
    topBar->addWidget(title, 1);

    m_modelDetailsButton = new QPushButton(QStringLiteral("模型详情"));
    m_modelDetailsButton->setMinimumHeight(m_compactMode ? 34 : 42);
    m_modelDetailsButton->setEnabled(false);
    m_modelDetailsButton->setStyleSheet(
        QStringLiteral("QPushButton{background:#203a54; color:#e6f2ff; border:1px solid %1; "
                       "border-radius:6px; padding:4px 10px; font-size:%2px;}"
                       "QPushButton:disabled{background:#2b2f3a; color:#777d8c; border-color:#3a3a4a;}")
            .arg(kAccentColor)
            .arg(m_compactMode ? 15 : 18));
    connect(m_modelDetailsButton, &QPushButton::clicked, this, &MainWindow::showModelDetails);
    topBar->addWidget(m_modelDetailsButton);

    root->addLayout(topBar);

    QGridLayout *grid = new QGridLayout;
    grid->setSpacing(m_compactMode ? 6 : 12);

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
    m_infoLabel->setMinimumHeight(m_compactMode ? 58 : 74);
    m_infoLabel->setWordWrap(true);
    m_infoLabel->setAlignment(Qt::AlignVCenter | Qt::AlignLeft);
    m_infoLabel->setStyleSheet(
        QStringLiteral("QLabel{background:%1; border-radius:8px; border:1px solid #3a3a4a; "
                       "padding:%2px; font-size:%3px; color:#c0c6d4;}")
            .arg(kCardColor)
            .arg(m_compactMode ? 6 : 10)
            .arg(m_compactMode ? 14 : 18));
    root->addWidget(m_infoLabel);

    QLabel *logTitle = new QLabel(QStringLiteral("报警日志"));
    logTitle->setStyleSheet(
        QStringLiteral("color:#9aa0b0; font-size:%1px; background:transparent;")
            .arg(m_compactMode ? 15 : 20));
    root->addWidget(logTitle);

    m_alarmList = new QListWidget;
    m_alarmList->setStyleSheet(
        QStringLiteral("QListWidget{background:%1; border-radius:8px; border:1px solid #3a3a4a; "
                       "font-size:%2px; color:#e6b0b0; padding:%3px;}")
            .arg(kCardColor)
            .arg(m_compactMode ? 13 : 18)
            .arg(m_compactMode ? 4 : 6));
    if (m_compactMode) {
        m_alarmList->setMaximumHeight(68);
    }
    root->addWidget(m_alarmList, m_compactMode ? 0 : 1);

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

void MainWindow::applyLevelStyle(QFrame *card, QLabel *value, int level)
{
    const char *color = levelColor(level);
    card->setStyleSheet(
        QStringLiteral("QFrame{background:%1; border-radius:8px; border:2px solid %2;}").arg(kCardColor).arg(color));
    value->setStyleSheet(
        QStringLiteral("color:%1; font-size:%2px; font-weight:bold; background:transparent;")
            .arg(color)
            .arg(m_compactMode ? 26 : 38));
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
    m_modelDetailsText = s.modelDetails;
    if (m_modelDetailsButton) {
        m_modelDetailsButton->setEnabled(!m_modelDetailsText.isEmpty());
    }
    if (m_compactMode) {
        m_infoLabel->setText(
            QStringLiteral("%1  设备:%2  模式:%3  延迟:%4  模型:%5\n原因:%6\n建议:%7")
                .arg(s.timestamp.toString("HH:mm:ss"))
                .arg(s.deviceId.isEmpty() ? QStringLiteral("--") : s.deviceId)
                .arg(s.analysisMode.isEmpty() ? QStringLiteral("mock") : s.analysisMode)
                .arg(latency)
                .arg(models)
                .arg(reason)
                .arg(suggestion));
    } else {
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
    }

    m_bottomLabel->setText(
        QStringLiteral("语音助手:%1   |   云端:%2   |   播报:%3")
            .arg(voiceStateToText(s.voiceState))
            .arg(cloudStateToText(s.cloudConnected))
            .arg(s.voiceText.isEmpty() ? QStringLiteral("无") : s.voiceText.left(m_compactMode ? 24 : 36)));
}

void MainWindow::onAlarmLogged(const QString &line)
{
    m_alarmList->addItem(line);
    m_alarmList->scrollToBottom();
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
        QStringLiteral("QTextEdit{background:%1; color:%2; border:1px solid #3a3a4a; "
                       "border-radius:8px; font-size:17px; padding:8px;}").arg(kCardColor).arg(kTextColor));
    layout->addWidget(text, 1);

    QDialogButtonBox *buttons = new QDialogButtonBox(QDialogButtonBox::Close);
    buttons->button(QDialogButtonBox::Close)->setText(QStringLiteral("关闭"));
    connect(buttons, &QDialogButtonBox::rejected, &dialog, &QDialog::reject);
    layout->addWidget(buttons);

    dialog.exec();
}

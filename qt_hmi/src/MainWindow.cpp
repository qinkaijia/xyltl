#include "MainWindow.h"
#include "StatusModel.h"

#include <QWidget>
#include <QLabel>
#include <QFrame>
#include <QListWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGridLayout>

// ---- 配色常量（深色工业风）----
static const char *kBgColor       = "#1a1a24";   // 窗口背景
static const char *kCardColor     = "#262633";   // 卡片背景
static const char *kTextColor     = "#e6e6e6";   // 普通文字
static const char *kNormalColor   = "#2ecc71";   // 正常-绿
static const char *kWarningColor  = "#f1c40f";   // 预警-黄/橙
static const char *kAlarmColor    = "#e74c3c";   // 报警-红
static const char *kAccentColor   = "#3aa0ff";   // 强调-蓝

// 根据状态等级返回对应颜色
static const char *levelColor(int level)
{
    switch (level) {
    case LEVEL_NORMAL:  return kNormalColor;
    case LEVEL_WARNING: return kWarningColor;
    case LEVEL_ALARM:   return kAlarmColor;
    default:            return kTextColor;
    }
}

MainWindow::MainWindow(StatusModel *model, QWidget *parent)
    : QMainWindow(parent), m_model(model)
{
    setWindowTitle(QStringLiteral("智能工业环境监测系统"));
    resize(1024, 600);   // 默认窗口大小，适配小屏

    setCentralWidget(buildCentral());

    // 订阅模型信号，界面只依赖 StatusModel
    if (m_model) {
        connect(m_model, &StatusModel::statusChanged,
                this, &MainWindow::onStatusChanged);
        connect(m_model, &StatusModel::alarmLogged,
                this, &MainWindow::onAlarmLogged);
    }
}

// 创建一张状态卡片：上方标题 + 下方大号数值
QFrame *MainWindow::createCard(const QString &title, QLabel **valueLabelOut)
{
    QFrame *card = new QFrame;
    card->setFrameShape(QFrame::StyledPanel);
    card->setMinimumHeight(110);

    QLabel *titleLabel = new QLabel(title);
    titleLabel->setStyleSheet(
        QStringLiteral("color:#9aa0b0; font-size:20px; background:transparent;"));

    QLabel *valueLabel = new QLabel(QStringLiteral("--"));
    valueLabel->setStyleSheet(
        QStringLiteral("color:%1; font-size:38px; font-weight:bold; background:transparent;")
            .arg(kTextColor));

    QVBoxLayout *lay = new QVBoxLayout(card);
    lay->setContentsMargins(16, 12, 16, 12);
    lay->addWidget(titleLabel);
    lay->addWidget(valueLabel);
    lay->addStretch();

    // 默认边框（正常态由后续 applyLevelStyle 覆盖）
    card->setStyleSheet(
        QStringLiteral("QFrame{background:%1; border-radius:10px; border:2px solid #3a3a4a;}")
            .arg(kCardColor));

    if (valueLabelOut) *valueLabelOut = valueLabel;
    return card;
}

QWidget *MainWindow::buildCentral()
{
    QWidget *central = new QWidget;
    central->setStyleSheet(
        QStringLiteral("background:%1; color:%2;").arg(kBgColor).arg(kTextColor));

    QVBoxLayout *root = new QVBoxLayout(central);
    root->setContentsMargins(18, 14, 18, 14);
    root->setSpacing(12);

    // ---- 顶部标题 ----
    QLabel *title = new QLabel(QStringLiteral("智能工业环境监测系统"));
    title->setAlignment(Qt::AlignCenter);
    title->setStyleSheet(
        QStringLiteral("color:%1; font-size:34px; font-weight:bold; "
                       "padding:6px; background:transparent;").arg(kAccentColor));
    root->addWidget(title);

    // ---- 卡片网格：2 行 x 3 列 ----
    QGridLayout *grid = new QGridLayout;
    grid->setSpacing(12);

    m_tempCard  = createCard(QStringLiteral("温度"),     &m_tempValue);
    m_humiCard  = createCard(QStringLiteral("湿度"),     &m_humiValue);
    m_sysCard   = createCard(QStringLiteral("系统状态"), &m_sysValue);
    m_gasCard   = createCard(QStringLiteral("气体"),     &m_gasValue);
    m_vibCard   = createCard(QStringLiteral("振动"),     &m_vibValue);
    m_cloudCard = createCard(QStringLiteral("云端"),     &m_cloudValue);

    grid->addWidget(m_tempCard,  0, 0);
    grid->addWidget(m_humiCard,  0, 1);
    grid->addWidget(m_sysCard,   0, 2);
    grid->addWidget(m_gasCard,   1, 0);
    grid->addWidget(m_vibCard,   1, 1);
    grid->addWidget(m_cloudCard, 1, 2);
    root->addLayout(grid);

    // ---- 中部：状态信息/趋势占位 ----
    m_infoLabel = new QLabel(QStringLiteral("系统就绪，等待数据刷新…"));
    m_infoLabel->setMinimumHeight(60);
    m_infoLabel->setAlignment(Qt::AlignVCenter | Qt::AlignLeft);
    m_infoLabel->setStyleSheet(
        QStringLiteral("QLabel{background:%1; border-radius:10px; "
                       "border:1px solid #3a3a4a; padding:10px; "
                       "font-size:20px; color:#c0c6d4;}").arg(kCardColor));
    root->addWidget(m_infoLabel);

    // ---- 报警日志区域 ----
    QLabel *logTitle = new QLabel(QStringLiteral("报警日志"));
    logTitle->setStyleSheet(
        QStringLiteral("color:#9aa0b0; font-size:20px; background:transparent;"));
    root->addWidget(logTitle);

    m_alarmList = new QListWidget;
    m_alarmList->setStyleSheet(
        QStringLiteral("QListWidget{background:%1; border-radius:10px; "
                       "border:1px solid #3a3a4a; font-size:18px; "
                       "color:#e6b0b0; padding:6px;}").arg(kCardColor));
    root->addWidget(m_alarmList, 1);   // 占据剩余伸展空间

    // ---- 底部状态栏：语音助手 | 云端 ----
    m_bottomLabel = new QLabel;
    m_bottomLabel->setAlignment(Qt::AlignCenter);
    m_bottomLabel->setStyleSheet(
        QStringLiteral("color:%1; font-size:20px; padding:6px; "
                       "background:transparent;").arg(kTextColor));
    m_bottomLabel->setText(QStringLiteral("语音助手：待唤醒   |   云端：已连接"));
    root->addWidget(m_bottomLabel);

    return central;
}

// 根据等级设置卡片边框与数值文字颜色
void MainWindow::applyLevelStyle(QFrame *card, QLabel *value, int level)
{
    const char *color = levelColor(level);
    card->setStyleSheet(
        QStringLiteral("QFrame{background:%1; border-radius:10px; border:2px solid %2;}")
            .arg(kCardColor).arg(color));
    value->setStyleSheet(
        QStringLiteral("color:%1; font-size:38px; font-weight:bold; background:transparent;")
            .arg(color));
}

void MainWindow::onStatusChanged(const SystemStatus &s)
{
    // 温度、湿度：数值刷新，颜色保持中性（信息量卡片）
    m_tempValue->setText(QStringLiteral("%1 ℃").arg(s.temperature, 0, 'f', 1));
    m_humiValue->setText(QStringLiteral("%1 %").arg(s.humidity, 0, 'f', 0));

    // 系统总体状态、气体、振动：按等级配色
    m_sysValue->setText(levelToText(s.alarmLevel));
    applyLevelStyle(m_sysCard, m_sysValue, s.alarmLevel);

    m_gasValue->setText(levelToText(s.gasLevel));
    applyLevelStyle(m_gasCard, m_gasValue, s.gasLevel);

    m_vibValue->setText(levelToText(s.vibrationLevel));
    applyLevelStyle(m_vibCard, m_vibValue, s.vibrationLevel);

    // 云端：已连接=绿，已断开=红
    m_cloudValue->setText(cloudStateToText(s.cloudConnected));
    applyLevelStyle(m_cloudCard, m_cloudValue,
                    s.cloudConnected ? LEVEL_NORMAL : LEVEL_ALARM);

    // 中部信息区：显示实时快照概要
    m_infoLabel->setText(
        QStringLiteral("更新时间 %1    温度 %2 ℃    湿度 %3 %    系统状态：%4")
            .arg(s.timestamp.toString("HH:mm:ss"))
            .arg(s.temperature, 0, 'f', 1)
            .arg(s.humidity, 0, 'f', 0)
            .arg(levelToText(s.alarmLevel)));

    // 底部状态栏：语音助手 + 云端
    m_bottomLabel->setText(
        QStringLiteral("语音助手：%1   |   云端：%2")
            .arg(voiceStateToText(s.voiceState))
            .arg(cloudStateToText(s.cloudConnected)));
}

void MainWindow::onAlarmLogged(const QString &line)
{
    m_alarmList->addItem(line);
    m_alarmList->scrollToBottom();   // 始终显示最新一条
}

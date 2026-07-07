#include "FinalStatusDataProvider.h"

#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QJsonValue>
#include <QStringList>
#include <QTimer>

static const int kPollIntervalMs = 1000;

static QString valueText(const QJsonObject &obj, const QString &key, const QString &fallback = QStringLiteral("--"))
{
    const QJsonValue value = obj.value(key);
    if (value.isString()) {
        const QString text = value.toString();
        return text.isEmpty() ? fallback : text;
    }
    if (value.isDouble()) {
        return QString::number(value.toDouble(), 'f', 2);
    }
    if (value.isBool()) {
        return value.toBool() ? QStringLiteral("true") : QStringLiteral("false");
    }
    return fallback;
}

static QString textArray(const QJsonValue &value)
{
    if (!value.isArray()) {
        return QStringLiteral("--");
    }
    QStringList items;
    const QJsonArray array = value.toArray();
    for (const QJsonValue &item : array) {
        if (item.isString() && !item.toString().isEmpty()) {
            items.append(item.toString());
        }
    }
    return items.isEmpty() ? QStringLiteral("--") : items.join(QStringLiteral("；"));
}

static QStringList stringArray(const QJsonValue &value)
{
    QStringList items;
    if (!value.isArray()) {
        return items;
    }
    const QJsonArray array = value.toArray();
    for (const QJsonValue &item : array) {
        if (item.isString() && !item.toString().isEmpty()) {
            items.append(item.toString());
        }
    }
    return items;
}

static QString buildModelDetails(const QJsonObject &root, const QJsonObject &status)
{
    QStringList lines;
    lines.append(QStringLiteral("状态概览"));
    lines.append(QStringLiteral("设备：%1").arg(valueText(status, QStringLiteral("device_id"))));
    lines.append(QStringLiteral("等级：%1（%2）")
                     .arg(status.value(QStringLiteral("alarm_level")).toInt(LEVEL_NORMAL))
                     .arg(valueText(status, QStringLiteral("status_text"),
                                    levelToText(status.value(QStringLiteral("alarm_level")).toInt(LEVEL_NORMAL)))));
    lines.append(QStringLiteral("分析模式：%1").arg(valueText(status, QStringLiteral("analysis_mode"))));
    lines.append(QStringLiteral("原因：%1").arg(valueText(status, QStringLiteral("reason"))));
    lines.append(QStringLiteral("建议：%1").arg(valueText(status, QStringLiteral("suggestion"))));

    const QJsonObject debug = root.value(QStringLiteral("debug")).toObject();
    if (debug.isEmpty()) {
        lines.append(QString());
        lines.append(QStringLiteral("调试信息：当前响应未包含 debug 字段。"));
        return lines.join(QStringLiteral("\n"));
    }

    if (debug.value(QStringLiteral("client")).isObject()) {
        const QJsonObject client = debug.value(QStringLiteral("client")).toObject();
        lines.append(QString());
        lines.append(QStringLiteral("云端请求"));
        lines.append(QStringLiteral("结果：%1  延迟：%2 ms  地址：%3")
                         .arg(client.value(QStringLiteral("ok")).toBool(false) ? QStringLiteral("成功")
                                                                                : QStringLiteral("失败"))
                         .arg(client.value(QStringLiteral("elapsed_ms")).toInt(-1))
                         .arg(valueText(client, QStringLiteral("base_url"))));
        const QString error = client.value(QStringLiteral("error")).toString();
        if (!error.isEmpty()) {
            lines.append(QStringLiteral("错误：%1").arg(error));
        }
    }

    if (debug.value(QStringLiteral("router")).isObject()) {
        const QJsonObject router = debug.value(QStringLiteral("router")).toObject();
        lines.append(QString());
        lines.append(QStringLiteral("模型路由"));
        lines.append(QStringLiteral("选中模型：%1")
                         .arg(stringArray(router.value(QStringLiteral("selected_models"))).join(QStringLiteral(","))));
        lines.append(QStringLiteral("仲裁模型：%1").arg(valueText(router, QStringLiteral("judge_model"))));
        lines.append(QStringLiteral("路由原因：%1").arg(valueText(router, QStringLiteral("reason"))));
    }

    if (debug.value(QStringLiteral("rule_result")).isObject()) {
        const QJsonObject rule = debug.value(QStringLiteral("rule_result")).toObject();
        lines.append(QString());
        lines.append(QStringLiteral("本地规则"));
        lines.append(QStringLiteral("等级：%1  命中：%2")
                         .arg(rule.value(QStringLiteral("alarm_level")).toInt(LEVEL_NORMAL))
                         .arg(stringArray(rule.value(QStringLiteral("rule_hits"))).join(QStringLiteral(","))));
        lines.append(QStringLiteral("规则原因：%1").arg(valueText(rule, QStringLiteral("reason"))));
    }

    lines.append(QString());
    lines.append(QStringLiteral("模型输出"));
    if (debug.value(QStringLiteral("model_results")).isArray()) {
        const QJsonArray models = debug.value(QStringLiteral("model_results")).toArray();
        if (models.isEmpty()) {
            lines.append(QStringLiteral("无模型输出。"));
        }
        int index = 1;
        for (const QJsonValue &value : models) {
            if (!value.isObject()) {
                continue;
            }
            const QJsonObject model = value.toObject();
            lines.append(QStringLiteral("[%1] %2  角色：%3  等级：%4  置信度：%5")
                             .arg(index++)
                             .arg(valueText(model, QStringLiteral("model_name")))
                             .arg(valueText(model, QStringLiteral("role")))
                             .arg(model.value(QStringLiteral("alarm_level")).toInt(LEVEL_NORMAL))
                             .arg(model.value(QStringLiteral("confidence")).toDouble(0.0), 0, 'f', 2));
            lines.append(QStringLiteral("摘要：%1").arg(valueText(model, QStringLiteral("risk_summary"))));
            lines.append(QStringLiteral("可能原因：%1").arg(textArray(model.value(QStringLiteral("possible_causes")))));
            lines.append(QStringLiteral("建议：%1").arg(valueText(model, QStringLiteral("suggestion"))));
            const QString error = model.value(QStringLiteral("error")).toString();
            if (!error.isEmpty()) {
                lines.append(QStringLiteral("错误：%1").arg(error));
            }
        }
    } else {
        lines.append(QStringLiteral("当前响应未包含 model_results。"));
    }

    if (debug.value(QStringLiteral("judge_result")).isObject()) {
        const QJsonObject judge = debug.value(QStringLiteral("judge_result")).toObject();
        lines.append(QString());
        lines.append(QStringLiteral("仲裁结果"));
        lines.append(QStringLiteral("等级：%1  置信度：%2")
                         .arg(judge.value(QStringLiteral("alarm_level")).toInt(LEVEL_NORMAL))
                         .arg(judge.value(QStringLiteral("confidence")).toDouble(0.0), 0, 'f', 2));
        lines.append(QStringLiteral("主因：%1").arg(valueText(judge, QStringLiteral("main_reason"))));
        lines.append(QStringLiteral("建议：%1").arg(valueText(judge, QStringLiteral("suggestion"))));
        lines.append(QStringLiteral("播报：%1").arg(valueText(judge, QStringLiteral("voice_text"))));
    }

    return lines.join(QStringLiteral("\n"));
}

FinalStatusDataProvider::FinalStatusDataProvider(const QString &statusFile, QObject *parent)
    : IDataProvider(parent), m_statusFile(statusFile)
{
    m_timer = new QTimer(this);
    m_timer->setInterval(kPollIntervalMs);
    connect(m_timer, &QTimer::timeout, this, &FinalStatusDataProvider::poll);
}

FinalStatusDataProvider::~FinalStatusDataProvider() = default;

void FinalStatusDataProvider::start()
{
    if (!m_timer->isActive()) {
        m_timer->start();
    }
    poll();
}

void FinalStatusDataProvider::stop()
{
    m_timer->stop();
}

void FinalStatusDataProvider::poll()
{
    QFileInfo info(m_statusFile);
    if (!info.exists() || !info.isFile()) {
        return;
    }
    if (info.lastModified() == m_lastModified) {
        return;
    }

    SystemStatus status;
    if (loadStatus(&status)) {
        m_lastModified = info.lastModified();
        emit statusUpdated(status);
    }
}

bool FinalStatusDataProvider::loadStatus(SystemStatus *status)
{
    QFile file(m_statusFile);
    if (!file.open(QIODevice::ReadOnly)) {
        return false;
    }

    const QJsonDocument doc = QJsonDocument::fromJson(file.readAll());
    if (!doc.isObject()) {
        return false;
    }

    const QJsonObject root = doc.object();
    QJsonObject obj = root;
    if (root.contains(QStringLiteral("final_status")) && root.value(QStringLiteral("final_status")).isObject()) {
        obj = root.value(QStringLiteral("final_status")).toObject();
    }

    status->deviceId = obj.value(QStringLiteral("device_id")).toString();
    status->temperature = obj.value(QStringLiteral("temperature")).toDouble();
    status->humidity = obj.value(QStringLiteral("humidity")).toDouble();
    status->gasValue = obj.value(QStringLiteral("gas")).toDouble();
    status->vibrationValue = obj.value(QStringLiteral("vibration")).toDouble();
    status->currentValue = obj.value(QStringLiteral("current")).toDouble();
    status->alarmLevel = obj.value(QStringLiteral("alarm_level")).toInt(LEVEL_NORMAL);
    status->statusText = obj.value(QStringLiteral("status_text")).toString(levelToText(status->alarmLevel));
    status->cloudConnected = obj.value(QStringLiteral("cloud_connected")).toBool(true);
    status->alarmMessage = obj.value(QStringLiteral("reason")).toString();
    status->suggestion = obj.value(QStringLiteral("suggestion")).toString();
    status->voiceText = obj.value(QStringLiteral("voice_text")).toString();
    status->analysisMode = obj.value(QStringLiteral("analysis_mode")).toString();
    status->modelDetails = buildModelDetails(root, obj);
    if (root.value(QStringLiteral("debug")).isObject()) {
        const QJsonObject debug = root.value(QStringLiteral("debug")).toObject();
        if (debug.value(QStringLiteral("client")).isObject()) {
            status->cloudLatencyMs = debug.value(QStringLiteral("client")).toObject()
                                         .value(QStringLiteral("elapsed_ms")).toInt(-1);
        }
        if (debug.value(QStringLiteral("model_results")).isArray()) {
            const QJsonArray models = debug.value(QStringLiteral("model_results")).toArray();
            QStringList names;
            for (const QJsonValue &value : models) {
                if (value.isObject()) {
                    const QString name = value.toObject().value(QStringLiteral("model_name")).toString();
                    if (!name.isEmpty()) {
                        names.append(name);
                    }
                }
            }
            status->modelSource = names.join(QStringLiteral(","));
        }
    }

    const QString timestampText = obj.value(QStringLiteral("timestamp")).toString();
    status->timestamp = QDateTime::fromString(timestampText, Qt::ISODate);
    if (!status->timestamp.isValid()) {
        status->timestamp = QDateTime::currentDateTime();
    }

    status->gasLevel = levelFromHighThreshold(status->gasValue, 0.3, 0.6);
    status->vibrationLevel = levelFromHighThreshold(status->vibrationValue, 1.5, 2.5);
    return true;
}

int FinalStatusDataProvider::levelFromHighThreshold(double value, double warning, double alarm)
{
    if (value >= alarm) {
        return LEVEL_ALARM;
    }
    if (value >= warning) {
        return LEVEL_WARNING;
    }
    return LEVEL_NORMAL;
}

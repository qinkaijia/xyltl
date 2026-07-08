#ifndef FINALSTATUSDATAPROVIDER_H
#define FINALSTATUSDATAPROVIDER_H

#include "IDataProvider.h"

#include <QDateTime>
#include <QString>

class QTimer;

class FinalStatusDataProvider : public IDataProvider
{
    Q_OBJECT
public:
    explicit FinalStatusDataProvider(
        const QString &statusFile,
        const QString &voiceFile = QString(),
        const QString &visionFile = QString(),
        const QString &visionLiveFile = QString(),
        QObject *parent = nullptr);
    ~FinalStatusDataProvider() override;

    void start() override;
    void stop() override;

private slots:
    void poll();

private:
    bool loadStatus(SystemStatus *status);
    void loadVoiceStatus(SystemStatus *status);
    void loadVisionStatus(SystemStatus *status);
    static int voiceStateFromText(const QString &state);
    static int levelFromHighThreshold(double value, double warning, double alarm);

    QString m_statusFile;
    QString m_voiceFile;
    QString m_visionFile;
    QString m_visionLiveFile;
    QTimer *m_timer = nullptr;
    QDateTime m_lastModified;
    QDateTime m_lastVoiceModified;
    QDateTime m_lastVisionModified;
    QDateTime m_lastVisionLiveModified;
};

#endif // FINALSTATUSDATAPROVIDER_H

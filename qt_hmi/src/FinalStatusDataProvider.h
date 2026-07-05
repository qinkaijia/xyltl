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
    explicit FinalStatusDataProvider(const QString &statusFile, QObject *parent = nullptr);
    ~FinalStatusDataProvider() override;

    void start() override;
    void stop() override;

private slots:
    void poll();

private:
    bool loadStatus(SystemStatus *status);
    static int levelFromHighThreshold(double value, double warning, double alarm);

    QString m_statusFile;
    QTimer *m_timer = nullptr;
    QDateTime m_lastModified;
};

#endif // FINALSTATUSDATAPROVIDER_H

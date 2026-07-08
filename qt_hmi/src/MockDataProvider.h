#ifndef MOCKDATAPROVIDER_H
#define MOCKDATAPROVIDER_H

#include "IDataProvider.h"

class QTimer;

class MockDataProvider : public IDataProvider
{
    Q_OBJECT
public:
    explicit MockDataProvider(QObject *parent = nullptr);
    ~MockDataProvider() override;

    void start() override;
    void stop() override;

private slots:
    void generate();

private:
    QTimer *m_timer = nullptr;
    double m_temperature = 26.0;
    double m_humidity = 55.0;
    double m_gas = 0.12;
    double m_vibration = 0.5;
    double m_tvoc = 120.0;
    double m_eco2 = 450.0;
    double m_mq3Value = 0.12;
    double m_riskScore = 8.0;
    bool m_flameDetected = false;
    bool m_cloud = true;
};

#endif // MOCKDATAPROVIDER_H

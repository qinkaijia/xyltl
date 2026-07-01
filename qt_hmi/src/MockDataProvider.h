#ifndef MOCKDATAPROVIDER_H
#define MOCKDATAPROVIDER_H

#include "IDataProvider.h"

class QTimer;

// ============================================================================
// MockDataProvider —— 模拟数据源
//
// 每 1 秒产生一份 SystemStatus：
//   - 温度、湿度在合理范围内随机波动；
//   - 气体、振动偶尔进入预警/报警；
//   - 云端连接偶尔断开再恢复；
//   - 语音状态在 待唤醒/已唤醒/识别中 之间变化；
//   - 出现预警/报警时填写 alarmMessage，供上层写入报警日志。
//
// 本类不依赖任何真实硬件，可在虚拟机上独立运行、独立测试。
// ============================================================================
class MockDataProvider : public IDataProvider
{
    Q_OBJECT
public:
    explicit MockDataProvider(QObject *parent = nullptr);
    ~MockDataProvider() override;

    void start() override;
    void stop() override;

private slots:
    // 定时器触发，生成并发出一份新的模拟状态
    void generate();

private:
    QTimer *m_timer = nullptr;

    // 内部保存上一次的连续量，使数据平滑波动而非跳变
    double m_temperature = 26.0;
    double m_humidity    = 55.0;
    bool   m_cloud       = true;
};

#endif // MOCKDATAPROVIDER_H

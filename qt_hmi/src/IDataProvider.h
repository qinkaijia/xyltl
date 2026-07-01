#ifndef IDATAPROVIDER_H
#define IDATAPROVIDER_H

#include <QObject>
#include "SystemStatus.h"

// ============================================================================
// IDataProvider —— 系统状态数据源抽象接口
//
// 设计目的：
//   把“数据来源”与“界面显示”彻底解耦。界面只依赖本接口，
//   不关心数据是模拟生成、来自 JSON 文件、Socket 还是真实传感器。
//
// 后续可扩展的实现（无需改动界面代码）：
//   - MockDataProvider     ：模拟数据（当前阶段）
//   - JsonDataProvider     ：读取本地 JSON 文件回放
//   - SocketDataProvider   ：通过 TCP/UDP 接收板间/云端数据
//   - RealSensorDataProvider：对接真实传感器采集
//
// 用法：
//   继承本类，实现 start()/stop()，在有新数据时 emit statusUpdated(status)。
// ============================================================================
class IDataProvider : public QObject
{
    Q_OBJECT
public:
    explicit IDataProvider(QObject *parent = nullptr) : QObject(parent) {}
    ~IDataProvider() override = default;

    // 启动数据采集/生成（例如启动定时器、打开连接）
    virtual void start() = 0;

    // 停止数据采集/生成
    virtual void stop() = 0;

signals:
    // 每当有一份新的系统状态可用时发出。界面/模型监听此信号刷新。
    void statusUpdated(const SystemStatus &status);
};

#endif // IDATAPROVIDER_H

#include <QApplication>
#include <QStringList>

#include "SystemStatus.h"
#include "MainWindow.h"
#include "StatusModel.h"
#include "MockDataProvider.h"

// ============================================================================
// 程序入口
//
// 运行模式（通过命令行参数控制）：
//   ./display_qt_app                普通桌面窗口模式（虚拟机开发用）
//   ./display_qt_app --fullscreen   全屏模式（板端运行用）
//
// 数据来源当前为 MockDataProvider（模拟数据）。后续接入真实数据源时，
// 只需在此处把 MockDataProvider 换成对应的 IDataProvider 实现即可，
// 界面与模型代码无需改动。
// ============================================================================
int main(int argc, char *argv[])
{
    QApplication app(argc, argv);

    // 让 SystemStatus 可用于队列连接（为将来跨线程数据源预留）
    qRegisterMetaType<SystemStatus>("SystemStatus");

    // ---- 组装：数据源 -> 模型 -> 界面 ----
    MockDataProvider provider;          // 当前阶段：模拟数据源
    StatusModel      model;
    model.setProvider(&provider);

    MainWindow window(&model);

    // ---- 解析命令行参数，决定显示模式 ----
    const QStringList args = app.arguments();
    if (args.contains(QStringLiteral("--fullscreen"))) {
        window.showFullScreen();        // 板端全屏
    } else {
        window.show();                  // 桌面窗口
    }

    // ---- 启动数据源，开始刷新 ----
    provider.start();

    return app.exec();
}

# qt_hmi —— 智能工业环境监测系统 显示模块（display_qt）

基于 **Qt5 Widgets + CMake** 的工业监测仪表盘显示模块。当前阶段使用**模拟数据**
独立运行，不依赖任何真实传感器硬件；后续可无缝替换为真实数据源，并部署到
龙芯 2K1000LA 开发板，通过 `linuxfb` 或 `eglfs` 全屏运行。

## 1. 模块说明

界面为“智能工业环境监测系统”仪表盘，包含：

- 系统标题
- 温度（℃）、湿度（%）实时显示
- 气体状态、振动状态、系统总体状态（正常 / 预警 / 报警，三色配色）
- 云端连接状态（已连接 / 已断开）
- 语音助手状态（待唤醒 / 已唤醒 / 识别中）
- 报警日志区域（带时间戳）
- 实时数据刷新（每 1 秒）

设计原则：**显示与数据源解耦**。界面只依赖 `StatusModel`，数据由抽象接口
`IDataProvider` 提供，因此更换数据源不影响界面代码。

### 目录结构

```text
qt_hmi/
├── CMakeLists.txt
├── README.md
├── src/
│   ├── main.cpp             # 入口，支持 --fullscreen；在此切换数据源
│   ├── SystemStatus.h       # 统一状态结构体 + 状态/语音枚举 + 文本转换
│   ├── IDataProvider.h      # 数据源抽象接口（QObject，statusUpdated 信号）
│   ├── MockDataProvider.*   # 模拟数据源（每秒随机波动）
│   ├── StatusModel.*        # 中间模型：保存最新状态 + 报警日志
│   ├── MainWindow.*         # 深色仪表盘界面（纯代码，无 .ui）
├── resources/               # 图片/样式/字体（当前为空）
├── ui/                      # 预留（本模块不使用 .ui 文件）
├── tests/                   # 界面相关测试（预留）
└── scripts/
    ├── build.sh             # 编译
    ├── run_x11.sh           # 虚拟机桌面运行（窗口模式）
    ├── run_linuxfb.sh       # 板端 framebuffer 全屏运行
    └── run_eglfs.sh         # 板端 EGLFS 全屏运行
```

## 2. 依赖环境

- CMake >= 3.16
- Qt5（已在 Qt 5.15.3 上验证），组件：`Qt5Widgets`
- C++14 编译器（GCC / Clang）

Ubuntu 安装依赖示例：

```bash
sudo apt install build-essential cmake qtbase5-dev
```

## 3. 编译方法

```bash
cd qt_hmi
mkdir -p build
cd build
cmake ..
make -j$(nproc)
```

或使用脚本：

```bash
cd qt_hmi
./scripts/build.sh
```

生成可执行文件：`qt_hmi/build/display_qt_app`

> 若系统 Qt 路径特殊，可指定前缀：
> `cmake .. -DCMAKE_PREFIX_PATH=/opt/qt5`

## 4. 在 Linux 虚拟机中运行

普通桌面窗口模式（默认 1024x600）：

```bash
./build/display_qt_app
# 或
./scripts/run_x11.sh
```

全屏模式：

```bash
./build/display_qt_app --fullscreen
```

无显示环境下做冒烟测试（不弹窗，仅验证能启动）：

```bash
QT_QPA_PLATFORM=offscreen ./build/display_qt_app
```

## 5. 板端使用 linuxfb 运行（无 GPU / framebuffer）

```bash
export QT_QPA_PLATFORM=linuxfb
./build/display_qt_app --fullscreen
# 或
./scripts/run_linuxfb.sh
```

如有多个 framebuffer 设备，可指定：

```bash
export QT_QPA_PLATFORM='linuxfb:fb=/dev/fb0'
```

## 6. 板端使用 eglfs 运行（有 GPU / OpenGL ES）

```bash
export QT_QPA_PLATFORM=eglfs
./build/display_qt_app --fullscreen
# 或
./scripts/run_eglfs.sh
```

按需设置屏幕物理尺寸 / 旋转：

```bash
export QT_QPA_EGLFS_PHYSICAL_WIDTH=154
export QT_QPA_EGLFS_PHYSICAL_HEIGHT=86
export QT_QPA_EGLFS_ROTATION=90
```

## 7. 后续接入真实数据源

界面完全不依赖数据来源，接入新数据源只需两步：

**第一步**：新建一个继承 `IDataProvider` 的类，在拿到新数据时
`emit statusUpdated(status)`。例如：

```cpp
// SocketDataProvider.h
class SocketDataProvider : public IDataProvider {
    Q_OBJECT
public:
    void start() override;   // 打开连接、开始接收
    void stop()  override;   // 关闭连接
    // 收到数据后：把协议 JSON 解析成 SystemStatus，再 emit statusUpdated(s);
};
```

**第二步**：在 `src/main.cpp` 中把 `MockDataProvider` 换成新实现：

```cpp
// MockDataProvider provider;
SocketDataProvider provider;
model.setProvider(&provider);
```

计划中的数据源：

- `JsonDataProvider`   —— 读取/回放本地 JSON（对接 `protocol/` schema）
- `SocketDataProvider` —— 通过 TCP/UDP 接收板间通信或云端数据
- `RealSensorDataProvider` —— 对接 2K0301 采集的真实传感器数据

> 与 `protocol/` 的关系：`SystemStatus` 是显示层内部结构，与协议解耦。
> 由具体 Provider 负责把 `sensor_packet` / `risk_packet` / `judge_result`
> 转换成 `SystemStatus`，界面无需感知协议字段。建议后续把协议里的
> `risk_level`(L0~L3) 明确映射到本模块的等级枚举（如 L0=正常，
> L1/L2=预警，L3=报警）。

若真实数据源运行在独立线程，请用 `QueuedConnection`（`SystemStatus`
已通过 `Q_DECLARE_METATYPE` + `qRegisterMetaType` 注册，可跨线程传递）。

## 8. 常见问题排查命令

```bash
qmake -v                                # 查看 Qt/qmake 版本
cmake --version                         # 查看 CMake 版本
pkg-config --modversion Qt5Widgets      # 查看 Qt5Widgets 版本
ls /dev/fb*                             # 是否有 framebuffer 设备（linuxfb）
ls /dev/dri                             # 是否有 DRM 设备（eglfs）
find /usr -name "libqlinuxfb.so"        # linuxfb 平台插件是否存在
find /usr -name "libqeglfs.so"          # eglfs 平台插件是否存在
```

其它常见问题：

- **中文显示为方块**：板端缺中文字体。安装文泉驿等字体，或用
  `export QT_QPA_FONTDIR=/usr/share/fonts` 指定字体目录。
- **linuxfb 黑屏 / 无权限**：确认对 `/dev/fb0` 有读写权限，且未被其它
  程序（如控制台 splash）占用。
- **eglfs 报错找不到平台插件**：确认 Qt 编译时启用了 eglfs，并检查
  `QT_QPA_PLATFORM_PLUGIN_PATH` 指向正确的 plugins 目录。

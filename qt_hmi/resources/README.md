# resources —— 界面资源目录

存放图片、图标、Qt 样式表(.qss)、字体等界面资源。

当前显示模块使用纯代码内联样式，暂无外部资源文件。

后续如需引入资源：

1. 在本目录添加资源文件（如 `app.qss`、`logo.png`）。
2. 新建 `resources.qrc` 列出这些文件。
3. 在 `CMakeLists.txt` 的 `add_executable(...)` 中加入 `resources.qrc`
   （已开启 `CMAKE_AUTORCC`，会自动编译）。
4. 代码中通过 `:/` 前缀访问，例如 `QIcon(":/logo.png")`。

嵌入式提示：字体请确认板端已安装中文字体（如文泉驿），
否则中文可能显示为方块。可通过 `QT_QPA_FONTDIR` 指定字体目录。

cmake_minimum_required(VERSION 3.16)

project(display_qt LANGUAGES CXX)

# ---- C++ 标准 ----
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ---- Qt 自动处理 moc/uic/rcc ----
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

# ---- 查找 Qt5 Widgets ----
# 使用标准 find_package；若系统 Qt 路径特殊，可在 cmake 命令行传入
#   -DCMAKE_PREFIX_PATH=/path/to/qt
find_package(Qt5 REQUIRED COMPONENTS Widgets)

# ---- 源文件 ----
set(SOURCES
    src/main.cpp
    src/MainWindow.cpp
    src/StatusModel.cpp
    src/MockDataProvider.cpp
)

set(HEADERS
    src/SystemStatus.h
    src/IDataProvider.h
    src/MockDataProvider.h
    src/StatusModel.h
    src/MainWindow.h
)

add_executable(display_qt_app ${SOURCES} ${HEADERS})

target_link_libraries(display_qt_app PRIVATE Qt5::Widgets)

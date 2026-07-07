QT += widgets

CONFIG += c++14
TARGET = display_qt_app
TEMPLATE = app

SOURCES += \
    src/main.cpp \
    src/MainWindow.cpp \
    src/StatusModel.cpp \
    src/MockDataProvider.cpp \
    src/FinalStatusDataProvider.cpp

HEADERS += \
    src/SystemStatus.h \
    src/IDataProvider.h \
    src/MockDataProvider.h \
    src/FinalStatusDataProvider.h \
    src/StatusModel.h \
    src/MainWindow.h

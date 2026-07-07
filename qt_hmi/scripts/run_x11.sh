#!/bin/bash
# 在 Linux 虚拟机桌面（X11/Wayland）下运行，普通窗口模式
set -e
cd "$(dirname "$0")/.."
./build/display_qt_app

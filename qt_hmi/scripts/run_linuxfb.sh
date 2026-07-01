#!/bin/bash
# 在板端通过 linuxfb（无 GPU / framebuffer）全屏运行
set -e
cd "$(dirname "$0")/.."
export QT_QPA_PLATFORM=linuxfb
./build/display_qt_app --fullscreen

#!/bin/bash
# 在板端通过 eglfs（有 GPU / OpenGL ES）全屏运行
set -e
cd "$(dirname "$0")/.."
export QT_QPA_PLATFORM=eglfs
./build/display_qt_app --fullscreen

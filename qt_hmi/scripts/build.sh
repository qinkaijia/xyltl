#!/bin/bash
# 编译 display_qt 模块
set -e
cd "$(dirname "$0")/.."
mkdir -p build
cd build
cmake ..
make -j"$(nproc)"
echo "构建完成：$(pwd)/display_qt_app"

#!/bin/bash
#===========================================================================
# WiFi 连接脚本
# 用法：在板子上执行 ./wifi_connect.sh
# 如需更换 WiFi，修改下面的 SSID 和 PASSWORD 即可
#===========================================================================

SSID="OPPO Find X8"
PASSWORD="x635ee3g"
INTERFACE="wlan0"

echo "=== WiFi 连接脚本 ==="
echo "SSID: ${SSID}"
echo "接口: ${INTERFACE}"

# 1. 生成 wpa_supplicant 配置
echo "[1/3] 生成 WiFi 配置..."
wpa_passphrase "${SSID}" "${PASSWORD}" > /etc/wpa_supplicant.conf
if [ $? -ne 0 ]; then
    echo "❌ 生成配置失败！"
    exit 1
fi
echo "✅ 配置已生成"

# 2. 连接 WiFi
echo "[2/3] 连接 WiFi..."
# 先杀掉旧的 wpa_supplicant 进程（如果有的话）
pkill wpa_supplicant 2>/dev/null
sleep 1
wpa_supplicant -B -i ${INTERFACE} -c /etc/wpa_supplicant.conf
if [ $? -ne 0 ]; then
    echo "❌ 连接 WiFi 失败！"
    exit 1
fi
echo "✅ WiFi 已连接"

# 3. 获取 IP 地址
echo "[3/3] 获取 IP 地址..."
if command -v dhclient &> /dev/null; then
    dhclient ${INTERFACE}
elif command -v udhcpc &> /dev/null; then
    udhcpc -i ${INTERFACE}
else
    echo "⚠️  未找到 dhclient 或 udhcpc，尝试手动获取..."
fi

# 4. 显示结果
echo ""
echo "=== 连接结果 ==="
IP=$(ifconfig ${INTERFACE} 2>/dev/null | grep "inet " | awk '{print $2}')
if [ -n "${IP}" ]; then
    echo "✅ 联网成功！IP 地址: ${IP}"
else
    echo "⚠️  未获取到 IP，请检查 WiFi 名和密码是否正确"
fi

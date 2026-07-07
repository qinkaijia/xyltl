#!/usr/bin/env python3
"""
五传感器环境监测 — 远程监控面板（PC 端运行）
通过 SSH 轮询板子上的状态文件，实现多传感器数据展示和分级报警

用法:
    python3 env_monitor.py                 # 默认板子IP: 10.154.34.199
    python3 env_monitor.py 192.168.1.100   # 指定板子IP
    python3 env_monitor.py --demo          # 演示模式 (无需板子)

监控数据:
    · SHT30  温湿度       (I2C-5, 0x44)
    · SGP30  空气质量     (I2C-5, 0x58) — eCO₂ + TVOC
    · 火焰×2 红外检测    (GPIO 数字量)
    · MQ-3   乙醇浓度     (ADC 模拟量)

板子端文件:
    · /tmp/alarm.txt              — 实时报警状态
    · /home/root/env_log.csv      — CSV 数据日志
    · /home/root/alarm_event.txt  — 报警事件记录
"""
import subprocess
import time
import sys
import os
import re

# ======================== 配置 ========================

BOARD_IP       = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "10.154.34.199"
BOARD_USER     = "root"
ALARM_FILE     = "/tmp/alarm.txt"
CSV_FILE       = "/home/root/env_log.csv"
EVENT_FILE     = "/home/root/alarm_event.txt"
CHECK_INTERVAL = 1.0   # 轮询间隔（秒）
SSH_TIMEOUT    = 5     # SSH 超时（秒）

# ======================== 终端颜色 ========================

class C:
    R = '\033[31m'      # 红
    G = '\033[32m'      # 绿
    Y = '\033[33m'      # 黄
    C = '\033[36m'      # 青
    B = '\033[1m'       # 粗体
    D = '\033[90m'      # 灰
    X = '\033[0m'       # 重置

# ======================== SSH 通信 ========================

def ssh_cmd(cmd: str) -> str:
    """在板子上执行命令并返回 stdout"""
    full_cmd = (f'ssh -o ConnectTimeout={SSH_TIMEOUT} -o StrictHostKeyChecking=no '
                f'{BOARD_USER}@{BOARD_IP} "{cmd}"')
    try:
        r = subprocess.run(full_cmd, shell=True, capture_output=True, text=True,
                           timeout=SSH_TIMEOUT + 3)
        return r.stdout.strip()
    except Exception as e:
        return f"ERROR:{e}"


def read_remote_file(path: str) -> str:
    """读取板子上的文件"""
    return ssh_cmd(f"cat {path} 2>/dev/null || echo NO_FILE")


def get_alarm_state() -> dict:
    """
    读取报警文件，格式:
        状态码|状态文本|原因
        0|NORMAL|
        1|WARNING|乙醇偏高
        2|CRITICAL|火焰检测
    """
    raw = read_remote_file(ALARM_FILE)
    if raw in ("NO_FILE", "", "ERROR"):
        return {"level": -1, "text": "N/A", "cause": "", "raw": raw}

    parts = raw.split("|")
    if len(parts) < 2:
        return {"level": -1, "text": "?", "cause": "", "raw": raw}

    return {
        "level": int(parts[0]) if parts[0].isdigit() else -1,
        "text":  parts[1] if len(parts) > 1 else "",
        "cause": parts[2] if len(parts) > 2 else "",
        "raw":   raw
    }


def get_csv_tail(lines: int = 1) -> str:
    """读取 CSV 最后 N 行"""
    return ssh_cmd(f"tail -n {lines} {CSV_FILE} 2>/dev/null || echo NO_FILE")


def get_event_tail(lines: int = 3) -> str:
    """读取事件日志最后 N 行"""
    return ssh_cmd(f"tail -n {lines} {EVENT_FILE} 2>/dev/null || echo NO_FILE")


def parse_csv_line(line: str) -> dict:
    """解析 CSV 数据行"""
    parts = line.strip().split(",")
    if len(parts) < 10:
        return None
    return {
        "ts":        parts[0],
        "temp":      float(parts[1]) if parts[1] else None,
        "humidity":  float(parts[2]) if parts[2] else None,
        "eco2":      int(parts[3])   if parts[3] and parts[3] != "0" else None,
        "tvoc":      int(parts[4])   if parts[4] and parts[4] != "0" else None,
        "flame1":    int(parts[5]),
        "flame2":    int(parts[6]),
        "ethanol":   float(parts[7]) if parts[7] else 0,
        "voltage":   float(parts[8]) if parts[8] else 0,
        "level":     int(parts[9]),
    }

# ======================== 显示函数 ========================

def draw_header():
    """绘制顶部标题栏"""
    print(f"\n{C.B}╔══════════════════════════════════════════════════════════════╗{C.X}")
    print(f"{C.B}║       五传感器环境监测 — 远程监控面板  v3.0              ║{C.X}")
    print(f"{C.B}╠══════════════════════════════════════════════════════════════╣{C.X}")
    print(f"{C.B}║{C.X}  板子: {BOARD_USER}@{BOARD_IP:<39} {C.B}║{C.X}")
    print(f"{C.B}║{C.X}  传感器: SHT30 + SGP30 + 火焰×2 + MQ-3                {C.B}║{C.X}")
    print(f"{C.B}╚══════════════════════════════════════════════════════════════╝{C.X}")
    print()


def draw_dashboard(data: dict, alarm: dict):
    """绘制仪表盘"""
    # 报警状态颜色
    if alarm["level"] == 2:
        alarm_color = C.R + C.B
        alarm_icon  = "🚨 报警"
    elif alarm["level"] == 1:
        alarm_color = C.Y + C.B
        alarm_icon  = "⚠️  预警"
    elif alarm["level"] == 0:
        alarm_color = C.G + C.B
        alarm_icon  = "✅ 正常"
    else:
        alarm_color = C.D
        alarm_icon  = "⏳ 等待连接..."

    cause_str = f" — {alarm['cause']}" if alarm.get("cause") else ""

    print(f"  {alarm_color}┌── 系统状态 ──────────────────────────────────────┐{C.X}")
    print(f"  {alarm_color}│  {alarm_icon}{cause_str:<40}{alarm_color}│{C.X}")
    print(f"  {alarm_color}└──────────────────────────────────────────────────┘{C.X}")
    print()

    # 传感器数据卡片
    if data:
        d = data

        # 温度颜色
        temp = d.get("temp")
        if temp is not None:
            if temp >= 50:   tc = C.R
            elif temp >= 35: tc = C.Y
            else:            tc = C.G
            temp_str = f"{tc}{temp:.1f}℃{C.X}"
        else:
            temp_str = f"{C.D}--.-℃{C.X}"

        # 湿度颜色
        hum = d.get("humidity")
        if hum is not None:
            hum_str = f"{hum:.1f}%RH"
        else:
            hum_str = f"{C.D}--.-%RH{C.X}"

        # eCO2 颜色
        eco2 = d.get("eco2")
        if eco2 is not None:
            if eco2 >= 2000:  ec = C.R
            elif eco2 >= 1000: ec = C.Y
            else:              ec = C.G
            eco2_str = f"{ec}{eco2} ppm{C.X}"
        else:
            eco2_str = f"{C.D}--- ppm{C.X}"

        # TVOC 颜色
        tvoc = d.get("tvoc")
        if tvoc is not None:
            if tvoc >= 1000: vc = C.R
            elif tvoc >= 500: vc = C.Y
            else:             vc = C.G
            tvoc_str = f"{vc}{tvoc} ppb{C.X}"
        else:
            tvoc_str = f"{C.D}--- ppb{C.X}"

        # 火焰状态
        f1 = d.get("flame1", 0)
        f2 = d.get("flame2", 0)
        f1_str = f"{C.R}🔥 火!{C.X}" if f1 else f"{C.G}○ 安全{C.X}"
        f2_str = f"{C.R}🔥 火!{C.X}" if f2 else f"{C.G}○ 安全{C.X}"

        # 乙醇
        eth = d.get("ethanol", 0)
        vlt = d.get("voltage", 0)
        if eth >= 2.5:       ec = C.R
        elif eth >= 1.0:     ec = C.Y
        else:                ec = C.G
        eth_str = f"{ec}{eth:.3f} mg/L{C.X}"
        vlt_str = f"{vlt:.2f} V"

        # 打印表格
        print(f"  ┌──────────────┬──────────────┬──────────────┐")
        print(f"  │  🌡 温度      │  💧 湿度      │  ⚡ MQ-3     │")
        print(f"  ├──────────────┼──────────────┼──────────────┤")
        print(f"  │ {temp_str:<14}│ {hum_str:<14}│ {eth_str:<14}│")
        print(f"  │              │              │  电压: {vlt_str:<7}│")
        print(f"  └──────────────┴──────────────┴──────────────┘")

        print(f"  ┌──────────────┬──────────────┬──────────────┐")
        print(f"  │  🫁 eCO₂      │  🌫 TVOC      │  🔥 火焰     │")
        print(f"  ├──────────────┼──────────────┼──────────────┤")
        print(f"  │ {eco2_str:<14}│ {tvoc_str:<14}│ 1:{f1_str:<7} │")
        print(f"  │              │              │ 2:{f2_str:<7} │")
        print(f"  └──────────────┴──────────────┴──────────────┘")
    else:
        print(f"  {C.D}  等待传感器数据...{C.X}")

    print()


def send_desktop_notification(alarm: dict, data: dict):
    """发送桌面通知 (Linux notify-send)"""
    if alarm["level"] <= 0:
        return

    if alarm["level"] == 2:
        urgency = "critical"
        title = "🚨 环境监测 — 紧急报警！"
    else:
        urgency = "normal"
        title = "⚠️ 环境监测 — 预警"

    body_parts = []
    if alarm.get("cause"):
        body_parts.append(f"原因: {alarm['cause']}")
    if data:
        if data.get("ethanol", 0) > 0.1:
            body_parts.append(f"乙醇: {data['ethanol']:.3f} mg/L")
        if data.get("tvoc") and data["tvoc"] > 100:
            body_parts.append(f"TVOC: {data['tvoc']} ppb")
        if data.get("flame1") or data.get("flame2"):
            body_parts.append("检测到火焰!")
        if data.get("temp") and data["temp"] > 40:
            body_parts.append(f"温度: {data['temp']:.1f}℃")
    body = "\\n".join(body_parts) if body_parts else "请检查环境"

    os.system(f'notify-send -u {urgency} "{title}" "{body}" 2>/dev/null')


# ======================== 主循环 ========================

def main():
    is_demo = "--demo" in sys.argv

    if is_demo:
        print(f"\n{C.Y}{C.B}  ⚠ 演示模式 — 无实际板子连接{C.X}\n")
    else:
        draw_header()

    last_alarm_level = -1
    last_data_line = ""
    tick = 0

    while True:
        try:
            if is_demo:
                # 演示模式：模拟数据
                import random
                alarm = {
                    "level": 0,
                    "text": "NORMAL",
                    "cause": "",
                }
                d = {
                    "ts": time.strftime("%H:%M:%S"),
                    "temp": 25.0 + random.uniform(-2, 2),
                    "humidity": 55.0 + random.uniform(-10, 10),
                    "eco2": 450 + int(random.uniform(-50, 100)),
                    "tvoc": 50 + int(random.uniform(-20, 80)),
                    "flame1": 0,
                    "flame2": 0,
                    "ethanol": random.uniform(0.1, 0.5),
                    "voltage": random.uniform(0.5, 1.5),
                    "level": 0,
                }
            else:
                alarm = get_alarm_state()
                csv = get_csv_tail(1)
                d = None
                if csv and csv != "NO_FILE" and not csv.startswith("timestamp"):
                    d = parse_csv_line(csv)

            # 只有状态变化时才刷新显示
            if alarm["level"] != last_alarm_level:
                if not is_demo:
                    os.system("clear")
                    draw_header()

                draw_dashboard(d, alarm)
                if d:
                    print(f"  {C.D}数据时间: {d.get('ts', '--')}{C.X}")

                # 最近报警事件
                if not is_demo:
                    events = get_event_tail(3)
                    if events and events != "NO_FILE" and "---" not in events:
                        print(f"\n  {C.D}最近事件:{C.X}")
                        for line in events.strip().split("\n"):
                            if line.strip():
                                print(f"    {C.D}{line.strip()}{C.X}")

                print(f"\n  {C.D}按 Ctrl+C 退出  |  轮询间隔: {CHECK_INTERVAL}s{C.X}")

                # 桌面通知
                if alarm["level"] > 0:
                    send_desktop_notification(alarm, d or {})

                last_alarm_level = alarm["level"]

            # 每 30 秒刷新一次数据显示（安静状态下）
            tick += 1
            if tick % 30 == 0 and alarm["level"] == last_alarm_level and alarm["level"] <= 0 and not is_demo:
                os.system("clear")
                draw_header()
                d2 = parse_csv_line(get_csv_tail(1)) if not is_demo else d
                draw_dashboard(d2, alarm)
                if d2:
                    print(f"  {C.D}数据时间: {d2.get('ts', '--')}  |  系统正常{C.X}")
                print(f"\n  {C.D}按 Ctrl+C 退出  |  自动刷新: 30s{C.X}")

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print(f"\n{C.G}  监控面板已安全退出{C.X}\n")
            break
        except Exception as e:
            print(f"  {C.R}错误: {e}{C.X}")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()

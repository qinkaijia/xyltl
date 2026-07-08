from __future__ import annotations

from typing import List


class MockLLM:
    def analyze(self, user_text: str, device_context: dict) -> dict:
        text = (user_text or "").strip()
        if not text:
            return self._result("error", "UNSUPPORTED", False, False, {}, "没有识别到有效文本，请重试。")

        fan_result = self._fan_command(text)
        if fan_result:
            return fan_result

        buzzer_result = self._buzzer_command(text)
        if buzzer_result:
            return buzzer_result

        light_result = self._light_command(text)
        if light_result:
            return light_result

        if self._has_any(text, ["停止检测", "结束检测"]):
            return self._result("control", "STOP_DETECTION", True, True, {}, "停止检测属于关键操作，请确认后执行。")

        if self._has_any(text, ["开始检测", "启动检测", "检测一下"]):
            return self._result("control", "START_DETECTION", True, False, {}, "好的，已开始设备检测。")

        if self._has_any(text, ["状态", "正常", "怎么样", "如何"]):
            reply = self._build_status_reply(device_context)
            return self._result("query", "QUERY_STATUS", False, False, {}, reply)

        if self._has_any(text, ["报警", "为什么", "原因"]):
            reply = self._build_alarm_reply(device_context)
            return self._result("analysis", "EXPLAIN_ALARM", False, False, {}, reply)

        if "上传" in text:
            return self._result("control", "UPLOAD_DATA", True, False, {}, "好的，准备上传当前模拟检测数据。")

        if self._has_any(text, ["报告", "总结"]):
            return self._result("report", "GENERATE_REPORT", True, False, {}, "正在生成当前检测报告。")

        return self._result(
            "error",
            "UNSUPPORTED",
            False,
            False,
            {},
            "当前命令暂不支持。你可以说：打开风扇、打开蜂鸣器、红灯闪烁、查询状态、开始检测。",
        )

    def _fan_command(self, text: str) -> dict | None:
        if not self._has_any(text, ["风扇", "排风", "通风", "电机"]):
            return None
        if self._has_any(text, ["关闭", "停止", "关掉"]):
            return self._result("control", "FAN_CONTROL", True, True, {"state": "off"}, "请确认是否关闭风扇。")
        speed = 80 if self._has_any(text, ["最大", "强力", "高速"]) else 60
        return self._result(
            "control",
            "FAN_CONTROL",
            True,
            False,
            {"state": "on", "speed": speed, "duration_ms": 1000},
            "好的，已下发开启风扇指令。",
        )

    def _buzzer_command(self, text: str) -> dict | None:
        if not self._has_any(text, ["蜂鸣器", "蜂鸣", "警报器", "声音报警"]):
            return None
        if self._has_any(text, ["关闭", "停止", "关掉"]):
            return self._result("control", "BUZZER_CONTROL", True, True, {"state": "off"}, "请确认是否关闭蜂鸣器。")
        return self._result(
            "control",
            "BUZZER_CONTROL",
            True,
            False,
            {"state": "on", "pattern": "fast", "duration_ms": 1000},
            "好的，已下发蜂鸣器报警指令。",
        )

    def _light_command(self, text: str) -> dict | None:
        if not self._has_any(text, ["灯", "警示灯", "报警灯", "红灯", "黄灯", "绿灯"]):
            return None
        if self._has_any(text, ["关闭", "停止", "关掉", "熄灭"]):
            return self._result("control", "ALARM_LIGHT", True, True, {"mode": "off"}, "请确认是否关闭报警灯。")
        color = "red"
        if "黄" in text:
            color = "yellow"
        elif "绿" in text:
            color = "green"
        mode = "blink" if self._has_any(text, ["闪", "闪烁"]) else "on"
        return self._result(
            "control",
            "ALARM_LIGHT",
            True,
            False,
            {"color": color, "mode": mode, "duration_ms": 1000},
            "好的，已下发报警灯指令。",
        )

    @staticmethod
    def _result(
        result_type: str,
        intent: str,
        need_execute: bool,
        need_confirm: bool,
        params: dict,
        reply: str,
    ) -> dict:
        return {
            "type": result_type,
            "intent": intent,
            "need_execute": need_execute,
            "need_confirm": need_confirm,
            "params": params,
            "reply": reply,
        }

    @staticmethod
    def _has_any(text: str, keywords: List[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _build_status_reply(device_context: dict) -> str:
        alarms = device_context.get("alarms", [])
        alarm_text = "、".join(alarms) if alarms else "无报警"
        detecting_text = "正在检测" if device_context.get("detecting") else "未在检测"
        return (
            f"当前设备{detecting_text}。温度 {device_context.get('temperature')} 摄氏度，"
            f"湿度 {device_context.get('humidity')}%，压力 {device_context.get('pressure')}kPa，"
            f"振动状态 {device_context.get('vibration')}，报警状态：{alarm_text}。"
        )

    @staticmethod
    def _build_alarm_reply(device_context: dict) -> str:
        alarms = device_context.get("alarms", [])
        if not alarms:
            return "当前没有模拟报警。温度、压力和振动状态暂未触发阈值。"
        reasons = []
        if "temperature_high" in alarms:
            reasons.append(f"温度达到 {device_context.get('temperature')} 摄氏度，超过高温阈值")
        if "vibration_abnormal" in alarms:
            reasons.append("振动状态为 abnormal，提示设备可能存在异常振动")
        return "当前报警原因：" + "；".join(reasons) + "。"

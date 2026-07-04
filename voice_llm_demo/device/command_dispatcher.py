from __future__ import annotations

from typing import Dict, Optional, Tuple

from .device_state import DeviceState


class CommandDispatcher:
    def __init__(self, device_state: DeviceState) -> None:
        self.device_state = device_state

    def execute(self, intent: str, params: Optional[Dict] = None) -> Tuple[bool, str]:
        _ = params or {}
        if intent == "START_DETECTION":
            self.device_state.detecting = True
            self.device_state.uploaded = False
            return True, "已开始设备检测。"
        if intent == "STOP_DETECTION":
            self.device_state.detecting = False
            return True, "已停止设备检测。"
        if intent == "UPLOAD_DATA":
            self.device_state.uploaded = True
            return True, "已模拟上传当前检测数据。"
        if intent == "GENERATE_REPORT":
            report = self.device_state.generate_report()
            return True, report
        if intent == "QUERY_STATUS":
            return True, "查询类指令无需执行硬件动作。"
        if intent == "EXPLAIN_ALARM":
            return True, "报警解释类指令无需执行硬件动作。"
        return False, f"未知或暂不支持的命令：{intent}"

from voice_llm_demo.device.command_dispatcher import CommandDispatcher
from voice_llm_demo.device.device_state import DeviceState
from voice_llm_demo.llm.mock_llm import MockLLM
from voice_llm_demo.safety.safety_guard import SafetyGuard


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, intent, params):
        self.calls.append((intent, params))
        return True, "ack ok"


def test_mock_llm_maps_fan_voice_command():
    result = MockLLM().analyze("打开风扇", {})

    assert result["intent"] == "FAN_CONTROL"
    assert result["need_execute"] is True
    assert result["params"]["state"] == "on"


def test_safety_guard_requires_confirm_for_turning_light_off():
    result = {
        "type": "control",
        "intent": "ALARM_LIGHT",
        "need_execute": True,
        "need_confirm": False,
        "params": {"mode": "off"},
        "reply": "关灯",
    }

    ok, message = SafetyGuard().check(result)

    assert ok is False
    assert "二次确认" in message


def test_dispatcher_uses_mqtt_executor_for_hardware_intent():
    executor = FakeExecutor()
    dispatcher = CommandDispatcher(DeviceState(), mqtt_executor=executor)

    ok, message = dispatcher.execute("BUZZER_CONTROL", {"state": "on"})

    assert ok is True
    assert message == "ack ok"
    assert executor.calls == [("BUZZER_CONTROL", {"state": "on"})]


def test_safety_guard_allows_non_executing_general_qa():
    result = {
        "type": "qa",
        "intent": "GENERAL_QA",
        "need_execute": False,
        "need_confirm": False,
        "params": {},
        "reply": "这是一个安全监护系统。",
    }

    ok, message = SafetyGuard().check(result)

    assert ok is True
    assert "通过" in message

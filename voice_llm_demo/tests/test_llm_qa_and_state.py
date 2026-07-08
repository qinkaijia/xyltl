import json

from voice_llm_demo.assistant_state import AssistantStateWriter
from voice_llm_demo.llm.llm_client import LLMClient


def test_hardware_command_stays_local_when_real_llm_enabled():
    client = LLMClient(use_real=True, provider="qwen")

    def fail_if_called(_messages):
        raise AssertionError("hardware command should not call remote LLM")

    client._call_chat_completion = fail_if_called  # type: ignore[method-assign]

    result = client.analyze("打开风扇", {})

    assert result["intent"] == "FAN_CONTROL"
    assert result["need_execute"] is True


def test_general_question_uses_real_llm_and_limits_reply():
    client = LLMClient(use_real=True, provider="qwen", max_reply_chars=12, max_question_chars=20)
    client._call_chat_completion = lambda _messages: "这是一个超过长度限制的系统介绍回答"  # type: ignore[method-assign]

    result = client.analyze("请介绍一下这个系统的作用", {"temperature": 26})

    assert result["intent"] == "GENERAL_QA"
    assert result["need_execute"] is False
    assert result["provider"] == "qwen"
    assert len(result["reply"]) <= 12
    assert result["reply"].endswith("…")


def test_real_llm_failure_reports_error_without_local_fallback():
    client = LLMClient(use_real=True, provider="qwen", max_reply_chars=80)

    def fail_call(_messages):
        raise RuntimeError("缺少大模型密钥环境变量：QWEN_API_KEY")

    client._call_chat_completion = fail_call  # type: ignore[method-assign]

    result = client.analyze("请介绍一下这个系统的作用", {"temperature": 26})

    assert result["intent"] == "LLM_UNAVAILABLE"
    assert result["need_execute"] is False
    assert "真实大模型调用失败" in result["reply"]
    assert "本地安全控制" not in result["reply"]


def test_assistant_state_writer_outputs_qt_consumable_json(tmp_path):
    state_file = tmp_path / "voice_state.json"
    writer = AssistantStateWriter(str(state_file), max_history=1)

    writer.update(
        "speaking",
        state_text="正在显示回复",
        last_user_text="介绍系统",
        last_reply="这是一个工业安全监护系统。",
        last_intent="GENERAL_QA",
        llm_provider="qwen",
        commit_history=True,
    )

    data = json.loads(state_file.read_text(encoding="utf-8"))

    assert data["state"] == "speaking"
    assert data["last_user_text"] == "介绍系统"
    assert data["last_reply"]
    assert data["history"][0]["assistant"] == "这是一个工业安全监护系统。"

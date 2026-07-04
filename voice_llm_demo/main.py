from __future__ import annotations

from datetime import datetime
import json
import logging
import os
import traceback

import config
from asr import ASRClient
from device import CommandDispatcher, DeviceState
from llm import LLMClient
from recorder import RecorderError, VADRecorder
from safety import SafetyGuard


def setup_logging() -> None:
    os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if not root_logger.handlers:
        handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        root_logger.addHandler(handler)


def print_json(title: str, data: dict) -> None:
    print(f"\n{title}:")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def log_interaction(record: dict) -> None:
    logging.info(json.dumps(record, ensure_ascii=False, sort_keys=True))


def confirm_action() -> bool:
    answer = input("是否继续？请输入 y/n：").strip().lower()
    return answer == "y"


def run_once(
    recorder: VADRecorder,
    asr_client: ASRClient,
    device_state: DeviceState,
    llm_client: LLMClient,
    safety_guard: SafetyGuard,
    dispatcher: CommandDispatcher,
) -> None:
    audio_path = ""
    asr_text = ""
    llm_result: dict = {}
    safety_ok = False
    safety_message = ""
    execute_ok = False
    execute_message = ""

    try:
        try:
            audio_path = recorder.record_once()
        except RecorderError as exc:
            print(f"录音不可用：{exc}")
            print("本轮将跳过真实录音，直接进入手动 ASR 文本输入。")
            audio_path = "NO_AUDIO_RECORDED"

        asr_text = asr_client.transcribe(audio_path)
        if not asr_text:
            print("ASR 文本为空，本轮结束。")
            return

        device_state.update_simulated_data()
        device_context = device_state.get_context()
        llm_result = llm_client.analyze(asr_text, device_context)

        print_json("当前设备上下文", device_context)
        print_json("LLM 输出 JSON", llm_result)

        safety_ok, safety_message = safety_guard.check(llm_result)
        print(f"\n安全校验：{safety_message}")
        if not safety_ok:
            print(f"系统回复：{llm_result.get('reply', safety_message)}")
            return

        if safety_guard.need_confirm(llm_result):
            if not confirm_action():
                execute_message = "操作已取消。"
                print(execute_message)
                return

        if llm_result.get("need_execute"):
            execute_ok, execute_message = dispatcher.execute(
                llm_result.get("intent", ""),
                llm_result.get("params") or {},
            )
            print(f"\n命令执行结果：{execute_message}")
        else:
            execute_ok = True
            execute_message = "无需执行设备命令。"

        print(f"\n系统回复：{llm_result.get('reply', '')}")
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # noqa: BLE001 - keep CLI stable for field debugging.
        execute_message = f"本轮处理异常：{exc}"
        print(execute_message)
        logging.error(traceback.format_exc())
    finally:
        log_interaction(
            {
                "time": datetime.now().isoformat(timespec="seconds"),
                "audio_path": audio_path,
                "asr_text": asr_text,
                "device_context": device_state.get_context(),
                "llm_result": llm_result,
                "safety_ok": safety_ok,
                "safety_message": safety_message,
                "execute_ok": execute_ok,
                "execute_message": execute_message,
                "system_reply": llm_result.get("reply", "") if isinstance(llm_result, dict) else "",
            }
        )


def main() -> None:
    os.makedirs(config.RECORDED_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)
    setup_logging()

    recorder = VADRecorder()
    asr_client = ASRClient()
    device_state = DeviceState()
    llm_client = LLMClient()
    safety_guard = SafetyGuard()
    dispatcher = CommandDispatcher(device_state)

    print("智能语音 + LLM 命令行 Demo 已启动")
    print("按 Enter 开始一次语音交互，输入 q 退出")

    while True:
        command = input("\n> ").strip().lower()
        if command == "q":
            print("已退出。")
            break
        run_once(recorder, asr_client, device_state, llm_client, safety_guard, dispatcher)


if __name__ == "__main__":
    main()

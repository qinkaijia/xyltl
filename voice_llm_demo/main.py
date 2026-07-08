from __future__ import annotations

import argparse
from datetime import datetime
import json
import logging
import os
import shutil
import subprocess
import time
import traceback

from assistant_state import AssistantStateWriter
import config
from asr import ASRClient
from device import CommandDispatcher, DeviceState, MqttCommandExecutor
from llm import LLMClient
from recorder import RecorderError, VADRecorder
from safety import SafetyGuard
from tts import VoiceSpeaker


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


def list_audio_devices() -> None:
    if not shutil.which("arecord"):
        print("未找到 arecord，请先安装 alsa-utils。")
        return
    subprocess.run(["arecord", "-l"], check=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="智能语音 + LLM 命令行 Demo")
    parser.add_argument("--continuous", action="store_true", help="持续监听麦克风，检测到人声后自动处理。")
    parser.add_argument("--listen-only", action="store_true", help="只做 VAD 收音和保存 wav，不进入 ASR/LLM。")
    parser.add_argument("--manual-text", default="", help="跳过录音和 ASR，直接用给定文本做一次命令联调。")
    parser.add_argument("--audio-device", default="", help="ALSA 录音设备，例如 hw:1,0。为空时使用系统默认设备。")
    parser.add_argument("--list-audio", action="store_true", help="列出 arecord 可用录音设备后退出。")
    parser.add_argument("--mqtt-control", action="store_true", help="启用 2K0301 MQTT 真实命令下发。")
    parser.add_argument("--mqtt-host", default="", help="2K0301 MQTT Broker 地址，板端通常为 127.0.0.1。")
    parser.add_argument("--mqtt-port", type=int, default=0, help="2K0301 MQTT Broker 端口，默认 1883。")
    parser.add_argument("--mqtt-qos", type=int, default=-1, choices=[-1, 0, 1, 2], help="MQTT QoS，默认 1。")
    parser.add_argument("--mqtt-ack-timeout", type=float, default=0.0, help="等待 301 ACK 的秒数，默认 3 秒。")
    parser.add_argument("--assistant-state-file", default="", help="写给 Qt HMI 读取的语音助手状态 JSON。")
    parser.add_argument("--context-status-file", default="", help="提供给大模型问答的最新系统状态 JSON。")
    parser.add_argument("--real-llm", action="store_true", help="普通问答启用真实大模型；执行命令仍走本地安全解析。")
    parser.add_argument("--llm-provider", default="", help="大模型提供商：deepseek/kimi/zhipu/doubao/qwen。")
    parser.add_argument("--max-history-turns", type=int, default=0, help="传给大模型的最近问答轮数。")
    parser.add_argument("--max-reply-chars", type=int, default=0, help="语音回答最大字符数。")
    parser.add_argument("--wake-required", action="store_true", help="连续监听时要求唤醒词，默认读取 VOICE_WAKE_REQUIRED。")
    parser.add_argument("--wake-words", default="", help="逗号分隔的唤醒词，例如：小龙,龙芯助手。")
    parser.add_argument("--wake-window-seconds", type=float, default=0.0, help="单独唤醒后等待下一句指令的秒数。")
    parser.add_argument("--tts-mode", default="", help="播报模式：none/print/baidu。默认读取 VOICE_TTS_MODE。")
    return parser.parse_args()


def build_mqtt_executor(args: argparse.Namespace):
    if not (args.mqtt_control or config.VOICE_MQTT_CONTROL_ENABLED):
        return None
    host = args.mqtt_host or config.VOICE_MQTT_HOST
    port = args.mqtt_port if args.mqtt_port > 0 else config.VOICE_MQTT_PORT
    qos = args.mqtt_qos if args.mqtt_qos >= 0 else config.VOICE_MQTT_QOS
    ack_timeout = args.mqtt_ack_timeout if args.mqtt_ack_timeout > 0 else config.VOICE_MQTT_ACK_TIMEOUT
    return MqttCommandExecutor(host=host, port=port, qos=qos, ack_timeout=ack_timeout)


def parse_words(text: str) -> list[str]:
    return [item.strip() for item in str(text or "").split(",") if item.strip()]


def consume_wake_word(text: str, wake_words: list[str]) -> tuple[bool, str]:
    clean = str(text or "").strip()
    for word in wake_words:
        if word and word in clean:
            cleaned = clean.replace(word, "", 1).strip(" ，,。.!！?？")
            return True, cleaned
    return False, clean


def next_wake_armed_until(
    outcome: str,
    wake_required: bool,
    wake_window_seconds: float,
    current_until: float,
    now: float,
) -> float:
    if not wake_required:
        return 0.0
    if outcome in {"armed", "handled"}:
        return now + wake_window_seconds
    if current_until and now >= current_until:
        return 0.0
    return current_until


def run_once(
    recorder: VADRecorder,
    asr_client: ASRClient,
    device_state: DeviceState,
    llm_client: LLMClient,
    safety_guard: SafetyGuard,
    dispatcher: CommandDispatcher,
    assistant_state: AssistantStateWriter | None = None,
    llm_provider: str = "",
    speaker: VoiceSpeaker | None = None,
    wake_required: bool = False,
    wake_words: list[str] | None = None,
    wake_session_active: bool = False,
    skip_on_record_error: bool = False,
    listen_only: bool = False,
) -> str:
    audio_path = ""
    asr_text = ""
    llm_result: dict = {}
    safety_ok = False
    safety_message = ""
    execute_ok = False
    execute_message = ""

    try:
        if assistant_state:
            assistant_state.update("listening", state_text="正在监听")
        try:
            audio_path = recorder.record_once()
        except RecorderError as exc:
            if skip_on_record_error:
                print(f"本轮未录到有效语音：{exc}，继续监听。")
                return "record_error"
            print(f"录音不可用：{exc}")
            print("本轮将跳过真实录音，直接进入手动 ASR 文本输入。")
            audio_path = "NO_AUDIO_RECORDED"

        if listen_only:
            print(f"listen_only 已保存音频：{audio_path}")
            if assistant_state:
                assistant_state.update("idle", state_text="录音已保存", execute_message=f"listen_only：{audio_path}")
            return "listen_only"

        if assistant_state:
            assistant_state.update("recognizing", state_text="正在识别", execute_message=f"录音：{audio_path}")
        asr_text = asr_client.transcribe(audio_path)
        if not asr_text:
            print("ASR 文本为空，本轮结束。")
            if speaker:
                speaker.speak("没有听清，请重新说一遍。")
            if assistant_state:
                assistant_state.update("error", state_text="未识别到文本", last_user_text="", last_reply="请重新说一遍。")
            return "empty"

        if assistant_state:
            assistant_state.update("recognizing", state_text="已识别文本", last_user_text=asr_text, llm_provider=llm_provider)

        if wake_required:
            woke, cleaned_text = consume_wake_word(asr_text, wake_words or [])
            if wake_session_active and not woke:
                print("处于唤醒窗口，直接处理本句指令。")
            elif not woke:
                print("未检测到唤醒词，本轮忽略。")
                if assistant_state:
                    assistant_state.update(
                        "idle",
                        state_text="等待唤醒词",
                        last_user_text=asr_text,
                        last_reply="未检测到唤醒词，请先说：{}".format("、".join(wake_words or [])),
                    )
                return "ignored"
            if not cleaned_text:
                reply = "我在，请说。"
                print("检测到唤醒词，等待下一句指令。")
                if speaker:
                    speaker.speak(reply)
                if assistant_state:
                    assistant_state.update("awake", state_text="已唤醒", last_user_text=asr_text, last_reply=reply)
                return "armed"
            if woke:
                asr_text = cleaned_text

        if assistant_state:
            assistant_state.update("thinking", state_text="大模型思考中", last_user_text=asr_text, llm_provider=llm_provider)
        device_state.update_simulated_data()
        device_context = device_state.get_context()
        llm_result = llm_client.analyze(asr_text, device_context)

        print_json("当前设备上下文", device_context)
        print_json("LLM 输出 JSON", llm_result)

        safety_ok, safety_message = safety_guard.check(llm_result)
        print(f"\n安全校验：{safety_message}")
        if not safety_ok:
            print(f"系统回复：{llm_result.get('reply', safety_message)}")
            if speaker:
                speaker.speak(llm_result.get("reply", safety_message))
            if assistant_state:
                assistant_state.update(
                    "error",
                    state_text="安全校验未通过",
                    last_user_text=asr_text,
                    last_reply=llm_result.get("reply", safety_message),
                    last_intent=llm_result.get("intent", ""),
                    safety_message=safety_message,
                    llm_provider=llm_result.get("provider", llm_provider),
                    commit_history=True,
                )
            return "handled"

        if safety_guard.need_confirm(llm_result):
            if not confirm_action():
                execute_message = "操作已取消。"
                print(execute_message)
                if speaker:
                    speaker.speak(execute_message)
                return "cancelled"

        if llm_result.get("need_execute"):
            if assistant_state:
                assistant_state.update(
                    "executing",
                    state_text="正在执行命令",
                    last_user_text=asr_text,
                    last_reply=llm_result.get("reply", ""),
                    last_intent=llm_result.get("intent", ""),
                    safety_message=safety_message,
                    llm_provider=llm_result.get("provider", llm_provider),
                )
            execute_ok, execute_message = dispatcher.execute(
                llm_result.get("intent", ""),
                llm_result.get("params") or {},
            )
            print(f"\n命令执行结果：{execute_message}")
        else:
            execute_ok = True
            execute_message = "无需执行设备命令。"

        print(f"\n系统回复：{llm_result.get('reply', '')}")
        if speaker:
            speak_text = llm_result.get("reply", "")
            if execute_message and execute_message != "无需执行设备命令。":
                speak_text = f"{speak_text}。{execute_message}"
            speaker.speak(speak_text)
        if assistant_state:
            assistant_state.update(
                "speaking",
                state_text="正在显示回复",
                last_user_text=asr_text,
                last_reply=llm_result.get("reply", ""),
                last_intent=llm_result.get("intent", ""),
                safety_message=safety_message,
                execute_message=execute_message,
                llm_provider=llm_result.get("provider", llm_provider),
                commit_history=True,
            )
        return "handled"
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # noqa: BLE001 - keep CLI stable for field debugging.
        execute_message = f"本轮处理异常：{exc}"
        print(execute_message)
        logging.error(traceback.format_exc())
        if assistant_state:
            assistant_state.update("error", state_text="处理异常", error=str(exc), execute_message=execute_message)
        return "error"
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


def run_text_once(
    asr_text: str,
    device_state: DeviceState,
    llm_client: LLMClient,
    safety_guard: SafetyGuard,
    dispatcher: CommandDispatcher,
    assistant_state: AssistantStateWriter | None = None,
    llm_provider: str = "",
    speaker: VoiceSpeaker | None = None,
) -> None:
    llm_result: dict = {}
    safety_ok = False
    safety_message = ""
    execute_ok = False
    execute_message = ""

    try:
        if not asr_text:
            print("ASR 文本为空，本轮结束。")
            if assistant_state:
                assistant_state.update("error", state_text="文本为空", last_reply="没有收到有效文本。")
            return

        if assistant_state:
            assistant_state.update("thinking", state_text="大模型思考中", last_user_text=asr_text, llm_provider=llm_provider)
        device_state.update_simulated_data()
        device_context = device_state.get_context()
        llm_result = llm_client.analyze(asr_text, device_context)

        print_json("当前设备上下文", device_context)
        print_json("LLM 输出 JSON", llm_result)

        safety_ok, safety_message = safety_guard.check(llm_result)
        print(f"\n安全校验：{safety_message}")
        if not safety_ok:
            print(f"系统回复：{llm_result.get('reply', safety_message)}")
            if speaker:
                speaker.speak(llm_result.get("reply", safety_message))
            if assistant_state:
                assistant_state.update(
                    "error",
                    state_text="安全校验未通过",
                    last_user_text=asr_text,
                    last_reply=llm_result.get("reply", safety_message),
                    last_intent=llm_result.get("intent", ""),
                    safety_message=safety_message,
                    llm_provider=llm_result.get("provider", llm_provider),
                    commit_history=True,
                )
            return

        if safety_guard.need_confirm(llm_result):
            if not confirm_action():
                execute_message = "操作已取消。"
                print(execute_message)
                if speaker:
                    speaker.speak(execute_message)
                return

        if llm_result.get("need_execute"):
            if assistant_state:
                assistant_state.update(
                    "executing",
                    state_text="正在执行命令",
                    last_user_text=asr_text,
                    last_reply=llm_result.get("reply", ""),
                    last_intent=llm_result.get("intent", ""),
                    safety_message=safety_message,
                    llm_provider=llm_result.get("provider", llm_provider),
                )
            execute_ok, execute_message = dispatcher.execute(
                llm_result.get("intent", ""),
                llm_result.get("params") or {},
            )
            print(f"\n命令执行结果：{execute_message}")
        else:
            execute_ok = True
            execute_message = "无需执行设备命令。"

        print(f"\n系统回复：{llm_result.get('reply', '')}")
        if speaker:
            speak_text = llm_result.get("reply", "")
            if execute_message and execute_message != "无需执行设备命令。":
                speak_text = f"{speak_text}。{execute_message}"
            speaker.speak(speak_text)
        if assistant_state:
            assistant_state.update(
                "speaking",
                state_text="正在显示回复",
                last_user_text=asr_text,
                last_reply=llm_result.get("reply", ""),
                last_intent=llm_result.get("intent", ""),
                safety_message=safety_message,
                execute_message=execute_message,
                llm_provider=llm_result.get("provider", llm_provider),
                commit_history=True,
            )
    finally:
        log_interaction(
            {
                "time": datetime.now().isoformat(timespec="seconds"),
                "audio_path": "MANUAL_TEXT",
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
    args = parse_args()
    if args.list_audio:
        list_audio_devices()
        return
    if args.audio_device:
        config.AUDIO_DEVICE = args.audio_device

    os.makedirs(config.RECORDED_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)
    setup_logging()

    recorder = VADRecorder()
    asr_client = ASRClient()
    device_state = DeviceState()
    llm_provider = args.llm_provider or config.VOICE_LLM_PROVIDER
    llm_client = LLMClient(
        use_real=args.real_llm or config.USE_REAL_LLM,
        provider=llm_provider,
        context_status_file=args.context_status_file or config.VOICE_CONTEXT_STATUS_FILE,
        max_history_turns=args.max_history_turns or config.VOICE_MAX_HISTORY_TURNS,
        max_reply_chars=args.max_reply_chars or config.VOICE_MAX_REPLY_CHARS,
    )
    safety_guard = SafetyGuard()
    mqtt_executor = build_mqtt_executor(args)
    dispatcher = CommandDispatcher(device_state, mqtt_executor=mqtt_executor)
    state_file = args.assistant_state_file or config.VOICE_ASSISTANT_STATE_FILE
    assistant_state = AssistantStateWriter(state_file, max_history=args.max_history_turns or config.VOICE_MAX_HISTORY_TURNS)
    speaker = VoiceSpeaker(args.tts_mode or config.VOICE_TTS_MODE)
    wake_words = parse_words(args.wake_words) or list(config.VOICE_WAKE_WORDS)
    wake_required = args.wake_required or config.VOICE_WAKE_REQUIRED
    wake_window_seconds = args.wake_window_seconds if args.wake_window_seconds > 0 else config.VOICE_WAKE_WINDOW_SECONDS
    assistant_state.update("idle", state_text="待唤醒", llm_provider=llm_provider)

    print("智能语音 + LLM 命令行 Demo 已启动")
    print(f"录音设备：{config.AUDIO_DEVICE or '系统默认'}")
    if mqtt_executor is not None:
        print("MQTT 真实控制已启用。")
    print(f"语音助手状态文件：{state_file}")
    print(f"问答模型：{llm_provider}（真实 LLM：{'开启' if (args.real_llm or config.USE_REAL_LLM) else '关闭'}）")
    print(f"唤醒词：{'开启' if wake_required else '关闭'} {wake_words if wake_required else ''}")
    if wake_required:
        print(f"唤醒窗口：{wake_window_seconds:.1f} 秒")
    print(f"播报模式：{speaker.mode}")

    if args.manual_text:
        run_text_once(args.manual_text, device_state, llm_client, safety_guard, dispatcher, assistant_state, llm_provider, speaker)
        return

    if args.continuous:
        print("持续监听模式已启动；说话触发录音，按 Ctrl+C 退出。")
        if args.listen_only:
            print("listen_only 模式：只保存录音文件，不调用 ASR/LLM。")
        wake_armed_until = 0.0
        while True:
            wake_session_active = wake_required and time.monotonic() < wake_armed_until
            previous_wake_until = wake_armed_until
            outcome = run_once(
                recorder,
                asr_client,
                device_state,
                llm_client,
                safety_guard,
                dispatcher,
                assistant_state,
                llm_provider,
                speaker,
                wake_required,
                wake_words,
                wake_session_active=wake_session_active,
                skip_on_record_error=True,
                listen_only=args.listen_only,
            )
            now = time.monotonic()
            wake_armed_until = next_wake_armed_until(
                outcome,
                wake_required,
                wake_window_seconds,
                wake_armed_until,
                now,
            )
            if outcome == "armed":
                print(f"唤醒窗口已开启，{wake_window_seconds:.1f} 秒内可直接说指令。")
            elif outcome == "handled":
                print(f"回答完成，唤醒窗口已延长 {wake_window_seconds:.1f} 秒，可继续追问。")
            elif previous_wake_until and previous_wake_until != wake_armed_until and wake_armed_until == 0.0:
                print("唤醒窗口已超时，对话结束。")
                if assistant_state:
                    assistant_state.update("idle", state_text="对话结束，等待唤醒词", last_reply="对话已结束，请再次唤醒。")
            time.sleep(config.CONTINUOUS_INTERVAL_SECONDS)

    else:
        print("按 Enter 开始一次语音交互，输入 q 退出")
        while True:
            command = input("\n> ").strip().lower()
            if command == "q":
                print("已退出。")
                break
            run_once(recorder, asr_client, device_state, llm_client, safety_guard, dispatcher, assistant_state, llm_provider, speaker)


if __name__ == "__main__":
    main()

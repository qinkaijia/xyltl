from __future__ import annotations

from datetime import datetime
import math
import os
import shutil
import struct
import subprocess
import time
from typing import List, Optional
import wave

import config


class RecorderError(RuntimeError):
    """Raised when recording cannot start or complete safely."""


def pcm16_rms(frame: bytes) -> float:
    """Calculate RMS for signed 16-bit little-endian PCM without audioop."""
    if not frame:
        return 0.0
    sample_count = len(frame) // config.SAMPLE_WIDTH
    if sample_count <= 0:
        return 0.0
    samples = struct.unpack("<" + "h" * sample_count, frame[: sample_count * 2])
    square_sum = sum(sample * sample for sample in samples)
    return math.sqrt(square_sum / sample_count)


class VADRecorder:
    def __init__(self) -> None:
        self.frame_bytes = int(config.SAMPLE_RATE * config.FRAME_MS / 1000) * config.SAMPLE_WIDTH
        self.end_silence_frames = max(1, int(config.END_SILENCE_SECONDS * 1000 / config.FRAME_MS))
        self.max_frames = max(1, int(config.MAX_RECORD_SECONDS * 1000 / config.FRAME_MS))
        self.min_frames = max(1, int(config.MIN_RECORD_SECONDS * 1000 / config.FRAME_MS))
        os.makedirs(config.RECORDED_DIR, exist_ok=True)

    def record_once(self) -> str:
        """
        Listen through arecord, detect speech by RMS threshold, save one WAV file,
        and return its path.
        """
        if not shutil.which("arecord"):
            raise RecorderError(
                "未找到 arecord。请先安装或检查 alsa-utils，并运行 arecord -l 确认声卡。"
            )

        command = [
            "arecord",
            "-q",
            "-f",
            "S16_LE",
            "-r",
            str(config.SAMPLE_RATE),
            "-c",
            str(config.CHANNELS),
            "-t",
            "raw",
            "-",
        ]

        process = None
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise RecorderError(f"启动 arecord 失败：{exc}") from exc

        if process.stdout is None:
            self._terminate_process(process)
            raise RecorderError("arecord stdout 不可用，无法读取麦克风数据。")

        try:
            print("正在校准环境噪声，请保持安静...")
            threshold = self._calibrate_noise(process)
            print(f"噪声校准完成，语音阈值：{threshold:.1f}")
            print("请开始说话...")

            frames = []  # type: List[bytes]
            pre_speech_frames = []  # type: List[bytes]
            speech_hit_frames = 0
            silence_frames = 0
            recording = False
            started_at = time.monotonic()

            while True:
                frame = process.stdout.read(self.frame_bytes)
                if len(frame) < self.frame_bytes:
                    raise RecorderError("麦克风数据中断，请检查录音设备是否被占用。")

                rms = pcm16_rms(frame)
                is_speech = rms >= threshold

                if not recording:
                    pre_speech_frames.append(frame)
                    pre_speech_frames = pre_speech_frames[-config.START_SPEECH_FRAMES :]
                    speech_hit_frames = speech_hit_frames + 1 if is_speech else 0
                    if speech_hit_frames >= config.START_SPEECH_FRAMES:
                        recording = True
                        frames.extend(pre_speech_frames)
                        silence_frames = 0
                        print("检测到人声，开始录音。")
                    elif time.monotonic() - started_at > config.MAX_RECORD_SECONDS:
                        raise RecorderError("等待人声超时，本轮未录到有效语音。")
                    continue

                frames.append(frame)
                silence_frames = 0 if is_speech else silence_frames + 1

                if len(frames) >= self.max_frames:
                    print("达到最大录音时长，自动停止。")
                    break
                if silence_frames >= self.end_silence_frames:
                    print("检测到持续静音，录音结束。")
                    break

            if len(frames) < self.min_frames:
                print("提示：本次录音较短，仍会保存文件，必要时可重新录制。")

            output_path = self._save_wav(frames)
            print(f"录音已保存：{output_path}")
            return output_path
        finally:
            self._terminate_process(process)

    def _calibrate_noise(self, process: subprocess.Popen) -> float:
        assert process.stdout is not None
        frame_total = max(1, int(config.NOISE_CALIBRATION_SECONDS * 1000 / config.FRAME_MS))
        rms_values = []
        for _ in range(frame_total):
            frame = process.stdout.read(self.frame_bytes)
            if len(frame) < self.frame_bytes:
                raise RecorderError("噪声校准失败：未能读取到足够的麦克风数据。")
            rms_values.append(pcm16_rms(frame))
        noise_rms = sum(rms_values) / len(rms_values)
        return max(noise_rms * config.THRESHOLD_RATIO, config.MIN_ABSOLUTE_THRESHOLD)

    def _save_wav(self, frames: List[bytes]) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(config.RECORDED_DIR, f"input_{timestamp}.wav")
        with wave.open(output_path, "wb") as wav_file:
            wav_file.setnchannels(config.CHANNELS)
            wav_file.setsampwidth(config.SAMPLE_WIDTH)
            wav_file.setframerate(config.SAMPLE_RATE)
            wav_file.writeframes(b"".join(frames))
        return output_path

    @staticmethod
    def _terminate_process(process: Optional[subprocess.Popen]) -> None:
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()

from __future__ import annotations

import argparse
import math
from pathlib import Path
import shutil
import struct
import subprocess
import wave


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="录音设备固定时长采样探针")
    parser.add_argument("--device", default="", help="ALSA 设备，例如 hw:1,0。为空时使用默认设备。")
    parser.add_argument("--seconds", type=float, default=2.0)
    parser.add_argument("--output", default="data/recorded/probe.wav")
    parser.add_argument("--rate", type=int, default=16000)
    parser.add_argument("--channels", type=int, default=1)
    return parser.parse_args()


def pcm16_stats(pcm: bytes) -> tuple[float, int]:
    sample_count = len(pcm) // 2
    if sample_count <= 0:
        return 0.0, 0
    samples = struct.unpack("<" + "h" * sample_count, pcm[: sample_count * 2])
    peak = max(abs(sample) for sample in samples)
    rms = math.sqrt(sum(sample * sample for sample in samples) / sample_count)
    return rms, peak


def main() -> None:
    args = parse_args()
    if not shutil.which("arecord"):
        raise SystemExit("未找到 arecord，请先安装 alsa-utils。")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "arecord",
        "-q",
        "-f",
        "S16_LE",
        "-r",
        str(args.rate),
        "-c",
        str(args.channels),
        "-d",
        str(max(1, int(args.seconds))),
        str(output),
    ]
    if args.device:
        command[2:2] = ["-D", args.device]

    print("录音命令：{}".format(" ".join(command)))
    result = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise SystemExit(result.stderr.decode("utf-8", errors="replace") or "arecord 录音失败")

    with wave.open(str(output), "rb") as wav_file:
        pcm = wav_file.readframes(wav_file.getnframes())
        rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        width = wav_file.getsampwidth()

    rms, peak = pcm16_stats(pcm)
    print("录音文件：{}".format(output))
    print("格式：{} Hz / {} channel / {} bit".format(rate, channels, width * 8))
    print("RMS：{:.1f}  峰值：{}".format(rms, peak))
    if peak < 200:
        print("提示：峰值很低，可能没有说话、麦克风静音或录到了错误设备。")
    else:
        print("录音输入有效。")


if __name__ == "__main__":
    main()

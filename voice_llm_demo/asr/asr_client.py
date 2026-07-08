from __future__ import annotations

from email.utils import formatdate
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from urllib.parse import urlencode
import urllib.error
import urllib.request
import wave

import config


class ASRClient:
    def transcribe(self, audio_path: str) -> str:
        mode = getattr(config, "ASR_MODE", "manual").strip().lower()
        if mode == "manual":
            return self._manual_transcribe(audio_path)
        if mode == "baidu":
            return self._baidu_transcribe(audio_path)
        if mode == "xfyun":
            return self._xfyun_transcribe(audio_path)
        raise ValueError("未知 ASR_MODE: {}".format(config.ASR_MODE))

    def _manual_transcribe(self, audio_path: str) -> str:
        print("录音已保存：{}".format(audio_path))
        return input("请手动输入模拟 ASR 识别文本：").strip()

    def _fallback_manual(self, audio_path: str, reason: str) -> str:
        print("ASR 自动识别不可用：{}".format(reason))
        fallback_enabled = os.environ.get("ASR_FALLBACK_MANUAL", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if fallback_enabled and sys.stdin.isatty():
            print("已回退到 manual 手动输入模式。")
            return self._manual_transcribe(audio_path)
        print("当前为非交互模式，跳过手动输入，请重新说一遍或检查 ASR 配置。")
        return ""

    def _baidu_transcribe(self, audio_path: str) -> str:
        api_key = os.environ.get(config.BAIDU_API_KEY_ENV)
        secret_key = os.environ.get(config.BAIDU_SECRET_KEY_ENV)
        if not api_key or not secret_key:
            return self._fallback_manual(
                audio_path,
                "缺少环境变量 {} 或 {}".format(
                    config.BAIDU_API_KEY_ENV,
                    config.BAIDU_SECRET_KEY_ENV,
                ),
            )

        try:
            requests = self._try_import_requests()
            token = self._get_baidu_token(requests, api_key, secret_key)
            with open(audio_path, "rb") as audio_file:
                audio_data = audio_file.read()

            payload = {
                "format": "wav",
                "rate": config.SAMPLE_RATE,
                "channel": config.CHANNELS,
                "cuid": config.BAIDU_CUID,
                "token": token,
                "dev_pid": config.BAIDU_DEV_PID,
                "speech": base64.b64encode(audio_data).decode("utf-8"),
                "len": len(audio_data),
            }
            body = self._post_json(
                requests,
                "http://vop.baidu.com/server_api",
                payload,
                timeout=20,
            )
            if body.get("err_no") == 0 and body.get("result"):
                text = "".join(body["result"]).strip()
                if text:
                    print("百度 ASR 识别结果：{}".format(text))
                    return text
                return self._fallback_manual(audio_path, "百度 ASR 返回文本为空")

            return self._fallback_manual(
                audio_path,
                "百度 ASR 失败 err_no={} err_msg={}".format(
                    body.get("err_no"),
                    body.get("err_msg"),
                ),
            )
        except Exception as exc:  # noqa: BLE001 - CLI must stay alive on field devices.
            return self._fallback_manual(audio_path, "百度 ASR 调用异常：{}".format(exc))

    def _get_baidu_token(self, requests, api_key: str, secret_key: str) -> str:
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": api_key,
            "client_secret": secret_key,
        }
        if requests is not None:
            response = requests.post(url, params=params, timeout=15)
            response.raise_for_status()
            body = response.json()
        else:
            body = self._post_form(url, params, timeout=15)
        token = body.get("access_token")
        if not token:
            raise RuntimeError("获取百度 access_token 失败：{}".format(body))
        return token

    @staticmethod
    def _post_json(requests, url: str, payload: dict, timeout: int) -> dict:
        if requests is not None:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _post_form(url: str, params: dict, timeout: int) -> dict:
        data = urlencode(params).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _try_import_requests():
        try:
            import requests

            return requests
        except ImportError:
            print("提示：未安装 requests，百度 ASR 将使用 Python 标准库 urllib 调用。")
            return None

    def _xfyun_transcribe(self, audio_path: str) -> str:
        app_id = os.environ.get(config.XFYUN_APP_ID_ENV)
        api_key = os.environ.get(config.XFYUN_API_KEY_ENV)
        api_secret = os.environ.get(config.XFYUN_API_SECRET_ENV)
        if not app_id or not api_key or not api_secret:
            return self._fallback_manual(
                audio_path,
                "缺少环境变量 {}、{} 或 {}".format(
                    config.XFYUN_APP_ID_ENV,
                    config.XFYUN_API_KEY_ENV,
                    config.XFYUN_API_SECRET_ENV,
                ),
            )

        try:
            websocket = self._import_websocket()
            pcm_data = self._read_wav_pcm(audio_path)
            ws_url = self._build_xfyun_ws_url(api_key, api_secret)
            ws = websocket.create_connection(ws_url, timeout=20)
            try:
                result = self._send_xfyun_frames(ws, app_id, pcm_data)
            finally:
                ws.close()

            text = "".join(result).strip()
            if text:
                print("讯飞 ASR 识别结果：{}".format(text))
                return text
            return self._fallback_manual(audio_path, "讯飞 ASR 返回文本为空")
        except Exception as exc:  # noqa: BLE001 - network/API failures should fall back.
            return self._fallback_manual(audio_path, "讯飞 ASR 调用异常：{}".format(exc))

    @staticmethod
    def _read_wav_pcm(audio_path: str) -> bytes:
        with wave.open(audio_path, "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            if channels != config.CHANNELS or sample_width != config.SAMPLE_WIDTH or sample_rate != config.SAMPLE_RATE:
                raise RuntimeError(
                    "wav 格式不匹配：需要 {}Hz/{}bit/{}声道，实际 {}Hz/{}bit/{}声道".format(
                        config.SAMPLE_RATE,
                        config.SAMPLE_WIDTH * 8,
                        config.CHANNELS,
                        sample_rate,
                        sample_width * 8,
                        channels,
                    )
                )
            return wav_file.readframes(wav_file.getnframes())

    @staticmethod
    def _build_xfyun_ws_url(api_key: str, api_secret: str) -> str:
        host = "iat-api.xfyun.cn"
        path = "/v2/iat"
        date = formatdate(timeval=None, localtime=False, usegmt=True)
        signature_origin = "host: {}\ndate: {}\nGET {} HTTP/1.1".format(host, date, path)
        signature_sha = hmac.new(
            api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        signature = base64.b64encode(signature_sha).decode("utf-8")
        authorization_origin = (
            'api_key="{}", algorithm="hmac-sha256", '
            'headers="host date request-line", signature="{}"'
        ).format(api_key, signature)
        authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
        query = urlencode({"authorization": authorization, "date": date, "host": host})
        return "wss://{}{}?{}".format(host, path, query)

    def _send_xfyun_frames(self, ws, app_id: str, pcm_data: bytes) -> list:
        frame_size = 1280
        results = []
        offset = 0
        first_frame = True

        while offset < len(pcm_data):
            chunk = pcm_data[offset : offset + frame_size]
            offset += frame_size
            is_last = offset >= len(pcm_data)
            status = 0 if first_frame else (2 if is_last else 1)
            payload = self._build_xfyun_frame(app_id, chunk, status, include_business=first_frame)
            ws.send(json.dumps(payload))
            first_frame = False

            self._collect_xfyun_messages(ws, results, stop_on_final=is_last)
            time.sleep(0.04)

        if not pcm_data:
            ws.send(json.dumps(self._build_xfyun_frame(app_id, b"", 2, include_business=True)))
            self._collect_xfyun_messages(ws, results, stop_on_final=True)
        return results

    @staticmethod
    def _build_xfyun_frame(app_id: str, audio: bytes, status: int, include_business: bool) -> dict:
        payload = {
            "data": {
                "status": status,
                "format": "audio/L16;rate={}".format(config.SAMPLE_RATE),
                "encoding": "raw",
                "audio": base64.b64encode(audio).decode("utf-8"),
            }
        }
        if include_business:
            payload["common"] = {"app_id": app_id}
            payload["business"] = {
                "language": config.XFYUN_LANGUAGE,
                "domain": config.XFYUN_DOMAIN,
                "accent": config.XFYUN_ACCENT,
            }
        return payload

    def _collect_xfyun_messages(self, ws, results: list, stop_on_final: bool) -> None:
        while True:
            ws.settimeout(0.2 if not stop_on_final else 5)
            try:
                message = ws.recv()
            except Exception:
                if stop_on_final:
                    raise
                return

            body = json.loads(message)
            code = body.get("code", 0)
            if code != 0:
                raise RuntimeError(
                    "讯飞 ASR 失败 code={} message={} sid={}".format(
                        code,
                        body.get("message"),
                        body.get("sid"),
                    )
                )
            text = self._extract_xfyun_text(body)
            if text:
                results.append(text)
            if body.get("data", {}).get("status") == 2:
                return
            if not stop_on_final:
                return

    @staticmethod
    def _extract_xfyun_text(body: dict) -> str:
        result = body.get("data", {}).get("result", {})
        words = []
        for item in result.get("ws", []):
            for candidate in item.get("cw", []):
                words.append(candidate.get("w", ""))
        return "".join(words)

    @staticmethod
    def _import_websocket():
        try:
            import websocket

            return websocket
        except ImportError as exc:
            raise RuntimeError("缺少 websocket-client，请先运行 pip3 install -r requirements.txt") from exc

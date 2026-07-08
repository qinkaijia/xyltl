from voice.voice_text_player import VoiceTextPlayer, extract_voice_text


def test_extract_voice_text_from_evaluate_response():
    payload = {"final_status": {"voice_text": "当前设备处于预警状态。"}}
    assert extract_voice_text(payload) == "当前设备处于预警状态。"


def test_print_player_speaks(capsys):
    ok = VoiceTextPlayer("print").speak("测试播报")
    captured = capsys.readouterr()
    assert ok is True
    assert "测试播报" in captured.out


def test_audio_mode_falls_back_when_file_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VOICE_AUDIO_DIR", str(tmp_path))
    ok = VoiceTextPlayer("audio").speak("当前设备处于报警状态。")
    captured = capsys.readouterr()
    assert ok is False
    assert "预录音频不存在" in captured.out


def test_baidu_mode_routes_to_baidu_speaker(monkeypatch):
    spoken = []

    def fake_speak_baidu(self, text):
        spoken.append(text)
        return True

    monkeypatch.setattr(VoiceTextPlayer, "_speak_baidu", fake_speak_baidu)

    ok = VoiceTextPlayer("baidu").speak("当前设备处于报警状态。")

    assert ok is True
    assert spoken == ["当前设备处于报警状态。"]

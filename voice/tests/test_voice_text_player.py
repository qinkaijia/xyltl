from voice.voice_text_player import VoiceTextPlayer, extract_voice_text


def test_extract_voice_text_from_evaluate_response():
    payload = {"final_status": {"voice_text": "当前设备处于预警状态。"}}
    assert extract_voice_text(payload) == "当前设备处于预警状态。"


def test_print_player_speaks(capsys):
    ok = VoiceTextPlayer("print").speak("测试播报")
    captured = capsys.readouterr()
    assert ok is True
    assert "测试播报" in captured.out

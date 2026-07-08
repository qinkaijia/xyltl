from voice_llm_demo.main import next_wake_armed_until, run_once


class FakeRecorder:
    def record_once(self):
        return "fake.wav"


class FakeASR:
    def __init__(self, text):
        self.text = text

    def transcribe(self, _audio_path):
        return self.text


class FakeDeviceState:
    def update_simulated_data(self):
        pass

    def get_context(self):
        return {"temperature": 25}


class FakeLLM:
    def __init__(self):
        self.last_text = ""

    def analyze(self, text, _device_context):
        self.last_text = text
        return {
            "intent": "GENERAL_QA",
            "need_execute": False,
            "need_confirm": False,
            "params": {},
            "reply": "ok",
            "provider": "fake",
        }


class FakeSafety:
    def check(self, _llm_result):
        return True, "ok"

    def need_confirm(self, _llm_result):
        return False


class FakeDispatcher:
    def execute(self, _intent, _params):
        return True, "done"


class FakeSpeaker:
    def __init__(self):
        self.spoken = []

    def speak(self, text):
        self.spoken.append(text)


def test_wake_word_only_arms_next_utterance():
    speaker = FakeSpeaker()

    outcome = run_once(
        FakeRecorder(),
        FakeASR("hello"),
        FakeDeviceState(),
        FakeLLM(),
        FakeSafety(),
        FakeDispatcher(),
        speaker=speaker,
        wake_required=True,
        wake_words=["hello"],
    )

    assert outcome == "armed"
    assert speaker.spoken == ["我在，请说。"]


def test_active_wake_session_processes_next_utterance_without_wake_word():
    llm = FakeLLM()

    outcome = run_once(
        FakeRecorder(),
        FakeASR("what is the status"),
        FakeDeviceState(),
        llm,
        FakeSafety(),
        FakeDispatcher(),
        wake_required=True,
        wake_words=["hello"],
        wake_session_active=True,
    )

    assert outcome == "handled"
    assert llm.last_text == "what is the status"


def test_answer_extends_wake_session_window():
    until = next_wake_armed_until(
        outcome="handled",
        wake_required=True,
        wake_window_seconds=10.0,
        current_until=0.0,
        now=100.0,
    )

    assert until == 110.0


def test_expired_wake_session_clears_window():
    until = next_wake_armed_until(
        outcome="record_error",
        wake_required=True,
        wake_window_seconds=10.0,
        current_until=105.0,
        now=106.0,
    )

    assert until == 0.0

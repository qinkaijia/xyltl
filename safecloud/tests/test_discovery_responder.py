import json

from discovery_responder import build_response


def test_build_discovery_response_uses_public_host():
    data = json.loads(build_response(("192.168.43.36", 12345), 8010, "192.168.43.5").decode("utf-8"))
    assert data["service"] == "SafeCloud"
    assert data["base_url"] == "http://192.168.43.5:8010"
    assert data["port"] == 8010

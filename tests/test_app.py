from dataclasses import asdict

from fastapi.testclient import TestClient

from liveline.server import CaptionHub, create_app
from liveline.session import LiveSession, SessionConfig, SessionStatus
from liveline.types import Caption


def test_status_endpoint():
    session = LiveSession()
    app = create_app(session=session, hub=CaptionHub())
    client = TestClient(app)
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert "running" in body
    assert "loopback_ok" in body


def test_home_and_overlay_pages():
    app = create_app(session=LiveSession(), hub=CaptionHub())
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert "Start subtitles" in client.get("/").text
    assert client.get("/overlay").status_code == 200
    assert "Waiting for speech" in client.get("/overlay").text


def test_start_system_without_loopback_returns_400(monkeypatch):
    import liveline.server as server

    monkeypatch.setattr(server, "find_loopback_device", lambda: None)
    app = create_app(session=LiveSession(), hub=CaptionHub())
    client = TestClient(app)
    r = client.post("/api/start", json={"source": "system", "source_lang": "ko", "target_lang": "en"})
    assert r.status_code == 400
    assert "BlackHole" in r.json()["detail"]


def test_session_status_defaults():
    st = SessionStatus()
    d = asdict(st)
    assert d["running"] is False
    assert d["captions"] == 0


def test_caption_dataclass():
    c = Caption(original="안녕", translated="hi", language="ko")
    assert c.translated == "hi"

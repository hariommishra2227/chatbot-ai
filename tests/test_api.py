from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_admin_requires_key():
    response = client.get("/api/admin/documents")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid admin credentials"


def test_chat_validation_hides_internal_details():
    response = client.post("/api/chat", json={"message": " "})
    assert response.status_code == 422
    assert "traceback" not in response.text.lower()


def test_lead_validation():
    response = client.post("/api/leads", json={"name": "A", "company": "B", "email": "bad", "phone": "x", "requirement": "hi"})
    assert response.status_code == 422


def test_static_interface():
    response = client.get("/")
    assert response.status_code == 200
    assert "Company Assistant" in response.text
    assert 'id="microphone"' in response.text
    assert 'value="en-IN"' in response.text
    assert 'value="hi-IN"' in response.text


def test_voice_implementation_is_browser_only():
    response = client.get("/app.js")
    assert response.status_code == 200
    script = response.text
    assert "webkitSpeechRecognition" in script
    assert "speechSynthesis" in script
    assert "recognition.start()" in script
    assert "/api/transcription" not in script
    assert "/api/tts" not in script

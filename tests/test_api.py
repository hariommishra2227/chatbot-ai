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


def test_admin_dashboard_requires_authentication_and_uses_http_only_session():
    login_page = client.get("/admin")
    assert login_page.status_code == 200
    assert "Document Admin" in login_page.text
    assert "Manage the private retrieval index" not in login_page.text
    denied = client.post("/admin/login", data={"api_key": "wrong"})
    assert denied.status_code == 401
    authenticated = client.post("/admin/login", data={"api_key": "test-admin-api-key-at-least-24"}, follow_redirects=False)
    assert authenticated.status_code == 303
    assert "httponly" in authenticated.headers["set-cookie"].lower()
    dashboard = client.get("/admin")
    assert "Manage the private retrieval index" in dashboard.text
    assert "test-admin-api-key-at-least-24" not in dashboard.text


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

import pytest


@pytest.fixture
def token(client):
    r = client.post("/auth/register", json={"email": "ai@test.com", "password": "pass123"})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": "ai@test.com", "password": "pass123"})
    assert r.status_code in (200, 201)
    if r.status_code == 201:
        r = client.post("/auth/login", json={"email": "ai@test.com", "password": "pass123"})
    assert r.status_code == 200
    return r.json()["access_token"]


class TestAIAssistant:
    def test_config_no_key(self, client, token):
        r = client.get("/ai/config", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["configured"] is False

    def test_generate_fallback(self, client, token):
        r = client.post(
            "/ai/generate",
            json={"prompt": "Write a welcome email", "subject": "Welcome", "tone": "friendly"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "result" in data

    def test_reply_fallback(self, client, token):
        r = client.post(
            "/ai/reply",
            json={"original_email": "Thanks for your help", "tone": "professional"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert "result" in r.json()

    def test_summarize_fallback(self, client, token):
        r = client.post(
            "/ai/summarize",
            json={"subject": "Meeting notes", "body": "We discussed the project timeline and agreed on Q3 delivery"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert "result" in r.json()

    def test_translate_fallback(self, client, token):
        r = client.post(
            "/ai/translate",
            json={"text": "Hello, how are you?", "source_lang": "english", "target_lang": "french"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert "result" in r.json()

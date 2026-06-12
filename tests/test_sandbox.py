import pytest


@pytest.fixture
def token(client):
    r = client.post("/auth/register", json={"email": "sandbox@test.com", "password": "pass123"})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": "sandbox@test.com", "password": "pass123"})
    assert r.status_code in (200, 201)
    if r.status_code == 201:
        r = client.post("/auth/login", json={"email": "sandbox@test.com", "password": "pass123"})
    assert r.status_code == 200
    return r.json()["access_token"]


class TestSandbox:
    def test_send_captures_email(self, client, token):
        r = client.post(
            "/sandbox/send",
            json={"to": "test@example.com", "subject": "Hello", "body_text": "World"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "captured"
        assert data["capture_id"]

    def test_preview_capture(self, client, token):
        r = client.post(
            "/sandbox/send",
            json={"to": "preview@test.com", "subject": "Preview", "body_text": "Test preview", "body_html": "<p>Test</p>"},
            headers={"Authorization": f"Bearer {token}"},
        )
        cid = r.json()["capture_id"]
        r2 = client.get(f"/sandbox/preview/{cid}", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200
        assert r2.json()["to"] == "preview@test.com"
        assert r2.json()["body_html"] == "<p>Test</p>"

    def test_preview_other_user_returns_404(self, client, token):
        r = client.post(
            "/sandbox/send",
            json={"to": "a@b.com", "subject": "S", "body_text": "B"},
            headers={"Authorization": f"Bearer {token}"},
        )
        cid = r.json()["capture_id"]
        email = "other_sandbox@test.com"
        r2 = client.post("/auth/register", json={"email": email, "password": "pass123"})
        if r2.status_code == 409:
            r2 = client.post("/auth/login", json={"email": email, "password": "pass123"})
        assert r2.status_code in (200, 201)
        if r2.status_code == 201:
            r2 = client.post("/auth/login", json={"email": email, "password": "pass123"})
        assert r2.status_code == 200
        other_token = r2.json()["access_token"]
        r3 = client.get(f"/sandbox/preview/{cid}", headers={"Authorization": f"Bearer {other_token}"})
        assert r3.status_code == 404

    def test_list_captures(self, client, token):
        r = client.get("/sandbox/captures", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

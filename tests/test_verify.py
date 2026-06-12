import pytest


@pytest.fixture
def token(client):
    r = client.post("/auth/register", json={"email": "verify@test.com", "password": "pass123"})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": "verify@test.com", "password": "pass123"})
    assert r.status_code in (201, 200)
    if r.status_code == 201:
        r = client.post("/auth/login", json={"email": "verify@test.com", "password": "pass123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


class TestVerify:
    def test_invalid_email(self, client, token):
        r = client.post("/verify-email", json={"email": "notanemail"}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["valid"] is False

    def test_valid_syntax(self, client, token):
        r = client.post("/verify-email", json={"email": "test@gmail.com"}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["risk"] in ("low", "high")

    def test_disposable_detected(self, client, token):
        r = client.post("/verify-email", json={"email": "test@mailinator.com"}, headers={"Authorization": f"Bearer {token}"})
        assert r.json()["disposable"] is True

    def test_unauthorized(self, client):
        r = client.post("/verify-email", json={"email": "test@test.com"})
        assert r.status_code in (401, 403)

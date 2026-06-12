import pytest


@pytest.fixture
def token(client):
    r = client.post("/auth/register", json={"email": "2fa@test.com", "password": "pass123"})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": "2fa@test.com", "password": "pass123"})
    assert r.status_code in (201, 200)
    if r.status_code == 201:
        r = client.post("/auth/login", json={"email": "2fa@test.com", "password": "pass123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


class Test2FA:
    def test_setup_2fa(self, client, token):
        r = client.post("/2fa/setup", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert "secret" in data
        assert "qr_code" in data
        assert "uri" in data

    def test_setup_duplicate(self, client, token):
        client.post("/2fa/setup", headers={"Authorization": f"Bearer {token}"})
        r = client.post("/2fa/setup", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 409

    def test_status_not_configured(self, client, token):
        r = client.get("/2fa/status", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["configured"] is False

    def test_status_configured(self, client, token):
        client.post("/2fa/setup", headers={"Authorization": f"Bearer {token}"})
        r = client.get("/2fa/status", headers={"Authorization": f"Bearer {token}"})
        assert r.json()["configured"] is True
        assert r.json()["enabled"] is False

    def test_verify_invalid_code(self, client, token):
        client.post("/2fa/setup", headers={"Authorization": f"Bearer {token}"})
        r = client.post("/2fa/verify", json={"code": "000000"}, headers={"Authorization": f"Bearer {token}"})
        assert r.json()["verified"] is False

    def test_disable_2fa(self, client, token):
        client.post("/2fa/setup", headers={"Authorization": f"Bearer {token}"})
        r = client.post("/2fa/disable", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        r = client.get("/2fa/status", headers={"Authorization": f"Bearer {token}"})
        assert r.json()["configured"] is False

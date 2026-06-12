import pytest


@pytest.fixture
def token(client):
    r = client.post("/auth/register", json={"email": "user@mail.com", "password": "pass123"})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": "user@mail.com", "password": "pass123"})
    assert r.status_code in (201, 200), f"Setup failed: {r.json()}"
    if r.status_code == 201:
        r = client.post("/auth/login", json={"email": "user@mail.com", "password": "pass123"})
    assert r.status_code == 200, f"Login failed: {r.json()}"
    data = r.json()
    assert "access_token" in data, f"No access_token: {data}"
    return data["access_token"]


class TestVacation:
    def test_get_default(self, client, token):
        r = client.get("/mail/settings/vacation", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["enabled"] is False

    def test_set_and_get(self, client, token):
        r = client.put(
            "/mail/settings/vacation",
            json={"subject": "OOO", "body": "Away", "enabled": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["subject"] == "OOO"
        assert r.json()["enabled"] is True

        r = client.get("/mail/settings/vacation", headers={"Authorization": f"Bearer {token}"})
        assert r.json()["subject"] == "OOO"


class TestForwarding:
    def test_empty_list(self, client, token):
        r = client.get("/mail/settings/forwarding", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json() == []

    def test_add_and_list(self, client, token):
        r = client.post(
            "/mail/settings/forwarding",
            json={"target_email": "fwd@other.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201
        rid = r.json()["id"]

        r = client.get("/mail/settings/forwarding", headers={"Authorization": f"Bearer {token}"})
        assert len(r.json()) == 1
        assert r.json()[0]["target_email"] == "fwd@other.com"

        r = client.delete(f"/mail/settings/forwarding/{rid}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 204

        r = client.get("/mail/settings/forwarding", headers={"Authorization": f"Bearer {token}"})
        assert r.json() == []

    def test_delete_not_found(self, client, token):
        r = client.delete("/mail/settings/forwarding/999", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404

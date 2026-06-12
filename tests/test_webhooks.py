import pytest


@pytest.fixture
def admin_token(client):
    r = client.post("/auth/register", json={"email": "wh-admin@test.com", "password": "admin123"})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": "wh-admin@test.com", "password": "admin123"})
    assert r.status_code in (201, 200), f"Setup failed: {r.json()}"
    if r.status_code == 201:
        r = client.post("/auth/login", json={"email": "wh-admin@test.com", "password": "admin123"})
    assert r.status_code == 200, f"Login failed: {r.json()}"
    data = r.json()
    assert "access_token" in data, f"No access_token: {data}"
    return data["access_token"]


@pytest.fixture
def user_token(client, admin_token):
    r = client.post(
        "/admin/domains",
        json={"domain": "wh-test.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        "/admin/users",
        json={"email": "wh-user@wh-test.com", "password": "user123"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    r = client.post("/auth/login", json={"email": "wh-user@wh-test.com", "password": "user123"})
    return r.json()["access_token"]


class TestWebhookCRUD:
    def test_create_webhook(self, client, user_token):
        r = client.post(
            "/webhooks",
            json={"url": "https://hooks.example.com/1", "events": ["email.received"]},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["url"] == "https://hooks.example.com/1"
        assert "secret" in data
        assert "id" in data

    def test_create_webhook_invalid_event(self, client, user_token):
        r = client.post(
            "/webhooks",
            json={"url": "https://hooks.example.com/bad", "events": ["invalid.event"]},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert r.status_code == 400

    def test_list_webhooks(self, client, user_token):
        client.post(
            "/webhooks",
            json={"url": "https://hooks.example.com/list", "events": ["email.sent"]},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        r = client.get("/webhooks", headers={"Authorization": f"Bearer {user_token}"})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert any(h["url"] == "https://hooks.example.com/list" for h in data)

    def test_update_webhook(self, client, user_token):
        r = client.post(
            "/webhooks",
            json={"url": "https://hooks.example.com/upd", "events": ["email.received"]},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        wid = r.json()["id"]
        r = client.put(
            f"/webhooks/{wid}",
            json={"url": "https://hooks.example.com/updated", "active": False},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert r.status_code == 200
        assert r.json()["url"] == "https://hooks.example.com/updated"
        assert r.json()["active"] is False

    def test_delete_webhook(self, client, user_token):
        r = client.post(
            "/webhooks",
            json={"url": "https://hooks.example.com/del", "events": ["email.received"]},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        wid = r.json()["id"]
        r = client.delete(f"/webhooks/{wid}", headers={"Authorization": f"Bearer {user_token}"})
        assert r.status_code == 204

    def test_webhooks_require_auth(self, client):
        r = client.get("/webhooks")
        assert r.status_code in (401, 403)

    def test_webhook_isolation(self, client, user_token, admin_token):
        r = client.post(
            "/webhooks",
            json={"url": "https://hooks.a.com", "events": ["email.received"]},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        r = client.get("/webhooks", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        assert len(r.json()) == 0


class TestWebhookValidation:
    def test_create_multiple_events(self, client, user_token):
        r = client.post(
            "/webhooks",
            json={
                "url": "https://hooks.example.com/multi",
                "events": ["email.received", "email.sent", "user.created"],
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert r.status_code == 201
        assert len(r.json()["events"]) == 3

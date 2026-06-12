import pytest


@pytest.fixture
def token(client):
    r = client.post("/auth/register", json={"email": "apikey@test.com", "password": "pass123"})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": "apikey@test.com", "password": "pass123"})
    assert r.status_code in (201, 200)
    if r.status_code == 201:
        r = client.post("/auth/login", json={"email": "apikey@test.com", "password": "pass123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


class TestApiKeys:
    def test_create_api_key(self, client, token):
        r = client.post("/api-keys", json={"name": "My Key"}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 201
        data = r.json()
        assert "full_key" in data
        assert data["name"] == "My Key"
        assert data["key_prefix"] == data["full_key"][:8]

    def test_list_api_keys(self, client, token):
        client.post("/api-keys", json={"name": "Key 1"}, headers={"Authorization": f"Bearer {token}"})
        client.post("/api-keys", json={"name": "Key 2"}, headers={"Authorization": f"Bearer {token}"})
        r = client.get("/api-keys", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2

    def test_revoke_api_key(self, client, token):
        create = client.post("/api-keys", json={"name": "To Delete"}, headers={"Authorization": f"Bearer {token}"})
        key_id = create.json()["id"]
        r = client.delete(f"/api-keys/{key_id}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 204
        r = client.get("/api-keys", headers={"Authorization": f"Bearer {token}"})
        keys = r.json()
        assert keys[0]["active"] is False

    def test_authenticate_with_api_key(self, client, token):
        create = client.post("/api-keys", json={"name": "API"}, headers={"Authorization": f"Bearer {token}"})
        full_key = create.json()["full_key"]
        r = client.get("/auth/me", headers={"X-Api-Key": full_key})
        assert r.status_code == 200
        assert r.json()["email"] == "apikey@test.com"

    def test_invalid_api_key(self, client):
        r = client.get("/auth/me", headers={"X-Api-Key": "invalid-key-12345"})
        assert r.status_code == 401

    def test_create_unauthorized(self, client):
        r = client.post("/api-keys", json={"name": "No Auth"})
        assert r.status_code in (401, 403)

    def test_revoke_not_found(self, client, token):
        r = client.delete("/api-keys/99999", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404

    def test_api_key_isolation(self, client, token):
        r1 = client.post("/api-keys", json={"name": "User1"}, headers={"Authorization": f"Bearer {token}"})
        key1 = r1.json()["full_key"]
        r = client.post("/auth/register", json={"email": "other@test.com", "password": "pass456"})
        if r.status_code == 201:
            r = client.post("/auth/login", json={"email": "other@test.com", "password": "pass456"})
        else:
            r = client.post("/auth/login", json={"email": "other@test.com", "password": "pass456"})
        token2 = r.json()["access_token"]
        r2 = client.post("/api-keys", json={"name": "User2"}, headers={"Authorization": f"Bearer {token2}"})
        key2 = r2.json()["full_key"]
        r = client.get("/auth/me", headers={"X-Api-Key": key1})
        assert r.json()["email"] == "apikey@test.com"
        r = client.get("/auth/me", headers={"X-Api-Key": key2})
        assert r.json()["email"] == "other@test.com"

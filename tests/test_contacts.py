import pytest


@pytest.fixture
def token(client):
    r = client.post("/auth/register", json={"email": "contact@test.com", "password": "pass123"})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": "contact@test.com", "password": "pass123"})
    assert r.status_code in (201, 200)
    if r.status_code == 201:
        r = client.post("/auth/login", json={"email": "contact@test.com", "password": "pass123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


class TestContacts:
    def test_create_contact(self, client, token):
        r = client.post("/contacts", json={"email": "alice@example.com", "name": "Alice"}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 201
        assert r.json()["email"] == "alice@example.com"

    def test_create_duplicate(self, client, token):
        client.post("/contacts", json={"email": "dup@example.com"}, headers={"Authorization": f"Bearer {token}"})
        r = client.post("/contacts", json={"email": "dup@example.com"}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 409

    def test_list_contacts(self, client, token):
        client.post("/contacts", json={"email": "a@example.com", "name": "A"}, headers={"Authorization": f"Bearer {token}"})
        client.post("/contacts", json={"email": "b@example.com", "name": "B"}, headers={"Authorization": f"Bearer {token}"})
        r = client.get("/contacts", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_get_contact(self, client, token):
        create = client.post("/contacts", json={"email": "get@example.com"}, headers={"Authorization": f"Bearer {token}"})
        cid = create.json()["id"]
        r = client.get(f"/contacts/{cid}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["email"] == "get@example.com"

    def test_update_contact(self, client, token):
        create = client.post("/contacts", json={"email": "upd@example.com", "name": "Old"}, headers={"Authorization": f"Bearer {token}"})
        cid = create.json()["id"]
        r = client.put(f"/contacts/{cid}", json={"name": "New"}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["name"] == "New"

    def test_delete_contact(self, client, token):
        create = client.post("/contacts", json={"email": "del@example.com"}, headers={"Authorization": f"Bearer {token}"})
        cid = create.json()["id"]
        r = client.delete(f"/contacts/{cid}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 204

    def test_not_found(self, client, token):
        r = client.get("/contacts/99999", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404

    def test_export_csv(self, client, token):
        client.post("/contacts", json={"email": "csv@example.com", "name": "CSV"}, headers={"Authorization": f"Bearer {token}"})
        r = client.get("/contacts/export/csv", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert "csv@example.com" in r.text
        assert "text/csv" in r.headers.get("content-type", "")

    def test_import_csv(self, client, token):
        csv_data = "email,name,notes\nin1@test.com,One,note1\nin2@test.com,Two,note2"
        r = client.post("/contacts/import/csv", json={"csv": csv_data}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 201
        assert r.json()["imported"] == 2
        r = client.get("/contacts", headers={"Authorization": f"Bearer {token}"})
        assert len(r.json()) == 2

    def test_isolation(self, client, token):
        r = client.post("/auth/register", json={"email": "other@test.com", "password": "pass456"})
        if r.status_code == 201:
            r = client.post("/auth/login", json={"email": "other@test.com", "password": "pass456"})
        else:
            r = client.post("/auth/login", json={"email": "other@test.com", "password": "pass456"})
        token2 = r.json()["access_token"]
        client.post("/contacts", json={"email": "user1@test.com"}, headers={"Authorization": f"Bearer {token}"})
        client.post("/contacts", json={"email": "user2@test.com"}, headers={"Authorization": f"Bearer {token2}"})
        r1 = client.get("/contacts", headers={"Authorization": f"Bearer {token}"})
        r2 = client.get("/contacts", headers={"Authorization": f"Bearer {token2}"})
        assert len(r1.json()) == 1
        assert len(r2.json()) == 1

    def test_unauthorized(self, client):
        r = client.get("/contacts")
        assert r.status_code in (401, 403)

    def test_search(self, client, token):
        client.post("/contacts", json={"email": "findme@example.com", "name": "Findable"}, headers={"Authorization": f"Bearer {token}"})
        client.post("/contacts", json={"email": "hidden@example.com"}, headers={"Authorization": f"Bearer {token}"})
        r = client.get("/contacts?search=find", headers={"Authorization": f"Bearer {token}"})
        assert len(r.json()) == 1
        assert r.json()[0]["email"] == "findme@example.com"

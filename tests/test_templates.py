import pytest


@pytest.fixture
def token(client):
    r = client.post("/auth/register", json={"email": "tmpl@test.com", "password": "pass123"})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": "tmpl@test.com", "password": "pass123"})
    assert r.status_code in (201, 200)
    if r.status_code == 201:
        r = client.post("/auth/login", json={"email": "tmpl@test.com", "password": "pass123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


class TestTemplates:
    def test_create_template(self, client, token):
        r = client.post("/templates", json={"name": "Welcome", "subject": "Welcome {{name}}!", "body_html": "<p>Hello {{name}}</p>"}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 201
        assert r.json()["variables"] == ["name"]

    def test_list_templates(self, client, token):
        client.post("/templates", json={"name": "A", "subject": "A"}, headers={"Authorization": f"Bearer {token}"})
        client.post("/templates", json={"name": "B", "subject": "B"}, headers={"Authorization": f"Bearer {token}"})
        r = client.get("/templates", headers={"Authorization": f"Bearer {token}"})
        assert len(r.json()) == 2

    def test_get_template(self, client, token):
        create = client.post("/templates", json={"name": "Get", "subject": "Get {{x}}"}, headers={"Authorization": f"Bearer {token}"})
        tid = create.json()["id"]
        r = client.get(f"/templates/{tid}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["variables"] == ["x"]

    def test_update_template(self, client, token):
        create = client.post("/templates", json={"name": "Old", "subject": "Old"}, headers={"Authorization": f"Bearer {token}"})
        tid = create.json()["id"]
        r = client.put(f"/templates/{tid}", json={"subject": "New {{var}}"}, headers={"Authorization": f"Bearer {token}"})
        assert r.json()["variables"] == ["var"]

    def test_delete_template(self, client, token):
        create = client.post("/templates", json={"name": "Del", "subject": "Del"}, headers={"Authorization": f"Bearer {token}"})
        tid = create.json()["id"]
        r = client.delete(f"/templates/{tid}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 204

    def test_render_template(self, client, token):
        create = client.post("/templates", json={"name": "Render", "subject": "Hi {{name}}!", "body_text": "Hello {{name}}"}, headers={"Authorization": f"Bearer {token}"})
        tid = create.json()["id"]
        r = client.post("/templates/render", json={"template_id": tid, "variables": {"name": "Alice"}}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["subject"] == "Hi Alice!"
        assert r.json()["body_text"] == "Hello Alice"

    def test_not_found(self, client, token):
        r = client.get("/templates/99999", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404

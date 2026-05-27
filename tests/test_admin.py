import pytest


@pytest.fixture
def admin_token(client):
    client.post("/auth/register", json={"email": "admin@test.com", "password": "admin123"})
    r = client.post("/auth/login", json={"email": "admin@test.com", "password": "admin123"})
    return r.json()["access_token"]


@pytest.fixture
def user_token(client, admin_token):
    r = client.post(
        "/admin/domains",
        json={"domain": "example.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    r = client.post(
        "/admin/users",
        json={"email": "user@example.com", "password": "user123"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    r = client.post("/auth/login", json={"email": "user@example.com", "password": "user123"})
    return r.json()["access_token"]


class TestDomains:
    def test_create_domain(self, client, admin_token):
        r = client.post(
            "/admin/domains",
            json={"domain": "newdomain.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201
        assert r.json()["domain"] == "newdomain.com"

    def test_create_duplicate_domain(self, client, admin_token):
        client.post(
            "/admin/domains",
            json={"domain": "dup.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        r = client.post(
            "/admin/domains",
            json={"domain": "dup.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200

    def test_list_domains(self, client, admin_token):
        client.post(
            "/admin/domains",
            json={"domain": "list1.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        r = client.get("/admin/domains", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        domains = [d["domain"] for d in r.json()]
        assert "list1.com" in domains

    def test_get_domain(self, client, admin_token):
        r = client.post(
            "/admin/domains",
            json={"domain": "getme.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        did = r.json()["id"]
        r = client.get(f"/admin/domains/{did}", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        assert r.json()["domain"] == "getme.com"

    def test_delete_domain(self, client, admin_token):
        r = client.post(
            "/admin/domains",
            json={"domain": "delme.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        did = r.json()["id"]
        r = client.delete(f"/admin/domains/{did}", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 204

    def test_forbidden_non_admin(self, client, user_token):
        r = client.get("/admin/domains", headers={"Authorization": f"Bearer {user_token}"})
        assert r.status_code == 403


class TestUsers:
    def test_create_user(self, client, admin_token):
        client.post(
            "/admin/domains",
            json={"domain": "myorg.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        r = client.post(
            "/admin/users",
            json={"email": "emp@myorg.com", "password": "emp123"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201
        assert r.json()["email"] == "emp@myorg.com"

    def test_list_users(self, client, admin_token):
        r = client.get("/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200

    def test_get_user(self, client, admin_token):
        r = client.get("/admin/users/1", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200

    def test_delete_user(self, client, admin_token):
        client.post(
            "/admin/domains",
            json={"domain": "org2.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        r = client.post(
            "/admin/users",
            json={"email": "del@org2.com", "password": "del123"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        uid = r.json()["id"]
        r = client.delete(f"/admin/users/{uid}", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 204

    def test_update_password(self, client, admin_token):
        r = client.put(
            "/admin/users/1/password",
            json={"password": "newpass123"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200


class TestMailboxes:
    def test_create_mailbox(self, client, admin_token):
        client.post(
            "/admin/users",
            json={"email": "boxuser@test.com", "password": "box123"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        r = client.post(
            "/admin/mailboxes",
            json={"email": "boxuser@test.com", "quota_mb": 256},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201
        assert r.json()["email"] == "boxuser@test.com"

    def test_list_mailboxes(self, client, admin_token):
        r = client.get("/admin/mailboxes", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200

    def test_delete_mailbox(self, client, admin_token):
        r = client.get("/admin/mailboxes", headers={"Authorization": f"Bearer {admin_token}"})
        if r.json():
            mid = r.json()[0]["id"]
            r = client.delete(f"/admin/mailboxes/{mid}", headers={"Authorization": f"Bearer {admin_token}"})
            assert r.status_code == 204


class TestAliases:
    def test_create_alias(self, client, admin_token):
        r = client.post(
            "/admin/aliases",
            json={"source": "info@test.com", "target": "admin@test.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201
        assert r.json()["source"] == "info@test.com"

    def test_list_aliases(self, client, admin_token):
        r = client.get("/admin/aliases", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200

    def test_delete_alias(self, client, admin_token):
        r = client.post(
            "/admin/aliases",
            json={"source": "del@test.com", "target": "admin@test.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        aid = r.json()["id"]
        r = client.delete(f"/admin/aliases/{aid}", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 204

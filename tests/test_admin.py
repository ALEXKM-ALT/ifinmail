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
        data = r.json()
        assert "items" in data
        assert "pagination" in data
        domains = [d["domain"] for d in data["items"]]
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

    def test_update_domain(self, client, admin_token):
        r = client.post(
            "/admin/domains",
            json={"domain": "updateme.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        did = r.json()["id"]
        r = client.put(
            f"/admin/domains/{did}",
            json={"verified": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.json()["verified"] is True

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
        data = r.json()
        assert "items" in data
        assert "pagination" in data

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

    def test_create_user_with_name(self, client, admin_token):
        client.post(
            "/admin/domains",
            json={"domain": "namedomain.com"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        r = client.post(
            "/admin/users",
            json={"email": "john@namedomain.com", "password": "pass123", "first_name": "John", "last_name": "Doe"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201
        assert r.json()["first_name"] == "John"
        assert r.json()["last_name"] == "Doe"


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


class TestStats:
    def test_get_stats(self, client, admin_token):
        r = client.get("/admin/stats", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        data = r.json()
        assert "total_users" in data
        assert "total_domains" in data
        assert "active_today" in data
        assert "total_aliases" in data

    def test_stats_growth(self, client, admin_token):
        r = client.get("/admin/stats/growth", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_stats_emails(self, client, admin_token):
        r = client.get("/admin/stats/emails", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestBilling:
    def test_list_plans(self, client, admin_token):
        r = client.get("/admin/billing/plans", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        plans = r.json()
        assert isinstance(plans, list)
        assert any(p["id"] == "free" for p in plans)

    def test_update_plan(self, client, admin_token):
        r = client.put(
            "/admin/billing/plans/free",
            json={"price": 0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.json()["price"] == 0

    def test_list_subscriptions(self, client, admin_token):
        r = client.get("/admin/billing/subscriptions", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200


class TestSecurity:
    def test_list_events(self, client, admin_token):
        r = client.get("/admin/security/events", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200

    def test_create_security_event(self, client, admin_token):
        r = client.post(
            "/admin/security/events",
            json={"event_type": "login_failed", "description": "Test event", "ip_address": "1.2.3.4"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201
        assert r.json()["event_type"] == "login_failed"

    def test_clear_events(self, client, admin_token):
        r = client.delete("/admin/security/events", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 204


class TestBackups:
    def test_list_backups(self, client, admin_token):
        r = client.get("/admin/system/backups", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200


class TestSystem:
    def test_system_health(self, client, admin_token):
        r = client.get("/admin/system/health", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        assert "status" in r.json()


class TestAdminUserEmails:
    def test_user_emails(self, client, admin_token):
        r = client.get("/admin/users/1/emails", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        data = r.json()
        assert "user" in data
        assert "items" in data
        assert "pagination" in data

    def test_user_emails_not_found(self, client, admin_token):
        r = client.get("/admin/users/9999/emails", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 404


class TestAdminImpersonate:
    def test_impersonate(self, client, admin_token):
        r = client.post("/admin/users/1/impersonate", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        data = r.json()
        assert "token" in data
        assert "message" in data

    def test_impersonate_not_found(self, client, admin_token):
        r = client.post("/admin/users/9999/impersonate", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 404


class TestAPIVersioning:
    def test_v1_admin_stats(self, client, admin_token):
        r = client.get("/v1/admin/stats", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200

    def test_v1_auth_me(self, client, admin_token):
        r = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200

    def test_v1_webhooks(self, client, admin_token):
        r = client.get("/v1/webhooks", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200


class TestOpenAPI:
    def test_openapi_json(self, client):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        data = r.json()
        assert data["info"]["version"] == "2.0.0"
        assert "x-versions" in data
        assert len(data["servers"]) == 2

    def test_openapi_versions(self, client):
        r = client.get("/openapi.json")
        data = r.json()
        versions = data["x-versions"]
        assert "v1" in versions["versions"]
        assert "v2" in versions["versions"]

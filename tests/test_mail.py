import pytest


@pytest.fixture
def token(client):
    client.post("/auth/register", json={"email": "user@mail.com", "password": "pass123"})
    r = client.post("/auth/login", json={"email": "user@mail.com", "password": "pass123"})
    return r.json()["access_token"]


class TestSend:
    def test_send_email(self, client, token):
        r = client.post(
            "/mail",
            json={"to": "other@mail.com", "subject": "Hello", "body_text": "World"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201
        assert r.json()["id"] is not None

    def test_send_without_subject(self, client, token):
        r = client.post(
            "/mail",
            json={"to": "other@mail.com", "body_text": "no subject"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201

    def test_send_unauthorized(self, client):
        r = client.post(
            "/mail",
            json={"to": "x@y.com", "subject": "x", "body_text": "x"},
        )
        assert r.status_code == 401


class TestList:
    def test_list_inbox(self, client, token):
        r = client.get("/mail?folder=INBOX", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_sent(self, client, token):
        r = client.get("/mail?folder=SENT", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_pagination(self, client, token):
        r = client.get(
            "/mail?page=1&per_page=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200

    def test_x_total_count_header(self, client, token):
        r = client.get("/mail?folder=INBOX", headers={"Authorization": f"Bearer {token}"})
        assert "x-total-count" in r.headers


class TestGet:
    def test_get_message(self, client, token):
        r = client.post(
            "/mail",
            json={"to": "x@mail.com", "subject": "Get me", "body_text": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        mid = r.json()["id"]

        r = client.get(f"/mail/{mid}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["subject"] == "Get me"

    def test_get_not_found(self, client, token):
        r = client.get("/mail/99999", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404


class TestPatch:
    def test_mark_read(self, client, token):
        r = client.post(
            "/mail",
            json={"to": "y@mail.com", "subject": "Read me", "body_text": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        mid = r.json()["id"]

        r = client.patch(
            f"/mail/{mid}",
            json={"read": True, "starred": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["read"] is True
        assert r.json()["starred"] is True


class TestMove:
    def test_move_to_trash(self, client, token):
        r = client.post(
            "/mail",
            json={"to": "z@mail.com", "subject": "Trash me", "body_text": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        mid = r.json()["id"]

        r = client.put(
            f"/mail/{mid}/move",
            json={"folder": "TRASH"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["folder"] == "TRASH"

    def test_move_invalid_folder(self, client, token):
        r = client.put(
            "/mail/1/move",
            json={"folder": "INVALID"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400


class TestDelete:
    def test_soft_delete(self, client, token):
        r = client.post(
            "/mail",
            json={"to": "d@mail.com", "subject": "Delete me", "body_text": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        mid = r.json()["id"]

        r = client.delete(f"/mail/{mid}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 204

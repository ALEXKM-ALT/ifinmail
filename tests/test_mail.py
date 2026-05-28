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


class TestFolderCounts:
    def test_folder_counts_returns_counts(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}

        r = client.get("/mail/folder-counts", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert "INBOX" not in data or data["INBOX"] >= 0

    def test_folder_counts_after_sending(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}

        r = client.get("/mail/folder-counts", headers=headers)
        assert r.status_code == 200
        before = r.json()

        client.post(
            "/mail",
            json={"to": "other@mail.com", "subject": "Count test", "body_text": "body"},
            headers=headers,
        )

        r = client.get("/mail/folder-counts", headers=headers)
        assert r.status_code == 200
        after = r.json()
        assert after.get("SENT", 0) >= before.get("SENT", 0)

    def test_folder_counts_unauthorized(self, client):
        r = client.get("/mail/folder-counts")
        assert r.status_code == 401


class TestCustomFolders:
    def test_create_folder(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post("/mail/folders", json={"name": "Work"}, headers=headers)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "WORK"

    def test_create_duplicate_folder(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        client.post("/mail/folders", json={"name": "Work"}, headers=headers)
        r = client.post("/mail/folders", json={"name": "Work"}, headers=headers)
        assert r.status_code == 409

    def test_create_reserved_name(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post("/mail/folders", json={"name": "INBOX"}, headers=headers)
        assert r.status_code == 400

    def test_list_folders(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        client.post("/mail/folders", json={"name": "Work"}, headers=headers)
        client.post("/mail/folders", json={"name": "Personal"}, headers=headers)
        r = client.get("/mail/folders", headers=headers)
        assert r.status_code == 200
        names = [f["name"] for f in r.json()]
        assert "WORK" in names
        assert "PERSONAL" in names

    def test_delete_folder(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post("/mail/folders", json={"name": "Temp"}, headers=headers)
        fid = r.json()["id"]
        r = client.delete(f"/mail/folders/{fid}", headers=headers)
        assert r.status_code == 204
        r = client.get("/mail/folders", headers=headers)
        assert all(f["name"] != "TEMP" for f in r.json())

    def test_move_to_custom_folder(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        client.post("/mail/folders", json={"name": "Projects"}, headers=headers)
        r = client.post(
            "/mail",
            json={"to": "x@y.com", "subject": "Project", "body_text": "body"},
            headers=headers,
        )
        mid = r.json()["id"]
        r = client.put(
            f"/mail/{mid}/move",
            json={"folder": "Projects"},
            headers=headers,
        )
        assert r.status_code == 200
        r = client.get(f"/mail/{mid}", headers=headers)
        assert r.json()["folder"] == "PROJECTS"

    def test_bulk_move_to_custom_folder(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        client.post("/mail/folders", json={"name": "Archive"}, headers=headers)
        ids = []
        for i in range(3):
            r = client.post(
                "/mail",
                json={"to": f"x{i}@y.com", "subject": f"Msg {i}", "body_text": "body"},
                headers=headers,
            )
            ids.append(r.json()["id"])
        r = client.post(
            "/mail/bulk-move",
            json={"ids": ids, "folder": "Archive"},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["moved"] == 3

    def test_move_to_invalid_custom_folder(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post(
            "/mail",
            json={"to": "x@y.com", "subject": "Test", "body_text": "body"},
            headers=headers,
        )
        mid = r.json()["id"]
        r = client.put(
            f"/mail/{mid}/move",
            json={"folder": "NonExistent"},
            headers=headers,
        )
        assert r.status_code == 400

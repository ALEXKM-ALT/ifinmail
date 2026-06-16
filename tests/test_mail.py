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
    assert "access_token" in data, f"No access_token in response: {data}"
    return data["access_token"]


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


class TestSmartReply:
    def test_suggest_reply_returns_suggestions(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post(
            "/mail",
            json={"to": "x@y.com", "subject": "Can you help?", "body_text": "I have a question about the project."},
            headers=headers,
        )
        mid = r.json()["id"]

        r = client.post(f"/mail/{mid}/suggest-reply", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) > 0
        assert all(isinstance(s, str) for s in data["suggestions"])

    def test_suggest_reply_not_found(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post("/mail/99999/suggest-reply", headers=headers)
        assert r.status_code == 404

    def test_suggest_reply_question_detection(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post(
            "/mail",
            json={"to": "q@y.com", "subject": "Quick question", "body_text": "Could you please review the doc?"},
            headers=headers,
        )
        mid = r.json()["id"]

        r = client.post(f"/mail/{mid}/suggest-reply", headers=headers)
        assert r.status_code == 200
        suggestions = r.json()["suggestions"]
        assert any("check" in s.lower() or "sure" in s.lower() or "thanks" in s.lower() for s in suggestions)

    def test_suggest_reply_thank_you_detection(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post(
            "/mail",
            json={"to": "t@y.com", "subject": "Thanks!", "body_text": "Thank you so much for your help."},
            headers=headers,
        )
        mid = r.json()["id"]

        r = client.post(f"/mail/{mid}/suggest-reply", headers=headers)
        assert r.status_code == 200
        suggestions = r.json()["suggestions"]
        assert any("welcome" in s.lower() or "glad" in s.lower() or "happy" in s.lower() for s in suggestions)


class TestSpamLearning:
    def test_report_spam(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post(
            "/mail",
            json={"to": "a@y.com", "subject": "Win a prize!", "body_text": "You won"},
            headers=headers,
        )
        mid = r.json()["id"]

        r = client.post(f"/mail/{mid}/report-spam", headers=headers)
        assert r.status_code == 200
        assert r.json()["message"] == "Message marked as spam"

        r = client.get(f"/mail/{mid}", headers=headers)
        assert r.json()["folder"] == "SPAM"

    def test_report_ham(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post(
            "/mail",
            json={"to": "b@y.com", "subject": "Meeting", "body_text": "See you at 3"},
            headers=headers,
        )
        mid = r.json()["id"]

        r = client.post(f"/mail/{mid}/report-spam", headers=headers)
        assert r.status_code == 200

        r = client.post(f"/mail/{mid}/report-ham", headers=headers)
        assert r.status_code == 200
        assert r.json()["message"] == "Message marked as not spam"

    def test_report_spam_not_found(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post("/mail/99999/report-spam", headers=headers)
        assert r.status_code == 404

    def test_report_ham_not_found(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post("/mail/99999/report-ham", headers=headers)
        assert r.status_code == 404

    def test_report_spam_unauthorized(self, client):
        r = client.post("/mail/1/report-spam")
        assert r.status_code == 401

    def test_report_ham_unauthorized(self, client):
        r = client.post("/mail/1/report-ham")
        assert r.status_code == 401

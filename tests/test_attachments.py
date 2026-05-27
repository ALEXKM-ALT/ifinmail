import pytest


@pytest.fixture
def token(client):
    client.post("/auth/register", json={"email": "user@mail.com", "password": "pass123"})
    r = client.post("/auth/login", json={"email": "user@mail.com", "password": "pass123"})
    return r.json()["access_token"]


@pytest.fixture(autouse=True)
def _attachment_storage(tmp_path):
    import os

    os.environ["IFINMAIL_ATTACHMENT_STORAGE"] = str(tmp_path / "attachments")
    yield


class TestUpload:
    def test_upload_attachment(self, client, token):
        r = client.post(
            "/mail/attachments",
            files={"file": ("test.txt", b"hello world", "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["filename"] == "test.txt"
        assert data["content_type"] == "text/plain"
        assert data["size"] == 11
        assert data["message_id"] is None

    def test_upload_unauthorized(self, client):
        r = client.post(
            "/mail/attachments",
            files={"file": ("x.txt", b"data", "text/plain")},
        )
        assert r.status_code == 401


class TestSendWithAttachments:
    def test_send_with_uploaded_attachments(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        upload = client.post(
            "/mail/attachments",
            files={"file": ("report.pdf", b"%PDF-1.4...", "application/pdf")},
            headers=headers,
        )
        assert upload.status_code == 201
        att_id = upload.json()["id"]

        r = client.post(
            "/mail",
            json={
                "to": "recipient@example.com",
                "subject": "With attachment",
                "body_text": "See attached",
                "attachment_ids": [att_id],
            },
            headers=headers,
        )
        assert r.status_code == 201
        msg_id = r.json()["id"]

        list_r = client.get(f"/mail/{msg_id}/attachments", headers=headers)
        assert list_r.status_code == 200
        atts = list_r.json()
        assert len(atts) == 1
        assert atts[0]["filename"] == "report.pdf"
        assert atts[0]["message_id"] == msg_id

    def test_send_with_attachment_marks_has_attachments(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        upload = client.post(
            "/mail/attachments",
            files={"file": ("f.dat", b"data", "application/octet-stream")},
            headers=headers,
        )
        att_id = upload.json()["id"]

        r = client.post(
            "/mail",
            json={"to": "x@y.com", "subject": "test", "body_text": "body", "attachment_ids": [att_id]},
            headers=headers,
        )
        msg_id = r.json()["id"]

        get_r = client.get(f"/mail/{msg_id}", headers=headers)
        assert get_r.json()["has_attachments"] == 1

    def test_send_without_attachments_has_none(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post(
            "/mail",
            json={"to": "x@y.com", "subject": "no attach", "body_text": "body"},
            headers=headers,
        )
        msg_id = r.json()["id"]

        get_r = client.get(f"/mail/{msg_id}", headers=headers)
        assert get_r.json()["has_attachments"] == 0


class TestDownload:
    def test_download_attachment(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        upload = client.post(
            "/mail/attachments",
            files={"file": ("hello.txt", b"hello world content", "text/plain")},
            headers=headers,
        )
        att_id = upload.json()["id"]

        send = client.post(
            "/mail",
            json={
                "to": "r@t.com",
                "subject": "s",
                "body_text": "b",
                "attachment_ids": [att_id],
            },
            headers=headers,
        )
        msg_id = send.json()["id"]

        dl = client.get(f"/mail/{msg_id}/attachments/{att_id}/download", headers=headers)
        assert dl.status_code == 200
        assert dl.content == b"hello world content"

    def test_download_not_found(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        r = client.get("/mail/99999/attachments/99999/download", headers=headers)
        assert r.status_code == 404

    def test_list_attachments(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        upload = client.post(
            "/mail/attachments",
            files={"file": ("a.txt", b"aaa", "text/plain")},
            headers=headers,
        )
        att_id = upload.json()["id"]

        client.post(
            "/mail",
            json={"to": "r@t.com", "subject": "s", "body_text": "b", "attachment_ids": [att_id]},
            headers=headers,
        )
        msg_id = client.post(
            "/mail",
            json={"to": "r2@t.com", "subject": "s2", "body_text": "b2"},
            headers=headers,
        ).json()["id"]

        r = client.get(f"/mail/{msg_id}/attachments", headers=headers)
        assert r.status_code == 200
        assert r.json() == []

    def test_get_attachment_meta(self, client, token):
        headers = {"Authorization": f"Bearer {token}"}
        upload = client.post(
            "/mail/attachments",
            files={"file": ("meta.txt", b"meta", "text/plain")},
            headers=headers,
        )
        att_id = upload.json()["id"]

        send = client.post(
            "/mail",
            json={"to": "r@t.com", "subject": "s", "body_text": "b", "attachment_ids": [att_id]},
            headers=headers,
        )
        msg_id = send.json()["id"]

        r = client.get(f"/mail/{msg_id}/attachments/{att_id}", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["filename"] == "meta.txt"
        assert data["content_type"] == "text/plain"
        assert data["size"] == 4

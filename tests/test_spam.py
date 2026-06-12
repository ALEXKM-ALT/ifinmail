import pytest


@pytest.fixture
def token(client):
    r = client.post("/auth/register", json={"email": "spam@test.com", "password": "pass123"})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": "spam@test.com", "password": "pass123"})
    assert r.status_code in (201, 200)
    if r.status_code == 201:
        r = client.post("/auth/login", json={"email": "spam@test.com", "password": "pass123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


class TestSpamCheck:
    def test_clean_email(self, client, token):
        r = client.post("/spam-check", json={"subject": "Meeting tomorrow", "body_text": "Hi, let's meet at 3pm."}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["risk"] == "low"

    def test_spammy_email(self, client, token):
        r = client.post("/spam-check", json={"subject": "WIN BIG MONEY NOW!!!", "body_text": "Click here to claim your FREE prize!"}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["risk"] == "high"
        assert len(r.json()["flags"]) > 0

    def test_unauthorized(self, client):
        r = client.post("/spam-check", json={"subject": "test"})
        assert r.status_code in (401, 403)

import pytest


@pytest.fixture
def token(client):
    r = client.post("/auth/register", json={"email": "intel@test.com", "password": "pass123"})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": "intel@test.com", "password": "pass123"})
    assert r.status_code in (200, 201)
    if r.status_code == 201:
        r = client.post("/auth/login", json={"email": "intel@test.com", "password": "pass123"})
    assert r.status_code == 200
    return r.json()["access_token"]


class TestIntelligence:
    def test_analyze_basic(self, client, token):
        r = client.post(
            "/intelligence/analyze",
            json={"subject": "Meeting tomorrow", "body_text": "Let's discuss the project proposal at 3pm"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "spam_probability" in data
        assert "sentiment" in data
        assert "language" in data
        assert "business_score" in data
        assert data["word_count"] == 9

    def test_analyze_positive_sentiment(self, client, token):
        r = client.post(
            "/intelligence/analyze",
            json={"subject": "Great news", "body_text": "This is amazing and wonderful! Thank you so much!"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["sentiment"] == "positive"

    def test_analyze_negative_sentiment(self, client, token):
        r = client.post(
            "/intelligence/analyze",
            json={"subject": "Problem", "body_text": "I am very disappointed and angry about this terrible issue"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["sentiment"] == "negative"

    def test_analyze_spam_detection(self, client, token):
        r = client.post(
            "/intelligence/analyze",
            json={"subject": "WIN BIG!", "body_text": "FREE MONEY!!! CONGRATULATIONS YOU ARE A WINNER!!! CLICK HERE NOW!!! BUY NOW!!! LIMITED TIME OFFER!!!"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["spam_probability"] != "0%"

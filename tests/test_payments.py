import pytest


@pytest.fixture
def token(client):
    r = client.post("/auth/register", json={"email": "pay@test.com", "password": "pass123"})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": "pay@test.com", "password": "pass123"})
    assert r.status_code in (200, 201)
    if r.status_code == 201:
        r = client.post("/auth/login", json={"email": "pay@test.com", "password": "pass123"})
    assert r.status_code == 200
    return r.json()["access_token"]


class TestPayments:
    def test_get_plans(self, client, token):
        r = client.get("/payments/plans", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 3
        assert data[0]["name"] == "starter"

    def test_mpesa_stkpush_sandbox(self, client, token):
        r = client.post(
            "/payments/mpesa/stkpush",
            json={"phone": "254712345678", "amount": 50000},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["checkout_request_id"]

    def test_mpesa_status(self, client, token):
        r = client.post(
            "/payments/mpesa/stkpush",
            json={"phone": "254712345678", "amount": 200000},
            headers={"Authorization": f"Bearer {token}"},
        )
        cid = r.json()["checkout_request_id"]
        r2 = client.get(f"/payments/mpesa/status/{cid}", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200
        assert r2.json()["status"] == "pending"

    def test_mpesa_callback(self, client, token):
        r = client.post(
            "/payments/mpesa/stkpush",
            json={"phone": "254712345678", "amount": 50000},
            headers={"Authorization": f"Bearer {token}"},
        )
        cid = r.json()["checkout_request_id"]
        cb = client.post(
            "/payments/mpesa/callback",
            json={"Body": {"stkCallback": {"CheckoutRequestID": cid, "ResultCode": 0, "ResultDesc": "Success", "CallbackMetadata": {"Item": [{"Name": "MpesaReceiptNumber", "Value": "ABC123"}]}}}},
        )
        assert cb.status_code == 200
        r2 = client.get(f"/payments/mpesa/status/{cid}", headers={"Authorization": f"Bearer {token}"})
        assert r2.json()["status"] == "completed"

    def test_unauthorized(self, client):
        r = client.get("/payments/plans")
        assert r.status_code == 200
        r2 = client.get("/payments/mpesa/status/fake")
        assert r2.status_code in (401, 403)

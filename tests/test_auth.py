def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["database"] == "up"
    assert data["status"] in ("ok", "degraded")


def test_register(client):
    r = client.post("/auth/register", json={"email": "a@b.com", "password": "secret123"})
    assert r.status_code == 201
    assert r.json()["email"] == "a@b.com"


def test_register_duplicate(client):
    client.post("/auth/register", json={"email": "dup@b.com", "password": "secret123"})
    r = client.post("/auth/register", json={"email": "dup@b.com", "password": "secret123"})
    assert r.status_code == 409


def test_register_bad_email(client):
    r = client.post("/auth/register", json={"email": "bad", "password": "secret123"})
    assert r.status_code == 400


def test_register_short_password(client):
    r = client.post("/auth/register", json={"email": "x@b.com", "password": "ab"})
    assert r.status_code == 400


def test_login(client):
    client.post("/auth/register", json={"email": "login@b.com", "password": "secret123"})
    r = client.post("/auth/login", json={"email": "login@b.com", "password": "secret123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_wrong_password(client):
    client.post("/auth/register", json={"email": "wrong@b.com", "password": "secret123"})
    r = client.post("/auth/login", json={"email": "wrong@b.com", "password": "wrongpass"})
    assert r.status_code == 401


def test_login_not_found(client):
    r = client.post("/auth/login", json={"email": "noone@b.com", "password": "x"})
    assert r.status_code == 401


def test_me(client):
    client.post("/auth/register", json={"email": "me@b.com", "password": "secret123"})
    r = client.post("/auth/login", json={"email": "me@b.com", "password": "secret123"})
    token = r.json()["access_token"]

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "me@b.com"
    assert r.json()["is_admin"] is True


def test_me_unauthorized(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_bad_token(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer invalidtoken"})
    assert r.status_code == 401


def test_refresh(client):
    client.post("/auth/register", json={"email": "refresh@b.com", "password": "secret123"})
    r = client.post("/auth/login", json={"email": "refresh@b.com", "password": "secret123"})
    refresh_token = r.json()["refresh_token"]

    r = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_logout(client):
    client.post("/auth/register", json={"email": "logout@b.com", "password": "secret123"})
    r = client.post("/auth/login", json={"email": "logout@b.com", "password": "secret123"})
    refresh_token = r.json()["refresh_token"]

    r = client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert r.status_code == 200

    r = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 401

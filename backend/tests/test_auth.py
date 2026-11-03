"""Auth flow against the real Postgres. Each test uses its own email and deletes it afterwards."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.main import app
from app.models import RefreshToken, User

PASSWORD = "correct horse battery"


@pytest.fixture
def email() -> Iterator[str]:
    address = f"test-{uuid.uuid4().hex[:12]}@example.com"
    yield address
    with SessionLocal() as db:
        db.execute(delete(User).where(User.email == address))
        db.commit()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def signup(client: TestClient, email: str, **extra):
    return client.post("/api/auth/signup", json={"email": email, "password": PASSWORD, **extra})


def test_signup_stores_user_with_hashed_password_and_logs_in(client, email):
    res = signup(client, email.upper(), full_name="  Ada Lovelace ")
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == email  # stored lower-case
    assert body["full_name"] == "Ada Lovelace"
    assert "password" not in str(body)
    assert client.cookies.get("access_token") and client.cookies.get("refresh_token")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user.password_hash.startswith("$argon2") and PASSWORD not in user.password_hash
        assert db.scalar(select(RefreshToken).where(RefreshToken.user_id == user.id))

    assert client.get("/api/auth/me").json()["email"] == email


def test_duplicate_email_is_rejected(client, email):
    assert signup(client, email).status_code == 201
    assert signup(TestClient(app), email.upper()).status_code == 409


@pytest.mark.parametrize("payload", [{"email": "not-an-email", "password": PASSWORD}, {"password": "short"}])
def test_signup_validates_input(client, email, payload):
    assert client.post("/api/auth/signup", json={"email": email, **payload}).status_code == 422


def test_login_with_right_and_wrong_password(client, email):
    signup(client, email)
    fresh = TestClient(app)
    wrong = fresh.post("/api/auth/login", json={"email": email, "password": "wrong password"})
    unknown = fresh.post("/api/auth/login", json={"email": "nobody-" + email, "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()  # no hint about which part was wrong

    ok = fresh.post("/api/auth/login", json={"email": email.upper(), "password": PASSWORD})
    assert ok.status_code == 200
    assert fresh.get("/api/auth/me").status_code == 200


def test_me_requires_login(client):
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set("access_token", "garbage", path="/api")
    assert client.get("/api/auth/me").status_code == 401


def test_refresh_rotates_and_old_token_stops_working(client, email):
    signup(client, email)
    old = client.cookies.get("refresh_token")
    res = client.post("/api/auth/refresh")
    assert res.status_code == 200 and res.json()["email"] == email
    assert client.cookies.get("refresh_token") != old

    replay = TestClient(app)
    replay.cookies.set("refresh_token", old, path="/api/auth")
    assert replay.post("/api/auth/refresh").status_code == 401


def test_logout_revokes_refresh_and_clears_cookies(client, email):
    signup(client, email)
    token = client.cookies.get("refresh_token")
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401

    replay = TestClient(app)
    replay.cookies.set("refresh_token", token, path="/api/auth")
    assert replay.post("/api/auth/refresh").status_code == 401

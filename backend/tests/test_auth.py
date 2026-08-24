from pathlib import Path

from app.auth_models import Customer
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import select


def make_app(tmp_path: Path):
    return create_app(f"sqlite:///{tmp_path / 'auth.db'}")


def test_signup_session_logout_and_login(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    with TestClient(app) as client:
        signup = client.post(
            "/api/auth/signup",
            json={
                "name": "Demo Shopper",
                "email": "shopper@example.com",
                "password": "SafePass123",
            },
        )
        current = client.get("/api/auth/me")
        with app.state.db.session_factory() as session:
            stored = session.scalar(select(Customer).where(Customer.email == "shopper@example.com"))

        logout = client.post("/api/auth/logout")
        signed_out = client.get("/api/auth/me")
        login = client.post(
            "/api/auth/login",
            json={"email": "SHOPPER@example.com", "password": "SafePass123"},
        )

    assert signup.status_code == 201
    assert signup.json()["user"]["email"] == "shopper@example.com"
    cookie = signup.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert current.status_code == 200
    assert stored is not None
    assert stored.password_hash.startswith("scrypt$")
    assert "SafePass123" not in stored.password_hash
    assert logout.status_code == 200
    assert signed_out.status_code == 401
    assert login.status_code == 200


def test_duplicate_invalid_and_weak_credentials_are_rejected(tmp_path: Path) -> None:
    with TestClient(make_app(tmp_path)) as client:
        weak = client.post(
            "/api/auth/signup",
            json={"name": "Demo Shopper", "email": "shopper@example.com", "password": "password"},
        )
        first = client.post(
            "/api/auth/signup",
            json={
                "name": "Demo Shopper",
                "email": "shopper@example.com",
                "password": "SafePass123",
            },
        )
        duplicate = client.post(
            "/api/auth/signup",
            json={
                "name": "Another Shopper",
                "email": "shopper@example.com",
                "password": "OtherPass123",
            },
        )
        invalid = client.post(
            "/api/auth/login",
            json={"email": "shopper@example.com", "password": "WrongPass123"},
        )

    assert weak.status_code == 422
    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["error"] == "EMAIL_ALREADY_REGISTERED"
    assert invalid.status_code == 401
    assert invalid.json()["error"] == "INVALID_CREDENTIALS"

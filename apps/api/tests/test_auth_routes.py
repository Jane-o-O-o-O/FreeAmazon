from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes


class Settings:
    access_username = "demo"
    access_password = "secret"
    access_token_secret = "route-test-secret"
    access_token_ttl_seconds = 3600


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def test_login_route_returns_token(monkeypatch) -> None:
    monkeypatch.setattr("app.services.auth_service.get_settings", lambda: Settings())

    response = make_client().post(
        "/api/auth/login",
        json={"username": "demo", "password": "secret"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["username"] == "demo"


def test_session_route_requires_token(monkeypatch) -> None:
    monkeypatch.setattr("app.services.auth_service.get_settings", lambda: Settings())

    response = make_client().get("/api/auth/session")

    assert response.status_code == 401


def test_session_route_accepts_login_token(monkeypatch) -> None:
    monkeypatch.setattr("app.services.auth_service.get_settings", lambda: Settings())
    client = make_client()

    login_response = client.post(
        "/api/auth/login",
        json={"username": "demo", "password": "secret"},
    )
    token = login_response.json()["access_token"]
    session_response = client.get(
        "/api/auth/session",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert session_response.status_code == 200
    assert session_response.json() == {"authenticated": True, "username": "demo"}

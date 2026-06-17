import pytest

from app.services.auth_service import AuthService, AuthenticationError


class Settings:
    access_username = "demo"
    access_password = "secret"
    access_token_secret = "unit-test-secret"
    access_token_ttl_seconds = 3600


def test_auth_service_login_and_verify_token(monkeypatch) -> None:
    monkeypatch.setattr("app.services.auth_service.get_settings", lambda: Settings())

    token, expires_in = AuthService().login("demo", "secret")

    assert expires_in == 3600
    assert AuthService().verify_token(token) == "demo"


def test_auth_service_rejects_wrong_password(monkeypatch) -> None:
    monkeypatch.setattr("app.services.auth_service.get_settings", lambda: Settings())

    with pytest.raises(AuthenticationError):
        AuthService().login("demo", "wrong")


def test_auth_service_rejects_tampered_token(monkeypatch) -> None:
    monkeypatch.setattr("app.services.auth_service.get_settings", lambda: Settings())

    token, _ = AuthService().login("demo", "secret")

    with pytest.raises(AuthenticationError):
        AuthService().verify_token(f"{token}x")

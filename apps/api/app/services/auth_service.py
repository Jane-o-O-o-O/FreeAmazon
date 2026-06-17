import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.core.config import get_settings


class AuthenticationError(RuntimeError):
    """Raised when access credentials or tokens are invalid."""


class AuthService:
    def login(self, username: str, password: str) -> tuple[str, int]:
        settings = get_settings()
        if not self._matches(username, settings.access_username) or not self._matches(
            password,
            settings.access_password,
        ):
            raise AuthenticationError("Invalid username or password")

        expires_at = int(time.time()) + int(settings.access_token_ttl_seconds)
        payload = {"sub": settings.access_username, "exp": expires_at}
        return self._encode_token(payload, settings.access_token_secret), settings.access_token_ttl_seconds

    def verify_token(self, token: str) -> str:
        settings = get_settings()
        try:
            payload_b64, signature = token.split(".", 1)
            expected_signature = self._signature(payload_b64, settings.access_token_secret)
            if not hmac.compare_digest(signature, expected_signature):
                raise AuthenticationError("Invalid token signature")
            payload = json.loads(self._b64decode(payload_b64).decode("utf-8"))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AuthenticationError("Invalid access token") from exc

        username = payload.get("sub")
        expires_at = payload.get("exp")
        if not isinstance(username, str) or username != settings.access_username:
            raise AuthenticationError("Invalid token subject")
        if not isinstance(expires_at, int) or expires_at < int(time.time()):
            raise AuthenticationError("Access token expired")
        return username

    def _encode_token(self, payload: dict[str, Any], secret: str) -> str:
        payload_b64 = self._b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        return f"{payload_b64}.{self._signature(payload_b64, secret)}"

    def _signature(self, payload_b64: str, secret: str) -> str:
        digest = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
        return self._b64encode(digest)

    def _b64encode(self, value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    def _b64decode(self, value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding)

    def _matches(self, received: str, expected: str) -> bool:
        return hmac.compare_digest(received.encode("utf-8"), expected.encode("utf-8"))


auth_service = AuthService()

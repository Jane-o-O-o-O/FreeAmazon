import httpx
import pytest

from app.services.canopy_client import CanopyApiError, CanopyClient, CanopyConfigurationError


def test_canopy_client_requires_api_key() -> None:
    with pytest.raises(CanopyConfigurationError, match="CANOPY_API_KEY"):
        CanopyClient(api_key=None)


def test_get_product_uses_official_rest_path_and_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["api_key"] = request.headers.get("API-KEY")
        return httpx.Response(200, json={"data": {"amazonProduct": {"asin": "B0C1234567"}}})

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    def client_factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client_factory)

    payload = CanopyClient(
        api_key="test-key",
        base_url="https://rest.canopyapi.co/",
    ).get_product(asin="B0C1234567", domain="us")

    assert payload["data"]["amazonProduct"]["asin"] == "B0C1234567"
    assert captured["api_key"] == "test-key"
    assert captured["url"] == (
        "https://rest.canopyapi.co/api/amazon/product?asin=B0C1234567&domain=US"
    )


def test_canopy_client_formats_api_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"success": False, "errors": [{"code": 7003, "message": "Unauthorized"}]},
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    def client_factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client_factory)

    with pytest.raises(CanopyApiError, match="HTTP 401: Unauthorized"):
        CanopyClient(api_key="bad-key").get_product(asin="B0C1234567", domain="US")


def test_canopy_client_handles_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>not json</html>")

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    def client_factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client_factory)

    with pytest.raises(CanopyApiError, match="无法解析的 JSON"):
        CanopyClient(api_key="test-key").get_product(asin="B0C1234567", domain="US")

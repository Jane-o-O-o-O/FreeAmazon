import httpx
import pytest

from app.services.apify_client import ApifyActors, ApifyApiError, ApifyClient, ApifyConfigurationError


def actors() -> ApifyActors:
    return ApifyActors(
        reverse_image="dev00/alibaba-1688-aliexpress-reverse-image-search-api",
        keyword_search="ecomscrape/1688-product-search-scraper",
    )


def test_apify_client_requires_api_token() -> None:
    with pytest.raises(ApifyConfigurationError, match="APIFY_API_TOKEN"):
        ApifyClient(
            api_token=None,
            base_url="https://api.apify.com/v2",
            timeout_seconds=30,
            actors=actors(),
        )


def test_apify_client_runs_actor_with_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["json"] = request.read().decode("utf-8")
        return httpx.Response(200, json=[{"offerId": "123"}])

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    def client_factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client_factory)

    items = ApifyClient(
        api_token="test-token",
        base_url="https://api.apify.com/v2/",
        timeout_seconds=30,
        actors=actors(),
    ).search_by_image(image_url="https://example.com/main.jpg", destination="1688", limit=10)

    assert items == [{"offerId": "123"}]
    assert captured["auth"] == "Bearer test-token"
    assert captured["url"] == (
        "https://api.apify.com/v2/acts/"
        "dev00~alibaba-1688-aliexpress-reverse-image-search-api/run-sync-get-dataset-items"
    )
    assert '"imageUrl":"https://example.com/main.jpg"' in str(captured["json"])
    assert '"destination":"1688"' in str(captured["json"])


def test_apify_client_formats_api_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "token is invalid"}})

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    def client_factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client_factory)

    client = ApifyClient(
        api_token="bad-token",
        base_url="https://api.apify.com/v2",
        timeout_seconds=30,
        actors=actors(),
    )
    with pytest.raises(ApifyApiError, match="HTTP 401: token is invalid"):
        client.search_by_keyword(keyword="便携榨汁杯", limit=10, filters={})

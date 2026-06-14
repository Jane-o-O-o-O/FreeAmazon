import pytest

from app.services.amazon_service import AmazonService
from app.services.canopy_client import CanopyConfigurationError


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("B0C1234567", "B0C1234567"),
        ("https://www.amazon.com/dp/B0C1234567", "B0C1234567"),
        ("https://www.amazon.com/gp/product/B0C1234567?th=1", "B0C1234567"),
        ("https://www.amazon.com/some-product/dp/B0C1234567/ref=abc", "B0C1234567"),
    ],
)
def test_parse_asin(value: str, expected: str) -> None:
    assert AmazonService().parse_asin_from_url(value) == expected


def test_parse_asin_rejects_invalid_url() -> None:
    with pytest.raises(ValueError):
        AmazonService().parse_asin_from_url("https://example.com/no-asin")


def test_canopy_payload_is_normalized_to_amazon_product() -> None:
    payload = {
        "data": {
            "amazonProduct": {
                "title": "Portable Blender with USB-C Charging",
                "brand": "DemoBrand",
                "url": "https://www.amazon.com/dp/B0C1234567",
                "asin": "b0c1234567",
                "price": {
                    "symbol": "$",
                    "value": 29.99,
                    "currency": "USD",
                    "display": "$29.99",
                },
                "mainImageUrl": "https://example.com/main.jpg",
                "imageUrls": [
                    "https://example.com/main.jpg",
                    "https://example.com/side.jpg",
                ],
                "rating": 4.4,
                "ratingsTotal": 2381,
                "categories": [
                    {"name": "Home & Kitchen"},
                    {"name": "Kitchen & Dining", "breadcrumbPath": "Home & Kitchen > Kitchen"},
                ],
            }
        }
    }

    product = AmazonService()._product_from_canopy_payload(
        payload=payload,
        fallback_asin="B0C1234567",
        fallback_url="https://fallback.example/item",
        marketplace="us",
    )

    assert product.asin == "B0C1234567"
    assert product.marketplace == "US"
    assert product.title == "Portable Blender with USB-C Charging"
    assert product.brand == "DemoBrand"
    assert product.price == 29.99
    assert product.currency == "USD"
    assert product.rating == 4.4
    assert product.review_count == 2381
    assert product.main_image_url == "https://example.com/main.jpg"
    assert product.image_urls == [
        "https://example.com/main.jpg",
        "https://example.com/side.jpg",
    ]
    assert product.category == "Home & Kitchen > Kitchen"
    assert product.raw_data["provider"] == "canopy"


def test_canopy_payload_requires_amazon_product_root() -> None:
    with pytest.raises(ValueError, match="data.amazonProduct"):
        AmazonService()._product_from_canopy_payload(
            payload={"data": {}},
            fallback_asin="B0C1234567",
            fallback_url="https://fallback.example/item",
            marketplace="US",
        )


def test_real_canopy_mode_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    class Settings:
        canopy_use_mock = False
        canopy_api_key = None
        canopy_api_base_url = "https://rest.canopyapi.co"
        canopy_timeout_seconds = 30

    monkeypatch.setattr("app.services.amazon_service.get_settings", lambda: Settings())

    with pytest.raises(CanopyConfigurationError, match="CANOPY_API_KEY"):
        AmazonService().fetch_product("https://www.amazon.com/dp/B0C1234567", "US")


def test_fetch_product_uses_canopy_client_when_mock_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, str] = {}

    class Settings:
        canopy_use_mock = False
        canopy_api_key = "test-key"
        canopy_api_base_url = "https://rest.canopyapi.co"
        canopy_timeout_seconds = 30

    class FakeCanopyClient:
        def __init__(self, api_key: str, base_url: str, timeout_seconds: float) -> None:
            calls["api_key"] = api_key
            calls["base_url"] = base_url
            calls["timeout_seconds"] = str(timeout_seconds)

        def get_product(self, asin: str, domain: str) -> dict:
            calls["asin"] = asin
            calls["domain"] = domain
            return {
                "data": {
                    "amazonProduct": {
                        "asin": asin,
                        "title": "Real Canopy Product",
                        "url": f"https://www.amazon.com/dp/{asin}",
                        "mainImageUrl": "https://example.com/main.jpg",
                        "imageUrls": [],
                    }
                }
            }

    monkeypatch.setattr("app.services.amazon_service.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.amazon_service.CanopyClient", FakeCanopyClient)

    product = AmazonService().fetch_product("https://www.amazon.com/dp/B0C1234567", "us")

    assert calls == {
        "api_key": "test-key",
        "base_url": "https://rest.canopyapi.co",
        "timeout_seconds": "30",
        "asin": "B0C1234567",
        "domain": "us",
    }
    assert product.title == "Real Canopy Product"

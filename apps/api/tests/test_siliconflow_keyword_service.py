import httpx

from app.models.source_search import AmazonProduct
from app.services.siliconflow_keyword_service import SiliconFlowKeywordService


def product() -> AmazonProduct:
    return AmazonProduct(
        asin="B0C1234567",
        marketplace="US",
        url="https://www.amazon.com/dp/B0C1234567",
        title="Portable USB-C Blender Bottle for Smoothies",
        brand="DemoBrand",
        category="Home & Kitchen > Kitchen & Dining",
        price=29.99,
        currency="USD",
        rating=4.4,
        review_count=100,
        main_image_url="https://example.com/main.jpg",
        image_urls=["https://example.com/main.jpg"],
    )


def test_fallback_keywords_use_amazon_fields() -> None:
    keywords = SiliconFlowKeywordService().fallback_keywords(product())

    assert "便携榨汁杯" in keywords
    assert "USB充电" in keywords
    assert "厨房用品" in keywords


def test_llm_keywords_parse_json_array(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "[\"便携榨汁杯\", \"随行杯\"]"}}]},
        )

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    def client_factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client_factory)

    keywords = SiliconFlowKeywordService()._generate_with_llm(
        api_key="test-key",
        base_url="https://api.siliconflow.cn/v1",
        model="inclusionAI/Ling-flash-2.0",
        timeout_seconds=30,
        amazon_product=product(),
    )

    assert keywords == ["便携榨汁杯", "随行杯"]

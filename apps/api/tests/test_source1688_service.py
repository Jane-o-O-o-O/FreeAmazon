from app.models.source_search import AmazonProduct
from app.services.source1688_service import Source1688Service


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


def test_source1688_service_runs_complete_apify_chain(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    class Settings:
        apify_use_mock = False
        apify_api_token = "test-token"
        apify_api_base_url = "https://api.apify.com/v2"
        apify_timeout_seconds = 30
        apify_reverse_image_actor = "dev00/reverse-image"
        apify_keyword_search_actor = "ecomscrape/search"
        apify_reverse_image_destination = "1688"
        apify_search_limit = 12
        apify_keyword_limit = 2
        apify_detail_limit = 5

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            calls.append(("init", kwargs["base_url"]))
            self.actors = kwargs["actors"]

        def search_by_image(self, image_url: str, destination: str, limit: int) -> list[dict]:
            calls.append(("image", image_url))
            return [
                {
                    "offerId": "123",
                    "title": "便携榨汁杯 工厂批发",
                    "imageUrl": "https://img.alicdn.com/123.jpg",
                    "price": "18.8",
                    "minOrderQuantity": "2",
                    "monthlySales": "300",
                    "supplier": {
                        "name": "深圳测试工厂",
                        "location": "广东 深圳",
                        "years": "6年",
                        "isFactory": True,
                    },
                    "supportsDropshipping": True,
                }
            ]

        def search_by_keyword(self, keyword: str, limit: int, filters: dict) -> list[dict]:
            calls.append(("keyword", keyword))
            return [
                {
                    "offerId": "123",
                    "title": "便携榨汁杯 重复结果",
                    "imageUrl": "https://img.alicdn.com/123.jpg",
                    "price": "19.8",
                },
                {
                    "url": "https://detail.1688.com/offer/456789.html",
                    "title": "随行杯 一件代发",
                    "image": "https://img.alicdn.com/456.jpg",
                    "priceRange": "12.0-16.0",
                    "minOrder": "10件",
                    "sales": "421",
                    "companyName": "义乌测试贸易商行",
                    "location": "浙江 义乌",
                    "shopYears": "3年",
                },
            ]

    monkeypatch.setattr("app.services.source1688_service.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.source1688_service.ApifyClient", FakeClient)
    monkeypatch.setattr(
        "app.services.source1688_service.siliconflow_keyword_service.generate_keywords",
        lambda amazon_product: ["便携榨汁杯", "随行杯"],
    )

    items = Source1688Service().search_candidates(product(), filters={"dropshipping": True})

    assert [item.item_id for item in items] == ["123", "456789"]
    assert items[0].title == "便携榨汁杯 工厂批发"
    assert items[0].supplier_name == "深圳测试工厂"
    assert items[0].supplier_location == "广东 深圳"
    assert items[0].supplier_years == 6
    assert items[0].is_factory is True
    assert items[0].supports_dropshipping is True
    assert items[0].raw_data["search_types"] == ["image", "keyword"]
    assert items[1].price_min == 12.0
    assert items[1].price_max == 16.0
    assert items[1].supports_dropshipping is True
    assert ("image", "https://example.com/main.jpg") in calls
    assert ("keyword", "便携榨汁杯") in calls


def test_source1688_service_normalizes_zen_studio_actor_output(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    class Settings:
        apify_use_mock = False
        apify_api_token = "test-token"
        apify_api_base_url = "https://api.apify.com/v2"
        apify_timeout_seconds = 30
        apify_reverse_image_actor = ""
        apify_keyword_search_actor = "ghXSMZcW3GxsCrkiR"
        apify_reverse_image_destination = "1688"
        apify_search_limit = 12
        apify_keyword_limit = 2
        apify_detail_limit = 5

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.actors = kwargs["actors"]

        def search_by_keywords(
            self,
            keywords: list[str],
            limit: int,
            filters: dict,
        ) -> list[dict]:
            calls.append(("keywords", keywords))
            calls.append(("limit", limit))
            calls.append(("filters", filters))
            return [
                {
                    "offerId": "669074500111",
                    "title": "跨境便携榨汁杯 USB 充电",
                    "detailUrl": "https://detail.1688.com/offer/669074500111.html",
                    "images": [
                        {
                            "fullPathImageURI": "//cbu01.alicdn.com/img/ibank/demo.jpg",
                        }
                    ],
                    "price": {"min": 7.3, "max": 9.8, "currency": "CNY"},
                    "quantityPrices": [{"minQuantity": 2, "price": 7.3}],
                    "orderCount": 188,
                    "sourceKeyword": "便携榨汁杯",
                    "supplier": {
                        "memberId": "b2b-001",
                        "companyName": "深圳测试小家电工厂",
                        "province": "广东",
                        "city": "深圳市",
                        "tpYear": "5年",
                        "supportsDistribution": True,
                        "flags": {"isFactory": True},
                    },
                    "dropship": {"supportsDropship": True},
                }
            ]

    monkeypatch.setattr("app.services.source1688_service.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.source1688_service.ApifyClient", FakeClient)
    monkeypatch.setattr(
        "app.services.source1688_service.siliconflow_keyword_service.generate_keywords",
        lambda amazon_product: ["便携榨汁杯", "随行杯"],
    )

    items = Source1688Service().search_candidates(product(), filters={"max_price_cny": 30})

    assert [item.item_id for item in items] == ["669074500111"]
    assert items[0].url == "https://detail.1688.com/offer/669074500111.html"
    assert items[0].image_url == "https://cbu01.alicdn.com/img/ibank/demo.jpg"
    assert items[0].price_min == 7.3
    assert items[0].price_max == 9.8
    assert items[0].moq == 2
    assert items[0].monthly_sales == 188
    assert items[0].supplier_id == "b2b-001"
    assert items[0].supplier_name == "深圳测试小家电工厂"
    assert items[0].supplier_location == "广东 深圳市"
    assert items[0].supplier_years == 5
    assert items[0].is_factory is True
    assert items[0].supports_dropshipping is True
    assert items[0].raw_data["search_queries"] == ["便携榨汁杯"]
    assert ("keywords", ["便携榨汁杯", "随行杯"]) in calls

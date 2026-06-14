from app.core.config import get_settings
from app.models.source_search import AmazonProduct, SourceItem


class Source1688Service:
    def search_candidates(
        self,
        amazon_product: AmazonProduct,
        filters: dict,
    ) -> list[SourceItem]:
        settings = get_settings()
        if settings.tmapi_use_mock:
            return self._mock_candidates(amazon_product, filters)

        raise NotImplementedError(
            "TMAPI 客户端尚未配置。本地 MVP 请设置 TMAPI_USE_MOCK=true。"
        )

    def _mock_candidates(self, amazon_product: AmazonProduct, filters: dict) -> list[SourceItem]:
        base_items = [
            SourceItem(
                platform="1688",
                item_id="mock-1688-001",
                url="https://detail.1688.com/offer/mock-1688-001.html",
                title="便携式榨汁杯 USB 充电迷你果汁机 工厂现货批发",
                image_url=f"https://picsum.photos/seed/{amazon_product.asin.lower()}-main/640/640",
                price_min=22.8,
                price_max=29.6,
                moq=2,
                monthly_sales=864,
                supplier_id="supplier-001",
                supplier_name="深圳市示例小家电工厂",
                supplier_location="广东 深圳",
                supplier_years=6,
                is_factory=True,
                supports_dropshipping=True,
                raw_data={"mock": True, "search_type": "image"},
            ),
            SourceItem(
                platform="1688",
                item_id="mock-1688-002",
                url="https://detail.1688.com/offer/mock-1688-002.html",
                title="迷你便携料理杯 家用果汁杯 跨境电商现货一件代发",
                image_url=f"https://picsum.photos/seed/{amazon_product.asin.lower()}-side/640/640",
                price_min=18.5,
                price_max=25.0,
                moq=10,
                monthly_sales=421,
                supplier_id="supplier-002",
                supplier_name="义乌市示例贸易商行",
                supplier_location="浙江 义乌",
                supplier_years=3,
                is_factory=False,
                supports_dropshipping=True,
                raw_data={"mock": True, "search_type": "keyword"},
            ),
            SourceItem(
                platform="1688",
                item_id="mock-1688-003",
                url="https://detail.1688.com/offer/mock-1688-003.html",
                title="电动蛋白粉摇摇杯 运动水杯 小批量批发",
                image_url=f"https://picsum.photos/seed/{amazon_product.asin.lower()}-other/640/640",
                price_min=16.9,
                price_max=21.2,
                moq=20,
                monthly_sales=139,
                supplier_id="supplier-003",
                supplier_name="宁波示例塑料制品厂",
                supplier_location="浙江 宁波",
                supplier_years=2,
                is_factory=True,
                supports_dropshipping=False,
                raw_data={"mock": True, "search_type": "keyword"},
            ),
        ]

        max_price = filters.get("max_price_cny")
        factory_only = filters.get("factory_only", False)
        dropshipping = filters.get("dropshipping", False)
        min_supplier_years = filters.get("min_supplier_years")

        results = []
        for item in base_items:
            if max_price is not None and item.price_min is not None and item.price_min > max_price:
                continue
            if factory_only and not item.is_factory:
                continue
            if dropshipping and not item.supports_dropshipping:
                continue
            if (
                min_supplier_years is not None
                and item.supplier_years is not None
                and item.supplier_years < min_supplier_years
            ):
                continue
            results.append(item)
        return results


source1688_service = Source1688Service()

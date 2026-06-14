import re
from typing import Any

from app.core.config import get_settings
from app.models.source_search import AmazonProduct, SourceItem
from app.services.apify_client import ApifyActors, ApifyApiError, ApifyClient
from app.services.siliconflow_keyword_service import siliconflow_keyword_service


class Source1688Service:
    def search_candidates(
        self,
        amazon_product: AmazonProduct,
        filters: dict,
    ) -> list[SourceItem]:
        settings = get_settings()
        if settings.apify_use_mock:
            return self._mock_candidates(amazon_product, filters)

        client = ApifyClient(
            api_token=settings.apify_api_token,
            base_url=settings.apify_api_base_url,
            timeout_seconds=settings.apify_timeout_seconds,
            actors=ApifyActors(
                reverse_image=settings.apify_reverse_image_actor,
                keyword_search=settings.apify_keyword_search_actor,
            ),
        )

        raw_candidates = self._collect_raw_candidates(
            client=client,
            amazon_product=amazon_product,
            filters=filters,
            limit=settings.apify_search_limit,
            keyword_limit=settings.apify_keyword_limit,
            destination=settings.apify_reverse_image_destination,
        )
        merged = self._merge_candidates(raw_candidates)
        items = [self._to_source_item(candidate) for candidate in merged[: settings.apify_detail_limit]]
        return self._apply_filters(items, filters)

    def _collect_raw_candidates(
        self,
        *,
        client: ApifyClient,
        amazon_product: AmazonProduct,
        filters: dict,
        limit: int,
        keyword_limit: int,
        destination: str,
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        errors: list[str] = []

        if amazon_product.main_image_url:
            try:
                for item in client.search_by_image(
                    image_url=amazon_product.main_image_url,
                    destination=destination,
                    limit=limit,
                ):
                    item["_source_search_type"] = "image"
                    item["_source_query"] = amazon_product.main_image_url
                    item["_source_actor"] = client.actors.reverse_image
                    candidates.append(item)
            except ApifyApiError as exc:
                errors.append(f"图片搜索失败：{exc}")

        keywords = siliconflow_keyword_service.generate_keywords(amazon_product)
        for keyword in keywords[:keyword_limit]:
            try:
                for item in client.search_by_keyword(
                    keyword=keyword,
                    limit=max(3, min(limit, 20)),
                    filters=filters,
                ):
                    item["_source_search_type"] = "keyword"
                    item["_source_query"] = keyword
                    item["_source_actor"] = client.actors.keyword_search
                    candidates.append(item)
            except ApifyApiError as exc:
                errors.append(f"关键词 `{keyword}` 搜索失败：{exc}")

        usable = [candidate for candidate in candidates if self._extract_item_id(candidate)]
        if usable:
            return usable
        if errors:
            raise ApifyApiError(f"1688 Apify 搜索失败：{'；'.join(errors[:3])}")
        return []

    def _merge_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            item_id = self._extract_item_id(candidate)
            if not item_id:
                continue

            if item_id not in merged:
                candidate["_source_search_types"] = self._append_unique(
                    [],
                    candidate.get("_source_search_type"),
                )
                candidate["_source_queries"] = self._append_unique([], candidate.get("_source_query"))
                candidate["_source_actors"] = self._append_unique([], candidate.get("_source_actor"))
                merged[item_id] = candidate
                continue

            current = merged[item_id]
            current["_source_search_types"] = self._append_unique(
                current.setdefault("_source_search_types", []),
                candidate.get("_source_search_type"),
            )
            current["_source_queries"] = self._append_unique(
                current.setdefault("_source_queries", []),
                candidate.get("_source_query"),
            )
            current["_source_actors"] = self._append_unique(
                current.setdefault("_source_actors", []),
                candidate.get("_source_actor"),
            )
            current["_raw_duplicates"] = [*current.get("_raw_duplicates", []), candidate]

        return list(merged.values())

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
                raw_data={"mock": True, "provider": "apify", "search_type": "image"},
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
                raw_data={"mock": True, "provider": "apify", "search_type": "keyword"},
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
                raw_data={"mock": True, "provider": "apify", "search_type": "keyword"},
            ),
        ]
        return self._apply_filters(base_items, filters)

    def _to_source_item(self, candidate: dict[str, Any]) -> SourceItem:
        item_id = self._extract_item_id(candidate) or ""
        item_url = self._item_url(item_id, candidate)
        price_min, price_max = self._extract_price_range(candidate)
        supplier = self._extract_supplier(candidate)
        title = self._extract_first_string(
            candidate,
            [
                "title",
                "name",
                "productTitle",
                "product_title",
                "subject",
                "item.title",
                "product.title",
            ],
        )
        image_url = self._normalize_url(
            self._extract_first_string(
                candidate,
                [
                    "image",
                    "imageUrl",
                    "image_url",
                    "imgUrl",
                    "img_url",
                    "picUrl",
                    "pic_url",
                    "productImage",
                    "product_image",
                    "images.0",
                    "image_urls.0",
                    "product.images.0",
                ],
            )
        )

        raw_data = {
            "provider": "apify",
            "candidate": candidate,
            "search_types": candidate.get("_source_search_types"),
            "search_queries": candidate.get("_source_queries"),
            "actors": candidate.get("_source_actors"),
        }

        return SourceItem(
            platform=self._detect_platform(candidate, item_url),
            item_id=item_id,
            url=item_url,
            title=title or "",
            image_url=image_url or "",
            price_min=price_min,
            price_max=price_max,
            moq=self._extract_int(
                candidate,
                [
                    "moq",
                    "minOrder",
                    "min_order",
                    "minOrderQuantity",
                    "min_order_quantity",
                    "minimumOrderQuantity",
                    "minOrderQty",
                    "min_order_qty",
                    "beginAmount",
                    "begin_amount",
                    "quantityBegin",
                    "quantity_begin",
                ],
            ),
            monthly_sales=self._extract_int(
                candidate,
                [
                    "monthlySales",
                    "monthly_sales",
                    "sales",
                    "saleCount",
                    "sale_count",
                    "soldCount",
                    "sold_count",
                    "orders",
                    "orderCount",
                    "tradeCount",
                    "trade_count",
                ],
            ),
            supplier_id=self._extract_first_string(
                candidate,
                [
                    "supplierId",
                    "supplier_id",
                    "supplierUrl",
                    "supplier_url",
                    "sellerId",
                    "seller_id",
                    "shopId",
                    "shop_id",
                    "memberId",
                    "member_id",
                    "company.id",
                    "seller.id",
                    "supplier.id",
                ],
            ),
            supplier_name=supplier.get("name"),
            supplier_location=supplier.get("location"),
            supplier_years=supplier.get("years"),
            is_factory=self._is_factory(candidate, supplier),
            supports_dropshipping=self._supports_dropshipping(candidate),
            raw_data=raw_data,
        )

    def _extract_supplier(self, candidate: dict[str, Any]) -> dict[str, Any]:
        nested_supplier = self._first_dict(
            candidate,
            ["supplier", "seller", "shop", "company", "store", "vendor"],
        )
        source = nested_supplier or candidate
        return {
            "name": self._extract_first_string(
                source,
                [
                    "supplierName",
                    "supplier_name",
                    "sellerName",
                    "seller_name",
                    "shopName",
                    "shop_name",
                    "companyName",
                    "company_name",
                    "storeName",
                    "store_name",
                    "name",
                ],
            )
            or self._extract_first_string(
                candidate,
                ["supplierName", "sellerName", "shopName", "companyName"],
            ),
            "location": self._extract_first_string(
                source,
                [
                    "location",
                    "address",
                    "province",
                    "city",
                    "region",
                    "area",
                    "supplierLocation",
                    "supplier_location",
                ],
            )
            or self._extract_first_string(
                candidate,
                ["supplierLocation", "sellerLocation", "location", "address"],
            ),
            "years": self._extract_int(
                source,
                [
                    "years",
                    "supplierYears",
                    "supplier_years",
                    "shopYears",
                    "shop_years",
                    "companyYears",
                    "company_years",
                    "businessYears",
                ],
            )
            or self._extract_int(
                candidate,
                ["supplierYears", "shopYears", "companyYears", "years"],
            ),
        }

    def _item_url(self, item_id: str, candidate: dict[str, Any]) -> str:
        return self._normalize_url(
            self._extract_first_string(
                candidate,
                [
                    "url",
                    "detailUrl",
                    "detail_url",
                    "itemUrl",
                    "item_url",
                    "productUrl",
                    "product_url",
                    "link",
                    "href",
                ],
            )
            or f"https://detail.1688.com/offer/{item_id}.html"
        )

    def _detect_platform(self, candidate: dict[str, Any], item_url: str) -> str:
        site = self._extract_first_string(candidate, ["site", "platform", "source"])
        item_url_lower = item_url.lower()
        if "1688" in item_url_lower:
            return "1688"
        if "alibaba" in item_url_lower:
            return "Alibaba"
        if "aliexpress" in item_url_lower:
            return "AliExpress"
        source = f"{site or ''}".lower()
        if "1688" in source:
            return "1688"
        if "alibaba" in source:
            return "Alibaba"
        if "aliexpress" in source:
            return "AliExpress"
        return "1688"

    def _extract_item_id(self, item: dict[str, Any]) -> str | None:
        direct = self._extract_first_string(
            item,
            [
                "item_id",
                "itemId",
                "offer_id",
                "offerId",
                "id",
                "num_iid",
                "product_id",
                "productId",
                "product.id",
                "item.id",
            ],
        )
        if direct:
            return self._clean_item_id(direct)

        url = self._extract_first_string(
            item,
            ["url", "detailUrl", "detail_url", "itemUrl", "productUrl", "link", "href"],
        )
        if url:
            match = re.search(
                r"(?:offer/|offerId=|id=|product-detail/.*?_|product/)(\d{6,})",
                url,
            )
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _clean_item_id(value: str) -> str:
        match = re.search(r"\d{6,}", value)
        return match.group(0) if match else value.strip()

    def _extract_price_range(self, item: dict[str, Any]) -> tuple[float | None, float | None]:
        min_price = self._extract_float(
            item,
            [
                "priceMin",
                "price_min",
                "minPrice",
                "min_price",
                "price.min",
                "priceInfo.price",
                "priceInfo.min",
            ],
        )
        max_price = self._extract_float(
            item,
            ["priceMax", "price_max", "maxPrice", "max_price", "price.max", "priceInfo.max"],
        )
        single_price = self._extract_float(
            item,
            ["price", "salePrice", "sale_price", "unitPrice", "unit_price", "price.value"],
        )

        if min_price is not None or max_price is not None:
            return min_price or max_price, max_price or min_price
        if single_price is not None:
            return single_price, single_price

        raw_price = self._extract_first_string(
            item,
            [
                "price",
                "priceText",
                "price_text",
                "priceRange",
                "price_range",
                "priceDisplay",
                "price_display",
                "priceInfo.text",
            ],
        )
        if not raw_price:
            return None, None

        numbers = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", raw_price)]
        if not numbers:
            return None, None
        return min(numbers), max(numbers)

    def _apply_filters(self, items: list[SourceItem], filters: dict) -> list[SourceItem]:
        max_price = filters.get("max_price_cny")
        factory_only = filters.get("factory_only", False)
        dropshipping = filters.get("dropshipping", False)
        min_supplier_years = filters.get("min_supplier_years")

        results = []
        for item in items:
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

    def _is_factory(self, candidate: dict[str, Any], supplier: dict[str, Any]) -> bool:
        if self._extract_bool(
            candidate,
            [
                "isFactory",
                "is_factory",
                "factory",
                "factoryDirect",
                "factory_direct",
                "supplier.isFactory",
                "seller.isFactory",
                "shop.isFactory",
            ],
        ):
            return True
        joined = " ".join(
            str(value)
            for value in [
                candidate.get("title"),
                supplier.get("name"),
                candidate.get("tags"),
                candidate.get("badges"),
            ]
            if value
        )
        return any(word in joined for word in ["工厂", "厂家", "源头", "生产"])

    def _supports_dropshipping(self, candidate: dict[str, Any]) -> bool:
        if self._extract_bool(
            candidate,
            [
                "supportsDropshipping",
                "supports_dropshipping",
                "supportDropshipping",
                "support_dropshipping",
                "dropshipping",
                "onePieceDropshipping",
                "one_piece_dropshipping",
            ],
        ):
            return True
        joined = " ".join(
            str(value)
            for value in [
                candidate.get("title"),
                candidate.get("tags"),
                candidate.get("badges"),
                candidate.get("serviceTags"),
            ]
            if value
        )
        return any(word in joined for word in ["一件代发", "代发", "现货"])

    def _extract_first_string(self, item: dict[str, Any], paths: list[str]) -> str | None:
        for path in paths:
            value = self._get_path(item, path)
            if value is None:
                continue
            if isinstance(value, dict):
                continue
            if isinstance(value, list):
                value = value[0] if value else None
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    def _extract_float(self, item: dict[str, Any], paths: list[str]) -> float | None:
        for path in paths:
            value = self._get_path(item, path)
            if value is None or isinstance(value, (dict, list)):
                continue
            numbers = re.findall(r"\d+(?:\.\d+)?", str(value).replace(",", ""))
            if numbers:
                return float(numbers[0])
        return None

    def _extract_int(self, item: dict[str, Any], paths: list[str]) -> int | None:
        for path in paths:
            value = self._get_path(item, path)
            if value is None or isinstance(value, (dict, list)):
                continue
            numbers = re.findall(r"\d+(?:\.\d+)?", str(value).replace(",", ""))
            if numbers:
                return int(float(numbers[0]))
        return None

    def _extract_bool(self, item: dict[str, Any], paths: list[str]) -> bool:
        for path in paths:
            value = self._get_path(item, path)
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"true", "1", "yes", "y", "支持", "是"}:
                    return True
        return False

    def _first_dict(self, item: dict[str, Any], paths: list[str]) -> dict[str, Any] | None:
        for path in paths:
            value = self._get_path(item, path)
            if isinstance(value, dict):
                return value
        return None

    def _get_path(self, item: dict[str, Any], path: str) -> Any:
        value: Any = item
        for part in path.split("."):
            if isinstance(value, list):
                try:
                    value = value[int(part)]
                except (ValueError, IndexError):
                    return None
            elif isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    def _append_unique(self, values: list[Any], value: Any) -> list[Any]:
        if value is None or value in values:
            return values
        return [*values, value]

    @staticmethod
    def _normalize_url(value: str | None) -> str | None:
        if not value:
            return value
        if value.startswith("//"):
            return f"https:{value}"
        return value


source1688_service = Source1688Service()

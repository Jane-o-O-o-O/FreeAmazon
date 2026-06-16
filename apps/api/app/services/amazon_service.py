import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.models.source_search import AmazonProduct
from app.services.canopy_client import CanopyClient

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$", re.IGNORECASE)
ASIN_PATTERNS = [
    re.compile(r"/dp/([A-Z0-9]{10})(?:[/?]|$)", re.IGNORECASE),
    re.compile(r"/gp/product/([A-Z0-9]{10})(?:[/?]|$)", re.IGNORECASE),
    re.compile(r"/product/([A-Z0-9]{10})(?:[/?]|$)", re.IGNORECASE),
    re.compile(r"[?&]asin=([A-Z0-9]{10})(?:&|$)", re.IGNORECASE),
]
SHORT_LINK_HOSTS = {"a.co", "amzn.to"}
MARKETPLACE_BY_HOST = {
    "amazon.com": "US",
    "amazon.co.uk": "UK",
    "amazon.de": "DE",
    "amazon.co.jp": "JP",
    "amazon.ca": "CA",
    "amazon.com.au": "AU",
    "amazon.fr": "FR",
    "amazon.it": "IT",
    "amazon.es": "ES",
}


class AmazonService:
    def parse_asin_from_url(self, url_or_asin: str) -> str:
        value = url_or_asin.strip()
        if ASIN_RE.match(value):
            return value.upper()

        for pattern in ASIN_PATTERNS:
            match = pattern.search(value)
            if match:
                return match.group(1).upper()

        parsed = urlparse(value)
        if parsed.path:
            loose_match = re.search(r"([A-Z0-9]{10})", parsed.path, re.IGNORECASE)
            if loose_match:
                return loose_match.group(1).upper()

        raise ValueError("无法从 Amazon 链接中解析 ASIN")

    def fetch_product(self, amazon_url: str, marketplace: str) -> AmazonProduct:
        settings = get_settings()
        resolved_url = self.resolve_short_url(
            amazon_url,
            timeout_seconds=min(settings.canopy_timeout_seconds, 12),
        )
        asin = self.parse_asin_from_url(resolved_url)
        resolved_marketplace = self.marketplace_from_url(resolved_url) or marketplace

        if settings.canopy_use_mock:
            return self._mock_product(
                asin=asin,
                marketplace=resolved_marketplace,
                amazon_url=resolved_url,
            )

        client = CanopyClient(
            api_key=settings.canopy_api_key,
            base_url=settings.canopy_api_base_url,
            timeout_seconds=settings.canopy_timeout_seconds,
        )
        payload = client.get_product(asin=asin, domain=resolved_marketplace)
        return self._product_from_canopy_payload(
            payload=payload,
            fallback_asin=asin,
            fallback_url=resolved_url,
            marketplace=resolved_marketplace,
        )

    def resolve_short_url(self, url_or_asin: str, timeout_seconds: float = 10.0) -> str:
        value = url_or_asin.strip()
        if ASIN_RE.match(value):
            return value

        parsed = urlparse(value)
        host = parsed.netloc.lower().removeprefix("www.")
        if host not in SHORT_LINK_HOSTS:
            return value

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            )
        }
        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=timeout_seconds,
                headers=headers,
            ) as client:
                response = client.get(value)
                response.raise_for_status()
                return str(response.url)
        except httpx.HTTPError:
            return value

    def marketplace_from_url(self, url_or_asin: str) -> str | None:
        parsed = urlparse(url_or_asin.strip())
        host = parsed.netloc.lower().removeprefix("www.")
        if not host:
            return None
        return MARKETPLACE_BY_HOST.get(host)

    def _product_from_canopy_payload(
        self,
        *,
        payload: dict[str, Any],
        fallback_asin: str,
        fallback_url: str,
        marketplace: str,
    ) -> AmazonProduct:
        product = payload.get("data", {}).get("amazonProduct")
        if not isinstance(product, dict):
            raise ValueError("Canopy API 返回中缺少 data.amazonProduct。")

        image_urls = self._extract_image_urls(product)
        price = product.get("price") if isinstance(product.get("price"), dict) else {}
        categories = product.get("categories")

        return AmazonProduct(
            asin=str(product.get("asin") or fallback_asin).upper(),
            marketplace=marketplace.upper(),
            url=str(product.get("url") or fallback_url),
            title=str(product.get("title") or ""),
            brand=self._optional_str(product.get("brand")),
            category=self._extract_category(categories),
            price=self._optional_float(price.get("value")),
            currency=self._optional_str(price.get("currency")),
            rating=self._optional_float(product.get("rating")),
            review_count=self._optional_int(product.get("ratingsTotal")),
            main_image_url=(
                self._optional_str(product.get("mainImageUrl"))
                or (image_urls[0] if image_urls else "")
            ),
            image_urls=image_urls,
            raw_data={"provider": "canopy", "payload": payload},
        )

    def _extract_image_urls(self, product: dict[str, Any]) -> list[str]:
        urls: list[str] = []
        main_image = self._optional_str(product.get("mainImageUrl"))
        if main_image:
            urls.append(main_image)

        raw_image_urls = product.get("imageUrls")
        if isinstance(raw_image_urls, list):
            urls.extend(str(url) for url in raw_image_urls if url)

        return list(dict.fromkeys(urls))

    def _extract_category(self, categories: Any) -> str | None:
        if not isinstance(categories, list) or not categories:
            return None

        deepest = categories[-1]
        if not isinstance(deepest, dict):
            return None

        breadcrumb = self._optional_str(deepest.get("breadcrumbPath"))
        if breadcrumb:
            return breadcrumb

        names = [
            str(category.get("name"))
            for category in categories
            if isinstance(category, dict) and category.get("name")
        ]
        return " > ".join(names) if names else None

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _mock_product(self, asin: str, marketplace: str, amazon_url: str) -> AmazonProduct:
        image_seed = asin.lower()
        return AmazonProduct(
            asin=asin,
            marketplace=marketplace.upper(),
            url=amazon_url,
            title="便携式无线迷你榨汁杯，随行杯设计，USB-C 充电",
            brand="DemoBrand",
            category="厨房用品 > 小家电 > 榨汁机",
            price=29.99,
            currency="USD",
            rating=4.4,
            review_count=2381,
            main_image_url=f"https://picsum.photos/seed/{image_seed}-main/640/640",
            image_urls=[
                f"https://picsum.photos/seed/{image_seed}-main/640/640",
                f"https://picsum.photos/seed/{image_seed}-side/640/640",
                f"https://picsum.photos/seed/{image_seed}-detail/640/640",
            ],
            raw_data={"mock": True, "provider": "canopy"},
        )


amazon_service = AmazonService()

from typing import Any

import httpx


class CanopyConfigurationError(RuntimeError):
    """Raised when Canopy is enabled but credentials are incomplete."""


class CanopyApiError(RuntimeError):
    """Raised when Canopy returns an API or transport error."""


class CanopyClient:
    def __init__(
        self,
        api_key: str | None,
        base_url: str = "https://rest.canopyapi.co",
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key:
            raise CanopyConfigurationError(
                "Canopy API 未配置：请设置 CANOPY_API_KEY，或将 CANOPY_USE_MOCK=true。"
            )

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_product(
        self,
        *,
        asin: str | None = None,
        url: str | None = None,
        gtin: str | None = None,
        domain: str = "US",
    ) -> dict[str, Any]:
        return self._get(
            "/api/amazon/product",
            {
                "asin": asin,
                "url": url,
                "gtin": gtin,
                "domain": self._normalize_domain(domain),
            },
        )

    def get_gtin_from_asin(self, *, asin: str, domain: str = "US") -> dict[str, Any]:
        return self._get(
            "/api/amazon/product/gtin-from-asin",
            {"asin": asin, "domain": self._normalize_domain(domain)},
        )

    def get_asin_from_gtin(self, *, gtin: str, domain: str = "US") -> dict[str, Any]:
        return self._get(
            "/api/amazon/product/asin-from-gtin",
            {"gtin": gtin, "domain": self._normalize_domain(domain)},
        )

    def get_product_variants(
        self,
        *,
        asin: str | None = None,
        url: str | None = None,
        gtin: str | None = None,
        domain: str = "US",
    ) -> dict[str, Any]:
        return self._get_identifier_endpoint(
            "/api/amazon/product/variants",
            asin=asin,
            url=url,
            gtin=gtin,
            domain=domain,
        )

    def get_product_stock(
        self,
        *,
        asin: str | None = None,
        url: str | None = None,
        gtin: str | None = None,
        domain: str = "US",
    ) -> dict[str, Any]:
        return self._get_identifier_endpoint(
            "/api/amazon/product/stock",
            asin=asin,
            url=url,
            gtin=gtin,
            domain=domain,
        )

    def get_product_sales(
        self,
        *,
        asin: str | None = None,
        url: str | None = None,
        gtin: str | None = None,
        domain: str = "US",
    ) -> dict[str, Any]:
        return self._get_identifier_endpoint(
            "/api/amazon/product/sales",
            asin=asin,
            url=url,
            gtin=gtin,
            domain=domain,
        )

    def get_product_reviews(
        self,
        *,
        asin: str | None = None,
        url: str | None = None,
        gtin: str | None = None,
        domain: str = "US",
        page: int | None = None,
        only_verified_reviews: bool | None = None,
        rating: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        return self._get(
            "/api/amazon/product/reviews",
            {
                "asin": asin,
                "url": url,
                "gtin": gtin,
                "domain": self._normalize_domain(domain),
                "page": page,
                "onlyVerifiedReviews": only_verified_reviews,
                "rating": rating,
                "search": search,
            },
        )

    def get_product_offers(
        self,
        *,
        asin: str | None = None,
        url: str | None = None,
        gtin: str | None = None,
        domain: str = "US",
        page: int | None = None,
    ) -> dict[str, Any]:
        return self._get(
            "/api/amazon/product/offers",
            {
                "asin": asin,
                "url": url,
                "gtin": gtin,
                "domain": self._normalize_domain(domain),
                "page": page,
            },
        )

    def search_products(
        self,
        *,
        search_term: str,
        domain: str = "US",
        category_id: str | None = None,
        page: int | None = None,
        limit: int | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        conditions: str | None = None,
        sort: str | None = None,
    ) -> dict[str, Any]:
        return self._get(
            "/api/amazon/search",
            {
                "searchTerm": search_term,
                "domain": self._normalize_domain(domain),
                "categoryId": category_id,
                "page": page,
                "limit": limit,
                "minPrice": min_price,
                "maxPrice": max_price,
                "conditions": conditions,
                "sort": sort,
            },
        )

    def autocomplete(
        self,
        *,
        search_term: str,
        domain: str = "US",
        category: str | None = None,
    ) -> dict[str, Any]:
        return self._get(
            "/api/amazon/autocomplete",
            {
                "searchTerm": search_term,
                "domain": self._normalize_domain(domain),
                "category": category,
            },
        )

    def get_categories(self, *, domain: str = "US") -> dict[str, Any]:
        return self._get("/api/amazon/categories", {"domain": self._normalize_domain(domain)})

    def get_category(
        self,
        *,
        category_id: str,
        domain: str = "US",
        page: int | None = None,
        sort: str | None = None,
    ) -> dict[str, Any]:
        return self._get(
            "/api/amazon/category",
            {
                "categoryId": category_id,
                "domain": self._normalize_domain(domain),
                "page": page,
                "sort": sort,
            },
        )

    def get_seller(
        self,
        *,
        seller_id: str,
        domain: str = "US",
        page: int | None = None,
    ) -> dict[str, Any]:
        return self._get(
            "/api/amazon/seller",
            {"sellerId": seller_id, "domain": self._normalize_domain(domain), "page": page},
        )

    def get_author(
        self,
        *,
        asin: str,
        domain: str = "US",
        page: int | None = None,
    ) -> dict[str, Any]:
        return self._get(
            "/api/amazon/author",
            {"asin": asin, "domain": self._normalize_domain(domain), "page": page},
        )

    def get_deals(
        self,
        *,
        domain: str = "US",
        page: int | None = None,
        limit: int | None = None,
        category_ids: str | None = None,
    ) -> dict[str, Any]:
        return self._get(
            "/api/amazon/deals",
            {
                "domain": self._normalize_domain(domain),
                "page": page,
                "limit": limit,
                "categoryIds": category_ids,
            },
        )

    def get_bestsellers(
        self,
        *,
        domain: str = "US",
        page: int | None = None,
        limit: int | None = None,
        category_id: str | None = None,
        url: str | None = None,
    ) -> dict[str, Any]:
        return self._get(
            "/api/amazon/bestsellers",
            {
                "domain": self._normalize_domain(domain),
                "page": page,
                "limit": limit,
                "categoryId": category_id,
                "url": url,
            },
        )

    def get_bestseller_categories(self, *, domain: str = "US") -> dict[str, Any]:
        return self._get(
            "/api/amazon/bestseller-categories",
            {"domain": self._normalize_domain(domain)},
        )

    def _get_identifier_endpoint(
        self,
        path: str,
        *,
        asin: str | None,
        url: str | None,
        gtin: str | None,
        domain: str,
    ) -> dict[str, Any]:
        return self._get(
            path,
            {
                "asin": asin,
                "url": url,
                "gtin": gtin,
                "domain": self._normalize_domain(domain),
            },
        )

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        cleaned_params = {key: value for key, value in params.items() if value is not None}
        headers = {"API-KEY": self.api_key}

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url, params=cleaned_params, headers=headers)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = self._extract_error_message(exc.response)
            raise CanopyApiError(
                f"Canopy API 请求失败，HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise CanopyApiError("Canopy API 请求超时，请稍后重试或调大超时时间。") from exc
        except httpx.HTTPError as exc:
            raise CanopyApiError(f"Canopy API 网络请求失败：{exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise CanopyApiError("Canopy API 返回了无法解析的 JSON。") from exc

        if isinstance(payload, dict) and payload.get("errors"):
            raise CanopyApiError(f"Canopy API 返回错误：{payload['errors']}")
        if not isinstance(payload, dict):
            raise CanopyApiError("Canopy API 返回了非 JSON 对象。")
        return payload

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        return (domain or "US").strip().upper()

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text[:500]

        if isinstance(payload, dict):
            errors = payload.get("errors")
            if isinstance(errors, list) and errors:
                messages = [str(error.get("message", error)) for error in errors]
                return "; ".join(messages)
            if payload.get("message"):
                return str(payload["message"])
        return str(payload)

from dataclasses import dataclass
from typing import Any

import httpx


class ApifyConfigurationError(RuntimeError):
    """Raised when Apify is enabled but credentials are incomplete."""


class ApifyApiError(RuntimeError):
    """Raised when Apify returns an API, Actor, or transport error."""


@dataclass(frozen=True)
class ApifyActors:
    reverse_image: str | None
    keyword_search: str


class ApifyClient:
    def __init__(
        self,
        *,
        api_token: str | None,
        base_url: str,
        timeout_seconds: float,
        actors: ApifyActors,
    ) -> None:
        if not api_token:
            raise ApifyConfigurationError(
                "Apify 未配置：请设置 APIFY_API_TOKEN，或将 APIFY_USE_MOCK=true。"
            )

        self.api_token = api_token
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.actors = actors

    def search_by_image(
        self,
        *,
        image_url: str,
        destination: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        if not self.actors.reverse_image:
            return []

        payload = {
            "imageUrl": image_url,
            "destination": destination,
        }
        return self._trim_items(self.run_actor(self.actors.reverse_image, payload), limit)

    def search_by_keyword(
        self,
        *,
        keyword: str,
        limit: int,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self.search_by_keywords(keywords=[keyword], limit=limit, filters=filters)

    def search_by_keywords(
        self,
        *,
        keywords: list[str],
        limit: int,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        keywords = [keyword.strip() for keyword in keywords if keyword and keyword.strip()]
        if not keywords:
            return []

        if self._is_zen_studio_1688_actor(self.actors.keyword_search):
            payload = self._build_zen_studio_keyword_payload(
                keywords=keywords,
                limit=limit,
                filters=filters,
            )
            return self._trim_items(self.run_actor(self.actors.keyword_search, payload), limit * len(keywords))

        payload: dict[str, Any] = {
            "keyword": keywords[0],
            "max_items_per_url": limit,
            "max_retries_per_url": 2,
            "ignore_url_failures": True,
            "proxy": {"useApifyProxy": False},
        }

        max_price = filters.get("max_price_cny")
        if max_price is not None:
            payload["priceEnd"] = str(max_price)

        return self._trim_items(self.run_actor(self.actors.keyword_search, payload), limit)

    @staticmethod
    def _is_zen_studio_1688_actor(actor_id: str) -> bool:
        normalized = actor_id.lower().replace("~", "/")
        return normalized in {
            "ghxsmzcw3gxscrkir",
            "zen-studio/1688-wholesale-scraper",
        } or normalized.endswith("/1688-wholesale-scraper")

    @staticmethod
    def _build_zen_studio_keyword_payload(
        *,
        keywords: list[str],
        limit: int,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "keywords": keywords,
            "maxResults": max(1, min(int(limit), 10000)),
            "sortBy": str(filters.get("sort_by") or "relevance"),
            "includeSkuDetails": bool(filters.get("include_sku_details", False)),
        }

        max_price = filters.get("max_price_cny")
        if max_price is not None:
            payload["priceMax"] = int(float(max_price))

        max_moq = filters.get("max_moq")
        if max_moq is not None:
            payload["minOrderQuantity"] = max(1, int(float(max_moq)))

        if filters.get("factory_only"):
            payload["merchantType"] = "superFactory"

        province = filters.get("province")
        if province:
            payload["province"] = str(province)

        city = filters.get("city")
        if city:
            payload["city"] = str(city)

        return payload

    def run_actor(self, actor_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        url = f"{self.base_url}/acts/{self._normalize_actor_id(actor_id)}/run-sync-get-dataset-items"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = self._extract_error_message(exc.response)
            raise ApifyApiError(
                f"Apify Actor 请求失败，HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise ApifyApiError("Apify Actor 请求超时，请稍后重试或调大 APIFY_TIMEOUT_SECONDS。") from exc
        except httpx.HTTPError as exc:
            raise ApifyApiError(f"Apify 网络请求失败：{exc}") from exc

        try:
            payload_data = response.json()
        except ValueError as exc:
            raise ApifyApiError("Apify 返回了无法解析的 JSON。") from exc

        if isinstance(payload_data, list):
            return [item for item in payload_data if isinstance(item, dict)]
        if isinstance(payload_data, dict) and payload_data.get("error"):
            raise ApifyApiError(f"Apify 返回错误：{payload_data['error']}")
        if isinstance(payload_data, dict):
            return self._extract_items(payload_data)

        raise ApifyApiError("Apify 返回了不支持的数据结构。")

    @staticmethod
    def _normalize_actor_id(actor_id: str) -> str:
        return actor_id.replace("/", "~")

    @staticmethod
    def _trim_items(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        return items[: max(0, limit)]

    @staticmethod
    def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: list[Any] = [
            payload.get("items"),
            payload.get("results"),
            payload.get("result"),
            payload.get("data"),
        ]
        for candidate in candidates:
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
            if isinstance(candidate, dict):
                nested = ApifyClient._extract_items(candidate)
                if nested:
                    return nested
        return [payload]

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text[:500]

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])
            for key in ("message", "msg", "error", "error_message"):
                if payload.get(key):
                    return str(payload[key])
        return str(payload)

import json
import re
from typing import Any

import httpx

from app.core.config import get_settings
from app.models.source_search import AmazonProduct


class SiliconFlowKeywordError(RuntimeError):
    """Raised when the optional SiliconFlow keyword generation fails."""


class SiliconFlowKeywordService:
    def generate_keywords(self, amazon_product: AmazonProduct) -> list[str]:
        settings = get_settings()
        fallback = self.fallback_keywords(amazon_product)

        if settings.siliconflow_use_mock or not settings.siliconflow_api_key:
            return fallback

        try:
            generated = self._generate_with_llm(
                api_key=settings.siliconflow_api_key,
                base_url=settings.siliconflow_base_url,
                model=settings.siliconflow_model,
                timeout_seconds=settings.siliconflow_timeout_seconds,
                amazon_product=amazon_product,
            )
        except SiliconFlowKeywordError:
            return fallback

        return self._dedupe_keywords([*generated, *fallback])

    def fallback_keywords(self, amazon_product: AmazonProduct) -> list[str]:
        source = f"{amazon_product.title} {amazon_product.category or ''}".lower()
        mapping = [
            (["blender", "juicer", "juice", "smoothie"], "便携榨汁杯"),
            (["cup", "bottle"], "随行杯"),
            (["usb", "type-c", "portable", "rechargeable"], "USB充电"),
            (["laundry", "detergent", "pods"], "洗衣凝珠"),
            (["organizer", "storage"], "收纳"),
            (["kitchen"], "厨房用品"),
            (["pet"], "宠物用品"),
            (["baby"], "母婴用品"),
            (["led", "light"], "LED灯"),
            (["silicone"], "硅胶"),
        ]

        keywords = []
        for needles, keyword in mapping:
            if any(needle in source for needle in needles):
                keywords.append(keyword)

        title_words = re.findall(r"[A-Za-z0-9][A-Za-z0-9+-]{2,}", amazon_product.title)
        if title_words:
            keywords.append(" ".join(title_words[:4]))

        if amazon_product.category:
            category_tail = amazon_product.category.split(">")[-1].strip()
            if category_tail:
                keywords.append(category_tail)

        return self._dedupe_keywords(keywords)[:5] or [amazon_product.title[:40]]

    def _generate_with_llm(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
        amazon_product: AmazonProduct,
    ) -> list[str]:
        url = f"{base_url.rstrip('/')}/chat/completions"
        prompt = (
            "你是跨境电商1688选品助手。请根据 Amazon 商品信息生成 3-5 个适合在 1688 搜索的中文关键词。"
            "要求：只输出 JSON 数组；关键词要偏商品通用名和材质/用途，不要包含品牌名、Amazon、型号噪声。"
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "title": amazon_product.title,
                            "brand": amazon_product.brand,
                            "category": amazon_product.category,
                            "price": amazon_product.price,
                            "currency": amazon_product.currency,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SiliconFlowKeywordError(f"SiliconFlow 关键词生成失败：{exc}") from exc

        content = self._extract_message_content(data)
        keywords = self._parse_keywords(content)
        if not keywords:
            raise SiliconFlowKeywordError("SiliconFlow 未返回可用关键词。")
        return keywords

    def _extract_message_content(self, data: dict[str, Any]) -> str:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""

        first = choices[0]
        if not isinstance(first, dict):
            return ""

        message = first.get("message")
        if isinstance(message, dict) and message.get("content"):
            return str(message["content"])
        return str(first.get("text") or "")

    def _parse_keywords(self, content: str) -> list[str]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            parsed = re.split(r"[,，\n、]", cleaned)

        if isinstance(parsed, list):
            return self._dedupe_keywords(str(item) for item in parsed)
        return []

    @staticmethod
    def _dedupe_keywords(values: list[str] | Any) -> list[str]:
        seen = set()
        keywords = []
        for value in values:
            keyword = str(value).strip().strip('"').strip("'")
            if not keyword or keyword in seen:
                continue
            seen.add(keyword)
            keywords.append(keyword[:50])
        return keywords


siliconflow_keyword_service = SiliconFlowKeywordService()

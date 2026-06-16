import json
import re
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.copywriting import CopywritingRequest, CopywritingResponse


class CopywritingGenerationError(RuntimeError):
    """Raised when the LLM copywriting generation fails."""


class CopywritingService:
    skill_id = "amazon-copywriting-v1"

    site_profiles = {
        "amazon": {
            "name": "Amazon",
            "title_limit": 180,
            "style": "清晰呈现核心关键词、规格和购买理由",
            "cta": "适合日常使用、送礼和跨境电商选品测试。",
        },
        "tiktok": {
            "name": "TikTok Shop",
            "title_limit": 110,
            "style": "短促、有画面感，适合直播间和短视频转化",
            "cta": "适合短视频展示、直播讲解和冲动型下单场景。",
        },
        "shopee": {
            "name": "Shopee",
            "title_limit": 120,
            "style": "突出性价比、现货和关键词覆盖",
            "cta": "适合东南亚平台上架，方便用户快速理解卖点。",
        },
        "lazada": {
            "name": "Lazada",
            "title_limit": 120,
            "style": "强调品质、参数和平台搜索关键词",
            "cta": "适合平台搜索流量和活动页转化。",
        },
        "ebay": {
            "name": "eBay",
            "title_limit": 80,
            "style": "标题更紧凑，突出品类词和关键属性",
            "cta": "适合价格比较、长尾搜索和跨境买家浏览。",
        },
        "shopify": {
            "name": "独立站",
            "title_limit": 140,
            "style": "更像品牌详情页，重视场景、信任感和转化文案",
            "cta": "适合独立站详情页、广告落地页和邮件营销。",
        },
    }

    def generate(self, payload: CopywritingRequest) -> CopywritingResponse:
        settings = get_settings()
        if not settings.siliconflow_use_mock and settings.siliconflow_api_key:
            try:
                return self._generate_with_siliconflow(
                    payload=payload,
                    api_key=settings.siliconflow_api_key,
                    base_url=settings.siliconflow_base_url,
                    model=settings.siliconflow_model,
                    timeout_seconds=settings.siliconflow_timeout_seconds,
                )
            except CopywritingGenerationError:
                pass

        return self._generate_with_template(payload)

    def _generate_with_template(self, payload: CopywritingRequest) -> CopywritingResponse:
        profile = self._profile(payload.site)
        points = self._split_values(payload.selling_points)
        keywords = self._split_values(payload.keywords)
        audience = payload.audience or "跨境电商买家"

        title_parts = [payload.product_name, *keywords[:3], points[0] if points else ""]
        title = self._limit_text(" ".join(part for part in title_parts if part), profile["title_limit"])
        short_title = self._limit_text(f"{payload.product_name} | {profile['name']} 热卖款", 56)

        bullets = self._bullets(
            product_name=payload.product_name,
            audience=audience,
            points=points,
            profile_name=profile["name"],
            tone=payload.tone,
        )
        description = self._description(
            product_name=payload.product_name,
            audience=audience,
            points=points,
            keywords=keywords,
            profile=profile,
            tone=payload.tone,
        )

        tags = self._dedupe([profile["name"], payload.product_name, *keywords, *points])[:10]
        seo_keywords = self._dedupe([payload.product_name, *keywords, audience, profile["name"]])[:8]

        return CopywritingResponse(
            site=profile["name"],
            generation_source="template",
            model=None,
            skill=self.skill_id,
            title=title,
            short_title=short_title,
            bullet_points=bullets,
            description=description,
            tags=tags,
            seo_keywords=seo_keywords,
        )

    def _generate_with_siliconflow(
        self,
        *,
        payload: CopywritingRequest,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
    ) -> CopywritingResponse:
        profile = self._profile(payload.site)
        url = f"{base_url.rstrip('/')}/chat/completions"
        request_payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": self._copywriting_skill_prompt()},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "target_site": profile["name"],
                            "site_style": profile["style"],
                            "title_limit": profile["title_limit"],
                            "language": payload.language,
                            "tone": payload.tone,
                            "product_name": payload.product_name,
                            "audience": payload.audience,
                            "selling_points": self._split_values(payload.selling_points),
                            "keywords": self._split_values(payload.keywords),
                            "guardrails": [
                                "只使用输入中已经提供的信息，不要编造尺寸、容量、材质、认证、质保、销量、排名、功效或平台背书。",
                                "如果输入信息不足，用稳健的通用表达，不要把猜测写成事实。",
                                "标题、短标题、五点卖点、详情描述、标签和 SEO 关键词都必须与目标站点风格匹配。",
                            ],
                            "required_output": {
                                "title": "string",
                                "short_title": "string",
                                "bullet_points": ["string", "string", "string", "string", "string"],
                                "description": "string",
                                "tags": ["string"],
                                "seo_keywords": ["string"],
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0.35,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(url, json=request_payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CopywritingGenerationError(f"SiliconFlow 文案生成失败：{exc}") from exc

        content = self._extract_message_content(data)
        parsed = self._parse_json_object(content)
        if not parsed:
            raise CopywritingGenerationError("SiliconFlow 未返回可解析的 JSON 文案。")

        return self._normalize_llm_response(parsed, profile, payload, model)

    def _normalize_llm_response(
        self,
        parsed: dict[str, Any],
        profile: dict[str, object],
        payload: CopywritingRequest,
        model: str,
    ) -> CopywritingResponse:
        fallback = self._generate_with_template(payload)
        title_limit = int(profile["title_limit"])
        title = self._limit_text(str(parsed.get("title") or fallback.title), title_limit)
        short_title = self._limit_text(str(parsed.get("short_title") or fallback.short_title), 64)

        bullet_points = self._string_list(parsed.get("bullet_points"))[:5] or fallback.bullet_points
        tags = self._string_list(parsed.get("tags"))[:12] or fallback.tags
        seo_keywords = self._string_list(parsed.get("seo_keywords"))[:12] or fallback.seo_keywords
        description = str(parsed.get("description") or fallback.description).strip()

        return CopywritingResponse(
            site=str(profile["name"]),
            generation_source="siliconflow",
            model=model,
            skill=self.skill_id,
            title=title,
            short_title=short_title,
            bullet_points=bullet_points,
            description=description,
            tags=tags,
            seo_keywords=seo_keywords,
        )

    def _profile(self, site: str) -> dict[str, object]:
        normalized = site.strip().lower()
        return self.site_profiles.get(normalized, self.site_profiles["amazon"])

    def _copywriting_skill_prompt(self) -> str:
        skill_path = Path(__file__).resolve().parents[4] / "docs" / "AMAZON_COPYWRITING_SKILL.md"
        try:
            skill = skill_path.read_text(encoding="utf-8")
        except OSError:
            skill = "你是资深 Amazon Listing 文案优化师。只输出 JSON，不要输出 Markdown。"
        return (
            f"{skill}\n\n"
            "额外要求：严格输出一个 JSON object；字段必须包含 title、short_title、"
            "bullet_points、description、tags、seo_keywords。不要把 JSON 包在代码块里。"
            "不要虚构输入中没有出现的规格、材质、认证、保修、销量、排名、功效承诺或平台背书。"
        )

    def _bullets(
        self,
        *,
        product_name: str,
        audience: str,
        points: list[str],
        profile_name: str,
        tone: str,
    ) -> list[str]:
        base_points = points[:4] or ["实用设计", "适合跨境上架", "日常使用友好", "便于展示卖点"]
        bullets = [
            f"{point}：围绕 {product_name} 的核心使用场景，帮助 {audience} 更快判断价值。"
            for point in base_points
        ]
        bullets.append(f"{profile_name} 文案风格：{tone}，标题、卖点和描述可直接作为上架初稿。")
        return bullets[:5]

    def _description(
        self,
        *,
        product_name: str,
        audience: str,
        points: list[str],
        keywords: list[str],
        profile: dict[str, object],
        tone: str,
    ) -> str:
        point_text = "、".join(points[:5]) if points else "实用、易理解、适合跨境销售"
        keyword_text = "、".join(keywords[:6]) if keywords else product_name
        return (
            f"{product_name} 面向 {audience}，适合用于 {profile['name']} 平台上架。"
            f"文案重点突出 {point_text}，整体语气保持{tone}。"
            f"结合平台风格：{profile['style']}。"
            f"建议在标题、五点描述、详情页首屏和搜索标签中自然覆盖关键词：{keyword_text}。"
            f"{profile['cta']}"
        )

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

    def _parse_json_object(self, content: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.S)
            if not match:
                return {}
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}

        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in re.split(r"[,，\n、;；]", value) if item.strip()]
        return []

    @staticmethod
    def _split_values(value: str | None) -> list[str]:
        if not value:
            return []
        separators = [",", "，", "\n", "、", ";", "；"]
        normalized = value
        for separator in separators:
            normalized = normalized.replace(separator, "|")
        return [item.strip() for item in normalized.split("|") if item.strip()]

    @staticmethod
    def _limit_text(value: str, limit: object) -> str:
        max_length = int(limit)
        text = " ".join(value.split())
        return text if len(text) <= max_length else text[: max_length - 1].rstrip() + "…"

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        seen = set()
        results = []
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            results.append(normalized)
        return results


copywriting_service = CopywritingService()

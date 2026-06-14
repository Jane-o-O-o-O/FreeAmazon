from app.models.source_search import AmazonProduct, RankedSourceItem, SourceItem
from app.services.clip_service import clip_service


class RankingService:
    def rank(
        self,
        amazon_product: AmazonProduct,
        candidates: list[SourceItem],
    ) -> list[RankedSourceItem]:
        ranked = [self.score_candidate(amazon_product, candidate) for candidate in candidates]
        return sorted(ranked, key=lambda item: item.final_score, reverse=True)

    def score_candidate(
        self,
        amazon_product: AmazonProduct,
        candidate: SourceItem,
    ) -> RankedSourceItem:
        image_similarity = clip_service.image_similarity(
            amazon_product.main_image_url,
            candidate.image_url,
        )
        title_similarity = self._title_similarity(amazon_product.title, candidate.title)
        category_similarity = 0.78 if self._has_any(candidate.title, ["榨汁", "果汁", "料理杯"]) else 0.45
        price_score = self._price_score(candidate)
        supplier_score = self._supplier_score(candidate)
        risk_penalty = self._risk_penalty(amazon_product, candidate)

        final_score = (
            image_similarity * 0.45
            + title_similarity * 0.20
            + category_similarity * 0.10
            + price_score * 0.10
            + supplier_score * 0.10
            - risk_penalty * 0.05
        )

        final_score = round(max(0, min(1, final_score)), 4)
        match_label = self._match_label(final_score, image_similarity)
        explanation = self._explain(candidate, image_similarity, supplier_score)

        return RankedSourceItem(
            item=candidate,
            image_similarity=round(image_similarity, 4),
            title_similarity=round(title_similarity, 4),
            category_similarity=round(category_similarity, 4),
            price_score=round(price_score, 4),
            supplier_score=round(supplier_score, 4),
            risk_penalty=round(risk_penalty, 4),
            final_score=final_score,
            match_label=match_label,
            explanation=explanation,
        )

    def _title_similarity(self, source: str, target: str) -> float:
        source_tokens = self._tokenize(source)
        target_tokens = self._tokenize(target)
        if not source_tokens or not target_tokens:
            return 0
        overlap = source_tokens & target_tokens
        return len(overlap) / max(len(source_tokens), len(target_tokens))

    def _tokenize(self, value: str) -> set[str]:
        normalized = value.lower()
        keywords = [
            "便携",
            "无线",
            "迷你",
            "榨汁",
            "果汁",
            "料理杯",
            "usb",
            "type-c",
            "充电",
            "随行杯",
            "小家电",
            "批发",
        ]
        tokens = {keyword for keyword in keywords if keyword in normalized}
        tokens.update(part for part in normalized.replace("-", " ").split() if part)
        return tokens

    def _has_any(self, value: str, keywords: list[str]) -> bool:
        return any(keyword in value for keyword in keywords)

    def _price_score(self, candidate: SourceItem) -> float:
        if candidate.price_min is None:
            return 0.3
        if candidate.price_min <= 20:
            return 0.9
        if candidate.price_min <= 35:
            return 0.75
        if candidate.price_min <= 60:
            return 0.55
        return 0.25

    def _supplier_score(self, candidate: SourceItem) -> float:
        score = 0.35
        if candidate.is_factory:
            score += 0.25
        if candidate.supports_dropshipping:
            score += 0.15
        if candidate.supplier_years:
            score += min(candidate.supplier_years, 8) * 0.03
        if candidate.monthly_sales and candidate.monthly_sales > 300:
            score += 0.08
        return min(score, 1.0)

    def _risk_penalty(self, amazon_product: AmazonProduct, candidate: SourceItem) -> float:
        brand = (amazon_product.brand or "").lower()
        title = candidate.title.lower()
        if brand and brand not in {"demobrand"} and brand in title:
            return 0.7
        return 0.1

    def _match_label(self, final_score: float, image_similarity: float) -> str:
        if final_score >= 0.78 and image_similarity >= 0.82:
            return "疑似同款"
        if final_score >= 0.62:
            return "相似款"
        return "低可信"

    def _explain(
        self,
        candidate: SourceItem,
        image_similarity: float,
        supplier_score: float,
    ) -> str:
        parts = [f"图片相似度 {image_similarity:.2f}"]
        if candidate.is_factory:
            parts.append("工厂型供应商")
        if candidate.supports_dropshipping:
            parts.append("支持一件代发")
        parts.append(f"供应商评分 {supplier_score:.2f}")
        return "；".join(parts)


ranking_service = RankingService()

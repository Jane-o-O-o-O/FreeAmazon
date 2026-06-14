from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass
class AmazonProduct:
    asin: str
    marketplace: str
    url: str
    title: str
    brand: str | None
    category: str | None
    price: float | None
    currency: str | None
    rating: float | None
    review_count: int | None
    main_image_url: str
    image_urls: list[str]
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceItem:
    platform: str
    item_id: str
    url: str
    title: str
    image_url: str
    price_min: float | None
    price_max: float | None
    moq: int | None
    monthly_sales: int | None
    supplier_id: str | None
    supplier_name: str | None
    supplier_location: str | None
    supplier_years: int | None
    is_factory: bool
    supports_dropshipping: bool
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class RankedSourceItem:
    item: SourceItem
    image_similarity: float
    title_similarity: float
    category_similarity: float
    price_score: float
    supplier_score: float
    risk_penalty: float
    final_score: float
    match_label: str
    explanation: str


@dataclass
class SourceSearchTask:
    id: str
    amazon_url: str
    marketplace: str
    status: str
    progress: int = 0
    message: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=now_utc)
    updated_at: datetime = field(default_factory=now_utc)


@dataclass
class SourceSearchResult:
    task_id: str
    amazon_product: AmazonProduct
    candidates: list[RankedSourceItem]

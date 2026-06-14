from datetime import datetime

from pydantic import BaseModel, Field


class SourceSearchFilters(BaseModel):
    max_price_cny: float | None = None
    factory_only: bool = False
    dropshipping: bool = False
    min_supplier_years: int | None = None


class CreateSourceSearchTaskRequest(BaseModel):
    amazon_url: str = Field(..., min_length=5)
    marketplace: str = Field(default="US", min_length=2, max_length=8)
    filters: SourceSearchFilters = Field(default_factory=SourceSearchFilters)


class SourceSearchTaskResponse(BaseModel):
    task_id: str
    status: str
    progress: int
    message: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AmazonProductResponse(BaseModel):
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


class RankedSourceItemResponse(BaseModel):
    source: str
    item_id: str
    title: str
    url: str
    image_url: str
    price_min: float | None
    price_max: float | None
    moq: int | None
    monthly_sales: int | None
    supplier_name: str | None
    supplier_location: str | None
    supplier_years: int | None
    is_factory: bool
    supports_dropshipping: bool
    image_similarity: float
    title_similarity: float
    category_similarity: float
    price_score: float
    supplier_score: float
    risk_penalty: float
    final_score: float
    match_label: str
    explanation: str


class SourceSearchResultResponse(BaseModel):
    task_id: str
    amazon_product: AmazonProductResponse
    candidates: list[RankedSourceItemResponse]

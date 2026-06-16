from pydantic import BaseModel, Field


class CopywritingRequest(BaseModel):
    site: str = Field(..., min_length=2, max_length=40)
    product_name: str = Field(..., min_length=2, max_length=200)
    audience: str | None = Field(default=None, max_length=120)
    selling_points: str | None = Field(default=None, max_length=1000)
    keywords: str | None = Field(default=None, max_length=500)
    tone: str = Field(default="专业可信", max_length=40)
    language: str = Field(default="中文", max_length=20)


class CopywritingResponse(BaseModel):
    site: str
    generation_source: str = "template"
    model: str | None = None
    skill: str = "amazon-copywriting-v1"
    title: str
    short_title: str
    bullet_points: list[str]
    description: str
    tags: list[str]
    seo_keywords: list[str]

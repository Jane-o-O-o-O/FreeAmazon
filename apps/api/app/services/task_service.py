from uuid import uuid4

from fastapi import BackgroundTasks

from app.models.source_search import SourceSearchResult, SourceSearchTask, now_utc
from app.schemas.source_search import (
    AmazonProductResponse,
    CreateSourceSearchTaskRequest,
    RankedSourceItemResponse,
    SourceSearchResultResponse,
    SourceSearchTaskResponse,
)
from app.services.amazon_service import amazon_service
from app.services.ranking_service import ranking_service
from app.services.source1688_service import source1688_service


class TaskService:
    def __init__(self) -> None:
        self._tasks: dict[str, SourceSearchTask] = {}
        self._results: dict[str, SourceSearchResult] = {}

    def create(
        self,
        payload: CreateSourceSearchTaskRequest,
        background_tasks: BackgroundTasks,
    ) -> SourceSearchTaskResponse:
        task_id = f"task_{uuid4().hex[:12]}"
        task = SourceSearchTask(
            id=task_id,
            amazon_url=payload.amazon_url,
            marketplace=payload.marketplace.upper(),
            status="created",
            progress=0,
            message="任务已创建",
        )
        self._tasks[task_id] = task
        background_tasks.add_task(self.run, task_id, payload)
        return self._task_response(task)

    def create_and_run(self, payload: CreateSourceSearchTaskRequest) -> SourceSearchTaskResponse:
        task_id = f"task_{uuid4().hex[:12]}"
        task = SourceSearchTask(
            id=task_id,
            amazon_url=payload.amazon_url,
            marketplace=payload.marketplace.upper(),
            status="created",
            progress=0,
            message="任务已创建",
        )
        self._tasks[task_id] = task
        self.run(task_id, payload)
        return self._task_response(task)

    def run(self, task_id: str, payload: CreateSourceSearchTaskRequest) -> None:
        task = self._tasks[task_id]
        try:
            self._run_pipeline(task, payload)
        except Exception as exc:
            task.status = "failed"
            task.progress = 100
            task.error_message = str(exc)
            task.message = "任务执行失败"
            task.updated_at = now_utc()

    def get_task(self, task_id: str) -> SourceSearchTaskResponse | None:
        task = self._tasks.get(task_id)
        return self._task_response(task) if task else None

    def get_result(self, task_id: str) -> SourceSearchResultResponse | None:
        result = self._results.get(task_id)
        return self._result_response(result) if result else None

    def _run_pipeline(
        self,
        task: SourceSearchTask,
        payload: CreateSourceSearchTaskRequest,
    ) -> None:
        self._update(task, "fetching_amazon", 20, "正在读取 Amazon 商品信息")
        amazon_product = amazon_service.fetch_product(payload.amazon_url, payload.marketplace)
        task.marketplace = amazon_product.marketplace
        self._results[task.id] = SourceSearchResult(
            task_id=task.id,
            amazon_product=amazon_product,
            candidates=[],
            is_partial=True,
        )

        self._update(task, "searching_1688", 45, "正在搜索 1688 候选货源")
        candidates = source1688_service.search_candidates(
            amazon_product=amazon_product,
            filters=payload.filters.model_dump(),
        )

        self._update(task, "reranking", 75, "正在计算相似度并排序")
        ranked = ranking_service.rank(amazon_product, candidates)

        self._results[task.id] = SourceSearchResult(
            task_id=task.id,
            amazon_product=amazon_product,
            candidates=ranked,
            is_partial=False,
        )
        self._update(task, "completed", 100, "匹配完成")

    def _update(self, task: SourceSearchTask, status: str, progress: int, message: str) -> None:
        task.status = status
        task.progress = progress
        task.message = message
        task.updated_at = now_utc()

    def _task_response(self, task: SourceSearchTask) -> SourceSearchTaskResponse:
        return SourceSearchTaskResponse(
            task_id=task.id,
            status=task.status,
            progress=task.progress,
            message=task.message,
            error_message=task.error_message,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    def _result_response(self, result: SourceSearchResult) -> SourceSearchResultResponse:
        product = result.amazon_product
        return SourceSearchResultResponse(
            task_id=result.task_id,
            amazon_product=AmazonProductResponse(
                asin=product.asin,
                marketplace=product.marketplace,
                url=product.url,
                title=product.title,
                brand=product.brand,
                category=product.category,
                price=product.price,
                currency=product.currency,
                rating=product.rating,
                review_count=product.review_count,
                main_image_url=product.main_image_url,
                image_urls=product.image_urls,
            ),
            candidates=[
                RankedSourceItemResponse(
                    source=ranked.item.platform,
                    item_id=ranked.item.item_id,
                    title=ranked.item.title,
                    url=ranked.item.url,
                    image_url=ranked.item.image_url,
                    price_min=ranked.item.price_min,
                    price_max=ranked.item.price_max,
                    moq=ranked.item.moq,
                    monthly_sales=ranked.item.monthly_sales,
                    supplier_name=ranked.item.supplier_name,
                    supplier_location=ranked.item.supplier_location,
                    supplier_years=ranked.item.supplier_years,
                    is_factory=ranked.item.is_factory,
                    supports_dropshipping=ranked.item.supports_dropshipping,
                    image_similarity=ranked.image_similarity,
                    title_similarity=ranked.title_similarity,
                    category_similarity=ranked.category_similarity,
                    price_score=ranked.price_score,
                    supplier_score=ranked.supplier_score,
                    risk_penalty=ranked.risk_penalty,
                    final_score=ranked.final_score,
                    match_label=ranked.match_label,
                    explanation=ranked.explanation,
                )
                for ranked in result.candidates
            ],
            is_partial=result.is_partial,
        )


task_service = TaskService()

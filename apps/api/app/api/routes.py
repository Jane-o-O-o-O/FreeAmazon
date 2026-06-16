from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.schemas.copywriting import CopywritingRequest, CopywritingResponse
from app.schemas.source_search import (
    CreateSourceSearchTaskRequest,
    SourceSearchResultResponse,
    SourceSearchTaskResponse,
)
from app.services.copywriting_service import copywriting_service
from app.services.task_service import task_service

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/copywriting/generate", response_model=CopywritingResponse)
def generate_copywriting(payload: CopywritingRequest) -> CopywritingResponse:
    return copywriting_service.generate(payload)


@router.post("/api/source-search/tasks", response_model=SourceSearchTaskResponse)
def create_source_search_task(
    payload: CreateSourceSearchTaskRequest,
    background_tasks: BackgroundTasks,
) -> SourceSearchTaskResponse:
    return task_service.create(payload, background_tasks)


@router.get("/api/source-search/tasks/{task_id}", response_model=SourceSearchTaskResponse)
def get_source_search_task(task_id: str) -> SourceSearchTaskResponse:
    task = task_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get(
    "/api/source-search/tasks/{task_id}/results",
    response_model=SourceSearchResultResponse,
)
def get_source_search_results(task_id: str) -> SourceSearchResultResponse:
    result = task_service.get_result(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result

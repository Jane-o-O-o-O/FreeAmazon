from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Response

from app.schemas.auth import LoginRequest, LoginResponse, SessionResponse
from app.schemas.copywriting import CopywritingRequest, CopywritingResponse
from app.schemas.source_search import (
    CreateSourceSearchTaskRequest,
    SourceSearchResultResponse,
    SourceSearchTaskResponse,
)
from app.services.auth_service import AuthenticationError, auth_service
from app.services.copywriting_service import copywriting_service
from app.services.task_service import task_service

router = APIRouter()

IMAGE_PROXY_ALLOWED_DOMAINS = ("alicdn.com",)
IMAGE_PROXY_MAX_BYTES = 8 * 1024 * 1024


def require_auth(
    authorization: str | None = Header(default=None),
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing access token")
    return verify_access_token(authorization.removeprefix("Bearer ").strip())


def require_image_auth(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
) -> str:
    if authorization and authorization.startswith("Bearer "):
        return verify_access_token(authorization.removeprefix("Bearer ").strip())
    if token:
        return verify_access_token(token.strip())
    raise HTTPException(status_code=401, detail="Missing access token")


def verify_access_token(access_token: str) -> str:
    try:
        return auth_service.verify_token(access_token)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    try:
        token, expires_in = auth_service.login(payload.username, payload.password)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return LoginResponse(
        access_token=token,
        expires_in=expires_in,
        username=payload.username,
    )


@router.get("/api/auth/session", response_model=SessionResponse)
def get_session(username: str = Depends(require_auth)) -> SessionResponse:
    return SessionResponse(authenticated=True, username=username)


@router.get("/api/image-proxy")
def proxy_image(
    url: str = Query(..., min_length=8),
    _: str = Depends(require_image_auth),
) -> Response:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Unsupported image URL scheme")
    if not any(hostname == domain or hostname.endswith(f".{domain}") for domain in IMAGE_PROXY_ALLOWED_DOMAINS):
        raise HTTPException(status_code=400, detail="Image domain is not allowed")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        ),
        "Referer": "https://detail.1688.com/",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
            upstream = client.get(url)
            upstream.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Image upstream returned HTTP {exc.response.status_code}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Image upstream request failed") from exc

    content_type = upstream.headers.get("content-type", "application/octet-stream").split(";")[0]
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=502, detail="Upstream response is not an image")
    if len(upstream.content) > IMAGE_PROXY_MAX_BYTES:
        raise HTTPException(status_code=502, detail="Image is too large")

    return Response(
        content=upstream.content,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/api/copywriting/generate", response_model=CopywritingResponse)
def generate_copywriting(
    payload: CopywritingRequest,
    _: str = Depends(require_auth),
) -> CopywritingResponse:
    return copywriting_service.generate(payload)


@router.post("/api/source-search/tasks", response_model=SourceSearchTaskResponse)
def create_source_search_task(
    payload: CreateSourceSearchTaskRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_auth),
) -> SourceSearchTaskResponse:
    return task_service.create(payload, background_tasks)


@router.get("/api/source-search/tasks/{task_id}", response_model=SourceSearchTaskResponse)
def get_source_search_task(
    task_id: str,
    _: str = Depends(require_auth),
) -> SourceSearchTaskResponse:
    task = task_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get(
    "/api/source-search/tasks/{task_id}/results",
    response_model=SourceSearchResultResponse,
)
def get_source_search_results(
    task_id: str,
    _: str = Depends(require_auth),
) -> SourceSearchResultResponse:
    result = task_service.get_result(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result

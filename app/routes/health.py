# This project was developed with assistance from AI tools.

"""GET /v1/health and GET /v1/models — service health and model status."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.models.responses import HealthResponse, ModelStatus
from app.services.mission_planning import check_nemotron_health
from app.services.scene_understanding import check_cosmos_health

router = APIRouter()


async def _get_model_statuses(client: httpx.AsyncClient) -> list[ModelStatus]:
    """Check all model endpoints and return their statuses."""
    cosmos_ok, cosmos_err = await check_cosmos_health(client)
    nemotron_ok, nemotron_err = await check_nemotron_health(client)

    return [
        ModelStatus(
            name="cosmos-reason2",
            endpoint=settings.cosmos_endpoint,
            model=settings.cosmos_model,
            available=cosmos_ok,
            error=cosmos_err,
        ),
        ModelStatus(
            name="nemotron",
            endpoint=settings.nemotron_endpoint,
            model=settings.nemotron_model,
            available=nemotron_ok,
            error=nemotron_err,
        ),
    ]


@router.get("/v1/health/live")
async def liveness() -> dict:
    """Trivial liveness check — confirms the process is running."""
    return {"status": "alive"}


@router.get("/v1/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Service health check with model endpoint connectivity."""
    client: httpx.AsyncClient = request.app.state.http_client
    models = await _get_model_statuses(client)

    nemotron_up = any(m.available for m in models if m.name == "nemotron")
    cosmos_up = any(m.available for m in models if m.name == "cosmos-reason2")

    if nemotron_up and cosmos_up:
        status = "healthy"
    elif nemotron_up:
        status = "degraded"  # Can plan but no scene understanding
    else:
        status = "unhealthy"  # Cannot plan at all

    health = HealthResponse(status=status, models=models)
    if status == "unhealthy":
        return JSONResponse(status_code=503, content=health.model_dump())
    return health


@router.get("/v1/models", response_model=list[ModelStatus])
async def list_models(request: Request) -> list[ModelStatus]:
    """List configured models and their current status."""
    client: httpx.AsyncClient = request.app.state.http_client
    return await _get_model_statuses(client)

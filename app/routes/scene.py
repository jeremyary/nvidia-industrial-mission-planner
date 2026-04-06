# This project was developed with assistance from AI tools.

"""POST /v1/scene — standalone scene understanding endpoint."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.models.requests import SceneRequest
from app.models.responses import ErrorResponse, SceneResponse
from app.services.scene_understanding import understand_scene

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/v1/scene",
    response_model=SceneResponse,
    responses={502: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
)
async def describe_scene(body: SceneRequest, request: Request) -> SceneResponse | JSONResponse:
    """Get a scene description from a camera frame without generating a plan.

    Useful for monitoring dashboards and debugging.
    """
    client: httpx.AsyncClient = request.app.state.http_client

    try:
        description = await understand_scene(
            client,
            body.camera_frames,
        )
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={"error": "Scene model timed out", "detail": "Cosmos-Reason2 did not respond"},
        )
    except httpx.HTTPStatusError as e:
        return JSONResponse(
            status_code=502,
            content={
                "error": "Scene model error",
                "detail": f"Cosmos-Reason2 returned HTTP {e.response.status_code}",
            },
        )

    return SceneResponse(scene_description=description)

# This project was developed with assistance from AI tools.

"""POST /v1/plan — primary mission planning endpoint."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.models.requests import PlanRequest
from app.models.responses import ErrorResponse, PlanResponse
from app.services.mission_planning import plan_mission
from app.services.scene_understanding import understand_scene

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/v1/plan",
    response_model=PlanResponse,
    responses={502: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
)
async def create_plan(body: PlanRequest, request: Request) -> PlanResponse | JSONResponse:
    """Generate a mission plan for the robot.

    If a camera frame is provided, scene understanding is performed first
    via Cosmos-Reason2. The scene description is then fed to Nemotron for
    mission planning. Without a camera frame, planning proceeds in
    geometric mode using only the task description and robot state.
    """
    client: httpx.AsyncClient = request.app.state.http_client
    scene_description = None

    # Scene understanding (optional — only when camera frames are provided)
    if body.camera_frames:
        try:
            scene_description = await understand_scene(
                client,
                body.camera_frames,
            )
            logger.info("Scene understanding complete (%d chars)", len(scene_description))
        except httpx.TimeoutException:
            logger.warning("Cosmos-Reason2 timed out — falling back to state-only planning")
        except httpx.HTTPStatusError as e:
            logger.warning(
                "Cosmos-Reason2 returned %s — falling back to state-only planning",
                e.response.status_code,
            )
        except Exception:
            logger.exception("Cosmos-Reason2 call failed — falling back to state-only planning")

    # Mission planning (required)
    try:
        plan = await plan_mission(
            client,
            task=body.task,
            robot_state=body.robot_state,
            scene_description=scene_description,
            replan_context=body.replan_context,
            frame_id=body.frame_id,
            temperature=body.temperature,
        )
    except httpx.TimeoutException:
        logger.error("Nemotron timed out")
        return JSONResponse(
            status_code=504,
            content={"error": "Planning model timed out", "detail": "Nemotron did not respond"},
        )
    except httpx.HTTPStatusError as e:
        logger.error("Nemotron returned %s", e.response.status_code)
        return JSONResponse(
            status_code=502,
            content={
                "error": "Planning model error",
                "detail": f"Nemotron returned HTTP {e.response.status_code}",
            },
        )
    except ValueError as e:
        logger.error("Failed to parse planner output: %s", e)
        return JSONResponse(
            status_code=502,
            content={"error": "Invalid planner output", "detail": str(e)},
        )

    return plan

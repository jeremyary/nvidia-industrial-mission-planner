# This project was developed with assistance from AI tools.

"""Nemotron client for mission planning via OpenAI-compatible API."""

from __future__ import annotations

import json
import logging
from typing import Optional

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app import PROMPTS_DIR
from app.config import settings
from app.models.requests import ReplanContext, RobotState
from app.models.responses import Action, PlanResponse, ReplanCondition
from app.schemas.plan_output import PLAN_OUTPUT_SCHEMA

logger = logging.getLogger(__name__)

_PLANNER_SYSTEM_PROMPT = (PROMPTS_DIR / "planner_system.md").read_text()


def _build_user_message(
    task: str,
    robot_state: RobotState,
    scene_description: Optional[str],
    replan_context: Optional[ReplanContext],
    frame_id: str,
) -> str:
    """Build the user message for the planner LLM."""
    parts = [f"Task: {task}"]

    parts.append(
        f"Robot state: position=({robot_state.pose.x:.2f}, {robot_state.pose.y:.2f}), "
        f"yaw={robot_state.pose.yaw:.3f}"
    )
    parts.append(f"Frame: {frame_id}")

    if scene_description:
        parts.append(f"Scene description:\n{scene_description}")
    else:
        parts.append("No camera input available. Plan using geometric waypoints based on the task.")

    if replan_context:
        parts.append(f"REPLANNING — reason: {replan_context.trigger_reason}")
        parts.append(f"Previous plan: {replan_context.previous_plan_id}")
        if replan_context.completed_actions:
            completed = ", ".join(
                f"{a.action_id}({a.status})" for a in replan_context.completed_actions
            )
            parts.append(f"Completed actions: {completed}")
            failed = [a for a in replan_context.completed_actions if a.failure_reason]
            if failed:
                for a in failed:
                    parts.append(f"  {a.action_id} failed: {a.failure_reason}")

    return "\n\n".join(parts)


def _parse_plan_output(raw: str) -> dict:
    """Extract JSON from the model's raw output text.

    Handles both clean JSON and JSON wrapped in markdown fences.
    """
    text = raw.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()

    return json.loads(text)


def _is_transient(exc: BaseException) -> bool:
    """Return True for transient HTTP errors (502/503/504) worth retrying."""
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (502, 503, 504)


@retry(
    retry=retry_if_exception(_is_transient),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    reraise=True,
)
async def plan_mission(
    client: httpx.AsyncClient,
    task: str,
    robot_state: RobotState,
    scene_description: Optional[str] = None,
    replan_context: Optional[ReplanContext] = None,
    frame_id: str = "world",
    temperature: Optional[float] = None,
) -> PlanResponse:
    """Generate a mission plan using Nemotron."""
    user_message = _build_user_message(
        task, robot_state, scene_description, replan_context, frame_id
    )

    payload: dict = {
        "model": settings.nemotron_model,
        "messages": [
            {"role": "system", "content": _PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 4096,
        "temperature": temperature if temperature is not None else 0.1,
    }

    # Guided decoding for structured JSON output
    payload["response_format"] = {
        "type": "json_schema",
        "json_schema": {
            "name": "mission_plan",
            "strict": True,
            "schema": PLAN_OUTPUT_SCHEMA,
        },
    }

    response = await client.post(
        f"{settings.nemotron_endpoint}/chat/completions",
        json=payload,
        timeout=settings.request_timeout,
    )
    response.raise_for_status()

    data = response.json()
    try:
        raw_content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Unexpected planner model response structure: {e}") from e

    try:
        plan_data = _parse_plan_output(raw_content)
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error("Failed to parse planner output: %s\nRaw: %s", e, raw_content[:500])
        raise ValueError(f"Model output is not valid JSON: {e}") from e

    actions = []
    for i, a in enumerate(plan_data.get("actions", [])):
        try:
            actions.append(
                Action(
                    action_id=a["action_id"],
                    x=a["x"],
                    y=a["y"],
                    yaw=a["yaw"],
                    behavior=a["behavior"],
                    on_arrive=a.get("on_arrive"),
                    description=a["description"],
                )
            )
        except (KeyError, TypeError) as e:
            raise ValueError(f"Action {i} missing required field: {e}") from e

    if not actions:
        raise ValueError("Planner returned empty action list")

    replan_conditions = [
        ReplanCondition(
            condition=rc.get("condition", ""),
            action_id=rc.get("action_id"),
        )
        for rc in plan_data.get("replan_conditions", [])
    ]

    return PlanResponse(
        frame_id=frame_id,
        ttl_seconds=settings.plan_ttl_seconds,
        actions=actions,
        scene_description=scene_description,
        replan_conditions=replan_conditions,
        planning_notes=plan_data.get("planning_notes"),
    )


async def check_nemotron_health(client: httpx.AsyncClient) -> tuple[bool, Optional[str]]:
    """Check if the Nemotron endpoint is reachable."""
    try:
        response = await client.get(
            f"{settings.nemotron_endpoint}/models",
            timeout=5,
        )
        response.raise_for_status()
        return True, None
    except Exception as e:
        return False, str(e)

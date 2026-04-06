# This project was developed with assistance from AI tools.

"""Cosmos-Reason2 client for scene understanding via OpenAI-compatible API."""

from __future__ import annotations

import logging
from typing import Optional

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app import PROMPTS_DIR
from app.config import settings
from app.models.requests import CameraFrame

logger = logging.getLogger(__name__)

_SCENE_SYSTEM_PROMPT = (PROMPTS_DIR / "scene_system.md").read_text()


def _build_image_content(base64_jpeg: str) -> dict:
    """Build an OpenAI-compatible image_url content block for a base64 JPEG."""
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{base64_jpeg}"},
    }


def _is_transient(exc: BaseException) -> bool:
    """Return True for transient HTTP errors (502/503/504) worth retrying."""
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (502, 503, 504)


@retry(
    retry=retry_if_exception(_is_transient),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    reraise=True,
)
async def understand_scene(
    client: httpx.AsyncClient,
    camera_frames: list[CameraFrame],
) -> str:
    """Send camera frame(s) to Cosmos-Reason2 for scene understanding."""
    user_content: list[dict] = [
        {"type": "text", "text": "Describe this scene for robot navigation planning."},
    ]

    for frame in camera_frames:
        user_content.append({"type": "text", "text": f"Camera source: {frame.source}"})
        user_content.append(_build_image_content(frame.frame))

    payload = {
        "model": settings.cosmos_model,
        "messages": [
            {"role": "system", "content": _SCENE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": 2048,
        "temperature": 0.2,
    }

    response = await client.post(
        f"{settings.cosmos_endpoint}/chat/completions",
        json=payload,
        timeout=settings.request_timeout,
    )
    response.raise_for_status()

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Unexpected scene model response structure: {e}") from e


async def check_cosmos_health(client: httpx.AsyncClient) -> tuple[bool, Optional[str]]:
    """Check if the Cosmos-Reason2 endpoint is reachable."""
    try:
        response = await client.get(
            f"{settings.cosmos_endpoint}/models",
            timeout=5,
        )
        response.raise_for_status()
        return True, None
    except Exception as e:
        return False, str(e)

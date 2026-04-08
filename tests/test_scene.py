# This project was developed with assistance from AI tools.

"""Tests for POST /v1/scene endpoint."""

from __future__ import annotations

import httpx
import pytest
import respx
from httpx import Response

from app.config import settings

from .conftest import MOCK_SCENE_RESPONSE, TINY_JPEG_B64


@pytest.mark.asyncio
async def test_scene_description(client):
    """Scene description from a camera frame."""
    with respx.mock:
        respx.post(f"{settings.cosmos_endpoint}/chat/completions").mock(
            return_value=Response(200, json=MOCK_SCENE_RESPONSE)
        )

        resp = await client.post(
            "/v1/scene",
            json={"camera_frames": [{"source": "first_person", "frame": TINY_JPEG_B64}]},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "scene_description" in data
    assert len(data["scene_description"]) > 0


@pytest.mark.asyncio
async def test_scene_missing_camera_frames(client):
    """Missing camera_frames returns 422."""
    resp = await client.post("/v1/scene", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_scene_cosmos_timeout(client):
    """Cosmos-Reason2 timeout returns 504."""
    with respx.mock:
        respx.post(f"{settings.cosmos_endpoint}/chat/completions").mock(
            side_effect=httpx.ReadTimeout("timed out")
        )

        resp = await client.post(
            "/v1/scene",
            json={"camera_frames": [{"source": "first_person", "frame": TINY_JPEG_B64}]},
        )

    assert resp.status_code == 504


@pytest.mark.asyncio
async def test_scene_cosmos_error(client):
    """Cosmos-Reason2 HTTP error returns 502."""
    with respx.mock:
        respx.post(f"{settings.cosmos_endpoint}/chat/completions").mock(
            return_value=Response(500, json={"error": "internal"})
        )

        resp = await client.post(
            "/v1/scene",
            json={"camera_frames": [{"source": "first_person", "frame": TINY_JPEG_B64}]},
        )

    assert resp.status_code == 502

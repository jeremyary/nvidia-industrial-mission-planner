# This project was developed with assistance from AI tools.

"""Integration tests using mock vLLM responses — full request lifecycle."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.config import settings

from .conftest import MOCK_MODELS_RESPONSE, MOCK_PLAN_RESPONSE, MOCK_SCENE_RESPONSE, TINY_JPEG_B64


@pytest.mark.asyncio
async def test_liveness_probe(client):
    """Liveness probe returns 200 unconditionally (no upstream checks)."""
    resp = await client.get("/v1/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_health_all_up(client):
    """Health check when both models are available."""
    with respx.mock:
        respx.get(f"{settings.cosmos_endpoint}/models").mock(
            return_value=Response(200, json=MOCK_MODELS_RESPONSE)
        )
        respx.get(f"{settings.nemotron_endpoint}/models").mock(
            return_value=Response(200, json=MOCK_MODELS_RESPONSE)
        )

        resp = await client.get("/v1/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert len(data["models"]) == 2
    assert all(m["available"] for m in data["models"])


@pytest.mark.asyncio
async def test_health_cosmos_down(client):
    """Health check when Cosmos-Reason2 is unavailable (degraded)."""
    with respx.mock:
        respx.get(f"{settings.cosmos_endpoint}/models").mock(side_effect=ConnectionError("refused"))
        respx.get(f"{settings.nemotron_endpoint}/models").mock(
            return_value=Response(200, json=MOCK_MODELS_RESPONSE)
        )

        resp = await client.get("/v1/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"


@pytest.mark.asyncio
async def test_health_nemotron_down(client):
    """Health check when Nemotron is unavailable (unhealthy)."""
    with respx.mock:
        respx.get(f"{settings.cosmos_endpoint}/models").mock(
            return_value=Response(200, json=MOCK_MODELS_RESPONSE)
        )
        respx.get(f"{settings.nemotron_endpoint}/models").mock(
            side_effect=ConnectionError("refused")
        )

        resp = await client.get("/v1/health")

    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_models_endpoint(client):
    """GET /v1/models returns model statuses."""
    with respx.mock:
        respx.get(f"{settings.cosmos_endpoint}/models").mock(
            return_value=Response(200, json=MOCK_MODELS_RESPONSE)
        )
        respx.get(f"{settings.nemotron_endpoint}/models").mock(
            return_value=Response(200, json=MOCK_MODELS_RESPONSE)
        )

        resp = await client.get("/v1/models")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_full_plan_with_vision_flow(client):
    """End-to-end: camera frame → scene understanding → planning → response."""
    with respx.mock:
        respx.post(f"{settings.cosmos_endpoint}/chat/completions").mock(
            return_value=Response(200, json=MOCK_SCENE_RESPONSE)
        )
        respx.post(f"{settings.nemotron_endpoint}/chat/completions").mock(
            return_value=Response(200, json=MOCK_PLAN_RESPONSE)
        )

        resp = await client.post(
            "/v1/plan",
            json={
                "task": "Deliver water bottle to the presenter on stage",
                "robot_state": {
                    "pose": {"x": 0.0, "y": 0.0, "z": 0.0, "yaw": 0.0},
                },
                "camera_frames": [
                    {"source": "first_person", "frame": TINY_JPEG_B64},
                ],
            },
        )

    assert resp.status_code == 200
    data = resp.json()

    # Verify plan structure matches the robot operator's waypoint format
    assert "plan_id" in data
    assert "timestamp" in data
    assert "ttl_seconds" in data
    assert data["ttl_seconds"] == 300
    assert "frame_id" in data
    assert data["frame_id"] == "world"
    assert len(data["actions"]) > 0

    # Each action should have the fields that map to the Waypoint dataclass
    for action in data["actions"]:
        assert "action_id" in action
        assert "x" in action
        assert "y" in action
        assert "yaw" in action
        assert action["behavior"] in ("walk", "climb", "descend", "stand")
        assert "description" in action

    # Scene description should be present (camera was provided)
    assert data["scene_description"] is not None

    # Should have replan conditions
    assert len(data["replan_conditions"]) > 0


@pytest.mark.asyncio
async def test_graceful_degradation_cosmos_error(client):
    """Cosmos error → plan still succeeds with state-only planning."""
    with respx.mock:
        respx.post(f"{settings.cosmos_endpoint}/chat/completions").mock(
            return_value=Response(500, json={"error": "GPU OOM"})
        )
        respx.post(f"{settings.nemotron_endpoint}/chat/completions").mock(
            return_value=Response(200, json=MOCK_PLAN_RESPONSE)
        )

        resp = await client.post(
            "/v1/plan",
            json={
                "task": "Walk to the door",
                "robot_state": {
                    "pose": {"x": 0.0, "y": 0.0, "z": 0.0, "yaw": 0.0},
                },
                "camera_frames": [
                    {"source": "first_person", "frame": TINY_JPEG_B64},
                ],
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["scene_description"] is None  # Cosmos failed, no scene
    assert len(data["actions"]) > 0  # But planning still worked

# This project was developed with assistance from AI tools.

"""Shared test fixtures."""

from __future__ import annotations

import base64
import json

import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response

from app.config import settings
from app.main import app

# A minimal 1x1 red JPEG for testing (base64-encoded)
TINY_JPEG_B64 = base64.b64encode(
    bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000"
        "ffdb004300080606070605080707070909080a0c"
        "140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c"
        "20242e2720222c231c1c2837292c30313434341f"
        "27393d38323c2e333432ffc0000b080001000101"
        "011100ffc4001f00000105010101010101000000"
        "00000000000102030405060708090a0bffc40000"
        "ffc4000001000000000000000000000000000000"
        "00ffda00080101003f00540dffd9"
    )
).decode()


MOCK_SCENE_RESPONSE = {
    "id": "chatcmpl-test-scene",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": (
                    "Spatial layout: Indoor conference room, approximately 10m x 8m. "
                    "A podium with 3 stairs (step height ~0.18m) is located 5m ahead. "
                    "A person is standing at the podium, 8m ahead and 2m to the right, "
                    "facing the audience. The path to the stairs is clear, flat tile floor. "
                    "Navigation paths: Clear path ahead on flat ground to stairs (5m). "
                    "Stairs have handrails on both sides, width 1.5m."
                ),
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 100, "completion_tokens": 80, "total_tokens": 180},
}

MOCK_PLAN_RESPONSE = {
    "id": "chatcmpl-test-plan",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "actions": [
                            {
                                "action_id": "approach_stairs",
                                "x": 5.0,
                                "y": 0.0,
                                "yaw": 0.0,
                                "behavior": "walk",
                                "on_arrive": None,
                                "description": "Walk to base of podium stairs",
                            },
                            {
                                "action_id": "stabilize",
                                "x": 5.0,
                                "y": 0.0,
                                "yaw": 0.0,
                                "behavior": "stand",
                                "on_arrive": None,
                                "description": "Stabilize before climbing stairs",
                            },
                            {
                                "action_id": "climb_podium",
                                "x": 7.0,
                                "y": 0.0,
                                "yaw": 0.0,
                                "behavior": "climb",
                                "on_arrive": None,
                                "description": "Climb three stairs to podium level",
                            },
                            {
                                "action_id": "approach_presenter",
                                "x": 8.0,
                                "y": 2.0,
                                "yaw": 1.57,
                                "behavior": "walk",
                                "on_arrive": "handshake",
                                "description": "Walk to presenter and shake hands",
                            },
                        ],
                        "replan_conditions": [
                            {
                                "condition": "Presenter has moved",
                                "action_id": "approach_presenter",
                            }
                        ],
                        "planning_notes": "Walk to stairs, stabilize, climb, handshake.",
                    }
                ),
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 200, "completion_tokens": 150, "total_tokens": 350},
}

MOCK_MODELS_RESPONSE = {
    "object": "list",
    "data": [{"id": "test-model", "object": "model"}],
}


@pytest.fixture
async def client():
    """Async test client with lifespan handling."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Manually set up the http_client on app state (lifespan doesn't run with ASGITransport)
        import httpx

        app.state.http_client = httpx.AsyncClient()
        try:
            yield ac
        finally:
            await app.state.http_client.aclose()


@pytest.fixture
def plan_request_body():
    """Minimal plan request body."""
    return {
        "task": "Walk to the podium and shake hands with the presenter",
        "robot_state": {
            "pose": {"x": 0.0, "y": 0.0, "z": 0.0, "yaw": 0.0},
        },
    }


@pytest.fixture
def plan_request_with_camera(plan_request_body):
    """Plan request with camera frames."""
    return {
        **plan_request_body,
        "camera_frames": [{"source": "first_person", "frame": TINY_JPEG_B64}],
    }


@pytest.fixture
def mock_cosmos():
    """Mock the Cosmos-Reason2 chat completions endpoint."""
    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{settings.cosmos_endpoint}/chat/completions").mock(
            return_value=Response(200, json=MOCK_SCENE_RESPONSE)
        )
        mock.get(f"{settings.cosmos_endpoint}/models").mock(
            return_value=Response(200, json=MOCK_MODELS_RESPONSE)
        )
        yield mock


@pytest.fixture
def mock_nemotron():
    """Mock the Nemotron chat completions endpoint."""
    with respx.mock(assert_all_called=False) as mock:
        mock.post(f"{settings.nemotron_endpoint}/chat/completions").mock(
            return_value=Response(200, json=MOCK_PLAN_RESPONSE)
        )
        mock.get(f"{settings.nemotron_endpoint}/models").mock(
            return_value=Response(200, json=MOCK_MODELS_RESPONSE)
        )
        yield mock


@pytest.fixture
def mock_all(mock_cosmos, mock_nemotron):
    """Mock both model endpoints."""
    return mock_cosmos, mock_nemotron

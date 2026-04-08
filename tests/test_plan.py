# This project was developed with assistance from AI tools.

"""Tests for POST /v1/plan endpoint."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from httpx import Response

from app.config import settings
from app.services.mission_planning import _parse_plan_output

from .conftest import MOCK_PLAN_RESPONSE, MOCK_SCENE_RESPONSE


@pytest.mark.asyncio
async def test_plan_with_camera(client, plan_request_with_camera):
    """Full flow: camera frame → scene understanding → mission planning."""
    with respx.mock:
        respx.post(f"{settings.cosmos_endpoint}/chat/completions").mock(
            return_value=Response(200, json=MOCK_SCENE_RESPONSE)
        )
        respx.post(f"{settings.nemotron_endpoint}/chat/completions").mock(
            return_value=Response(200, json=MOCK_PLAN_RESPONSE)
        )

        resp = await client.post("/v1/plan", json=plan_request_with_camera)

    assert resp.status_code == 200
    data = resp.json()
    assert "plan_id" in data
    assert "timestamp" in data
    assert "ttl_seconds" in data
    assert data["ttl_seconds"] == 300
    assert len(data["actions"]) == 4
    assert data["actions"][0]["behavior"] == "walk"
    assert data["actions"][2]["behavior"] == "climb"
    assert data["actions"][3]["on_arrive"] == "handshake"
    assert data["scene_description"] is not None
    assert len(data["replan_conditions"]) > 0


@pytest.mark.asyncio
async def test_plan_without_camera(client, plan_request_body):
    """State-only geometric planning (no camera frame)."""
    with respx.mock:
        respx.post(f"{settings.nemotron_endpoint}/chat/completions").mock(
            return_value=Response(200, json=MOCK_PLAN_RESPONSE)
        )

        resp = await client.post("/v1/plan", json=plan_request_body)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["actions"]) == 4
    assert data["scene_description"] is None


@pytest.mark.asyncio
async def test_plan_cosmos_timeout_falls_back(client, plan_request_with_camera):
    """When Cosmos-Reason2 times out, planning continues without scene description."""
    with respx.mock:
        respx.post(f"{settings.cosmos_endpoint}/chat/completions").mock(
            side_effect=httpx.ReadTimeout("Connection timed out")
        )
        respx.post(f"{settings.nemotron_endpoint}/chat/completions").mock(
            return_value=Response(200, json=MOCK_PLAN_RESPONSE)
        )

        resp = await client.post("/v1/plan", json=plan_request_with_camera)

    assert resp.status_code == 200
    data = resp.json()
    assert data["scene_description"] is None


@pytest.mark.asyncio
async def test_plan_nemotron_timeout(client, plan_request_body):
    """When Nemotron times out, return 504."""
    with respx.mock:
        respx.post(f"{settings.nemotron_endpoint}/chat/completions").mock(
            side_effect=httpx.ReadTimeout("Connection timed out")
        )

        resp = await client.post("/v1/plan", json=plan_request_body)

    assert resp.status_code == 504
    assert "timed out" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_plan_nemotron_malformed_output(client, plan_request_body):
    """When Nemotron returns non-JSON, return 502."""
    malformed_response = {
        "id": "chatcmpl-bad",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "This is not valid JSON at all",
                },
                "finish_reason": "stop",
            }
        ],
    }

    with respx.mock:
        respx.post(f"{settings.nemotron_endpoint}/chat/completions").mock(
            return_value=Response(200, json=malformed_response)
        )

        resp = await client.post("/v1/plan", json=plan_request_body)

    assert resp.status_code == 502
    assert "invalid" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_plan_nemotron_empty_actions(client, plan_request_body):
    """When Nemotron returns empty actions list, return 502."""
    empty_response = {
        "id": "chatcmpl-empty",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps({"actions": []}),
                },
                "finish_reason": "stop",
            }
        ],
    }

    with respx.mock:
        respx.post(f"{settings.nemotron_endpoint}/chat/completions").mock(
            return_value=Response(200, json=empty_response)
        )

        resp = await client.post("/v1/plan", json=plan_request_body)

    assert resp.status_code == 502


def test_parse_plan_output_strips_markdown_fences():
    """LLM output wrapped in ```json ... ``` fences should parse correctly."""
    action = (
        '{"action_id": "a1", "x": 1, "y": 2, "yaw": 0,'
        ' "behavior": "walk", "on_arrive": null, "description": "go"}'
    )
    raw = f'```json\n{{"actions": [{action}]}}\n```'
    result = _parse_plan_output(raw)
    assert result["actions"][0]["action_id"] == "a1"


def test_parse_plan_output_clean_json():
    """Clean JSON without fences should also parse."""
    raw = '{"actions": []}'
    result = _parse_plan_output(raw)
    assert result["actions"] == []


@pytest.mark.asyncio
async def test_plan_nemotron_empty_choices(client, plan_request_body):
    """When Nemotron returns empty choices list, return 502 (not unhandled 500)."""
    empty_choices_response = {
        "id": "chatcmpl-empty",
        "object": "chat.completion",
        "choices": [],
    }

    with respx.mock:
        respx.post(f"{settings.nemotron_endpoint}/chat/completions").mock(
            return_value=Response(200, json=empty_choices_response)
        )

        resp = await client.post("/v1/plan", json=plan_request_body)

    assert resp.status_code == 502
    assert "invalid" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_plan_missing_task(client):
    """Missing required 'task' field returns 422."""
    resp = await client.post(
        "/v1/plan",
        json={
            "robot_state": {
                "pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
            }
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_plan_with_replan_context(client, plan_request_body):
    """Replanning with context from previous plan."""
    plan_request_body["replan_context"] = {
        "previous_plan_id": "abc123",
        "completed_actions": [
            {"action_id": "approach_stairs", "status": "completed"},
            {
                "action_id": "climb_podium",
                "status": "failed",
                "failure_reason": "Stairs blocked by obstacle",
            },
        ],
        "trigger_reason": "obstacle_detected",
    }

    with respx.mock:
        respx.post(f"{settings.nemotron_endpoint}/chat/completions").mock(
            return_value=Response(200, json=MOCK_PLAN_RESPONSE)
        )

        resp = await client.post("/v1/plan", json=plan_request_body)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["actions"]) > 0

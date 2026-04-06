#!/usr/bin/env python3
# This project was developed with assistance from AI tools.

"""Mock vLLM server for local development without GPU access.

Serves canned responses for both Cosmos-Reason2 (scene understanding)
and Nemotron (mission planning) on a single port.

Usage:
    python tests/mock_server.py [--port 9000]
"""

from __future__ import annotations

import json
import sys

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Mock vLLM Server")


MOCK_SCENE_DESCRIPTION = (
    "Spatial layout: Indoor conference room, approximately 12m x 10m. "
    "A raised podium with 4 stairs (step height ~0.18m, depth ~0.28m) is "
    "located 5m ahead and slightly to the right. "
    "Surfaces: Flat tile floor from current position to stairs. Carpeted podium surface. "
    "Obstacles: Two rows of chairs on the left side, 2m away. A lectern on the podium. "
    "People: One person standing at center stage on the podium, approximately 8m ahead "
    "and 2m to the right, facing the audience, holding a microphone. "
    "Objects: Water bottle on the lectern. Cables on the floor near the podium edge. "
    "Navigation paths: Clear 3m-wide path straight ahead to the stairs. "
    "Stair width is 1.5m with handrails on both sides."
)

MOCK_PLAN = {
    "actions": [
        {
            "action_id": "approach_stairs",
            "x": 5.0,
            "y": 0.5,
            "yaw": 0.0,
            "behavior": "walk",
            "on_arrive": None,
            "description": "Walk across flat floor to base of podium stairs",
        },
        {
            "action_id": "stabilize_before_climb",
            "x": 5.0,
            "y": 0.5,
            "yaw": 0.0,
            "behavior": "stand",
            "on_arrive": None,
            "description": "Stabilize stance before transitioning to stair climbing",
        },
        {
            "action_id": "climb_to_podium",
            "x": 7.0,
            "y": 0.5,
            "yaw": 0.0,
            "behavior": "climb",
            "on_arrive": None,
            "description": "Climb four stairs to reach podium level",
        },
        {
            "action_id": "walk_to_presenter",
            "x": 8.0,
            "y": 2.0,
            "yaw": 1.57,
            "behavior": "walk",
            "on_arrive": "handshake",
            "description": "Walk to presenter and extend arm for handshake",
        },
    ],
    "replan_conditions": [
        {
            "condition": "Presenter has moved from expected position",
            "action_id": "walk_to_presenter",
        },
        {"condition": "Stairs are blocked or obstructed", "action_id": "climb_to_podium"},
    ],
    "planning_notes": (
        "Four-step plan: approach stairs on flat ground, stabilize before transition, "
        "climb stairs to podium, then walk to presenter for handshake."
    ),
}


class ChatRequest(BaseModel):
    model: str = ""
    messages: list = []
    max_tokens: int = 2048
    temperature: float = 0.1


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest) -> JSONResponse:
    """Detect whether this is a scene or planning request and return canned response."""
    # Check if any message has image content (scene understanding)
    is_vision = any(
        isinstance(msg.get("content"), list)
        and any(c.get("type") == "image_url" for c in msg["content"] if isinstance(c, dict))
        for msg in request.messages
        if isinstance(msg, dict)
    )

    if is_vision:
        content = MOCK_SCENE_DESCRIPTION
    else:
        content = json.dumps(MOCK_PLAN)

    return JSONResponse(
        content={
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
        }
    )


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "nvidia/Cosmos-Reason2-8B", "object": "model"},
            {"id": "nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16", "object": "model"},
        ],
    }


if __name__ == "__main__":
    import uvicorn

    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 9000
    print(f"Starting mock vLLM server on port {port}")
    uvicorn.run(app, host="127.0.0.1", port=port)

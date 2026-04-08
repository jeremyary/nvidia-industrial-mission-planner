# This project was developed with assistance from AI tools.

"""JSON schema for guided decoding of mission plan output.

Hand-maintained rather than derived from Pydantic models because strict
guided decoding requires specific schema constructs (e.g., oneOf for
nullable enums) that Pydantic's generated schemas don't produce.
"""

PLAN_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["actions"],
    "properties": {
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["action_id", "x", "y", "z", "yaw", "behavior", "description"],
                "properties": {
                    "action_id": {"type": "string"},
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "z": {"type": "number"},
                    "yaw": {"type": "number"},
                    "behavior": {
                        "type": "string",
                        "enum": ["walk", "climb", "descend", "stand"],
                    },
                    "on_arrive": {
                        "oneOf": [
                            {"type": "string", "enum": ["handshake", "wave", "grasp", "release"]},
                            {"type": "null"},
                        ],
                    },
                    "description": {
                        "type": "string",
                    },
                },
            },
        },
        "replan_conditions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["condition"],
                "properties": {
                    "condition": {"type": "string"},
                    "action_id": {"type": ["string", "null"]},
                },
            },
        },
        "planning_notes": {"type": ["string", "null"]},
    },
}

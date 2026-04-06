# This project was developed with assistance from AI tools.

"""Pydantic request models for the mission planner API."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Pose(BaseModel):
    """Robot pose in world frame."""

    x: float = Field(..., description="X position in meters")
    y: float = Field(..., description="Y position in meters")
    z: float = Field(0.0, description="Z position in meters")
    yaw: float = Field(..., description="Yaw orientation in radians")


class RobotState(BaseModel):
    """Current state of the robot as reported by the robot client."""

    pose: Pose


class CompletedAction(BaseModel):
    """An action from a previous plan that has been completed or failed."""

    action_id: str
    status: Literal["completed", "failed", "skipped"] = Field(...)
    failure_reason: Optional[str] = None


class ReplanContext(BaseModel):
    """Context from a previous plan execution, provided when replanning."""

    previous_plan_id: str
    completed_actions: list[CompletedAction] = Field(default_factory=list)
    trigger_reason: str = Field(
        ...,
        description=(
            "Why replanning was triggered: obstacle_detected, path_blocked, "
            "task_updated, human_override"
        ),
    )


class CameraFrame(BaseModel):
    """A single camera frame with source identifier."""

    source: str = Field(
        ...,
        description="Camera source identifier, e.g. 'first_person', 'surveillance_north'",
    )
    frame: str = Field(
        ...,
        description="Base64-encoded JPEG image",
    )


class PlanRequest(BaseModel):
    """Request body for POST /v1/plan."""

    task: str = Field(
        ...,
        description="Natural language task instruction, e.g. 'deliver water bottle to presenter'",
        min_length=1,
    )
    robot_state: RobotState
    camera_frames: list[CameraFrame] = Field(
        default_factory=list,
        description="Camera frames from any number of sources (first-person, surveillance, etc.)",
    )
    replan_context: Optional[ReplanContext] = None
    frame_id: str = Field("world", description="Coordinate frame for poses")
    temperature: Optional[float] = Field(
        None,
        description="Override LLM temperature (0.0-1.0). Uses server default if omitted.",
        ge=0.0,
        le=1.0,
    )


class SceneRequest(BaseModel):
    """Request body for POST /v1/scene."""

    camera_frames: list[CameraFrame] = Field(
        ...,
        min_length=1,
        description="One or more camera frames with source identifiers",
    )
    robot_state: Optional[RobotState] = None

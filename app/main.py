# This project was developed with assistance from AI tools.

"""FastAPI application for the mission planner service."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.routes import health, plan, scene

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the httpx async client lifecycle."""
    logger.info("Starting mission-planner service")
    logger.info("Cosmos endpoint: %s", settings.cosmos_endpoint)
    logger.info("Nemotron endpoint: %s", settings.nemotron_endpoint)

    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.request_timeout, connect=10.0),
    )

    yield

    await app.state.http_client.aclose()
    logger.info("Mission-planner service stopped")


app = FastAPI(
    title="Mission Planner",
    description=(
        "Cloud mission planning service for Unitree G1 humanoid robot. "
        "Orchestrates VLM scene understanding and LLM mission planning."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(plan.router)
app.include_router(scene.router)
app.include_router(health.router)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

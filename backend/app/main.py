from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.observability import (
    init_langfuse,
    observe,
    shutdown_langfuse,
    trace_attributes,
)
from app.schemas import HealthResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Uses the app's own Settings so tests never fall back to get_settings().
        init_langfuse(app_settings)
        yield
        shutdown_langfuse()

    app = FastAPI(title="Screen to Cart API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        with trace_attributes("health"):
            return await _health_check()

    return app


@observe(name="health")
async def _health_check() -> HealthResponse:
    return HealthResponse(status="ok")


app = create_app()

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette import EventSourceResponse, ServerSentEvent

from app.config import Settings, get_settings
from app.observability import (
    init_langfuse,
    observe,
    shutdown_langfuse,
    trace_attributes,
)
from app.schemas import FrameSelected, HealthResponse, IdentifyRequest
from app.vision.frame_select import InvalidFrameError, select_sharpest


class _SseDocsResponse(EventSourceResponse):
    # FastAPI documents a route's response under its class-level media_type, which
    # sse-starlette only sets per instance. Without this, OpenAPI says application/json.
    media_type = "text/event-stream"


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

    @app.get("/lookup", responses={404: {"description": "No cached result"}})
    async def lookup(video_id: str, t: float) -> None:
        # The identify cache arrives in Phase 2; until then every lookup is a miss.
        raise HTTPException(status_code=404, detail="not_cached")

    @app.post(
        "/identify",
        response_class=_SseDocsResponse,
        responses={
            200: {
                "model": FrameSelected,
                "description": "SSE stream. The `frame_selected` event's data is FrameSelected.",
            }
        },
    )
    async def identify(request: IdentifyRequest) -> EventSourceResponse:
        # Frames are checked before the stream opens, because the status code
        # can't change once streaming has started.
        with trace_attributes("identify", session_id=request.video_id):
            try:
                selected = select_sharpest(request.frames)
            except InvalidFrameError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
        return EventSourceResponse(_identify_events(selected))

    return app


@observe(name="health")
async def _health_check() -> HealthResponse:
    return HealthResponse(status="ok")


async def _identify_events(selected: FrameSelected) -> AsyncIterator[ServerSentEvent]:
    yield ServerSentEvent(data=selected.model_dump_json(), event="frame_selected")


app = create_app()

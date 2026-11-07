import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import groq
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from langgraph.graph.state import CompiledStateGraph
from sse_starlette import EventSourceResponse, ServerSentEvent

from app.config import Settings, get_settings
from app.db.identify_cache import IdentifyCache, bucket_of
from app.graph.build import build_graph
from app.graph.state import PipelineState
from app.llm.factory import LlmConfigError
from app.llm.invoke import FixtureMissingError, LlmOutputError
from app.llm.rate_limit import RateLimited
from app.observability import (
    init_langfuse,
    new_callback_handler,
    observe,
    shutdown_langfuse,
    trace_attributes,
)
from app.schemas import (
    Candidates,
    CandidatesEvent,
    ErrorEvent,
    FrameSelected,
    HealthResponse,
    IdentifyRequest,
    LookupResult,
    ProductCandidate,
)
from app.vision.frame_select import InvalidFrameError, select_sharpest

# backend/app/main.py -> parents[1] is backend/. Gitignored: it holds video frames.
EVAL_CAPTURES_DIR = Path(__file__).resolve().parents[1] / "eval" / "captures"

_UPSTREAM_ERRORS = (LlmOutputError, FixtureMissingError, LlmConfigError, groq.APIError)


class _SseDocsResponse(EventSourceResponse):
    # FastAPI documents a route's response under its class-level media_type, which
    # sse-starlette only sets per instance. Without this, OpenAPI says application/json.
    media_type = "text/event-stream"


def get_identify_cache(request: Request) -> IdentifyCache:
    cache: IdentifyCache = request.app.state.identify_cache
    return cache


CacheDependency = Annotated[IdentifyCache, Depends(get_identify_cache)]


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    graph = build_graph()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Uses the app's own Settings so tests never fall back to get_settings().
        init_langfuse(app_settings)
        app.state.identify_cache = IdentifyCache(app_settings.database_url)
        yield
        await app.state.identify_cache.close()
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
    async def lookup(video_id: str, t: float, cache: CacheDependency) -> LookupResult:
        cached = await cache.get(video_id, t)
        if cached is None:
            raise HTTPException(status_code=404, detail="not_cached")
        return LookupResult(
            video_id=video_id, bucket=bucket_of(t), candidates=cached.candidates
        )

    @app.post(
        "/identify",
        response_class=_SseDocsResponse,
        responses={
            200: {
                "model": FrameSelected | CandidatesEvent | ErrorEvent,
                "description": (
                    "SSE stream. Event `frame_selected` carries FrameSelected, "
                    "`candidates` carries CandidatesEvent, `error` carries ErrorEvent."
                ),
            }
        },
    )
    async def identify(
        request: IdentifyRequest, cache: CacheDependency
    ) -> EventSourceResponse:
        # Frames are checked before the stream opens, because the status code
        # can't change once streaming has started.
        with trace_attributes("identify", session_id=request.video_id):
            try:
                selected = select_sharpest(request.frames)
            except InvalidFrameError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
        if app_settings.save_eval_captures:
            await _save_eval_capture(request, selected.index)
        return EventSourceResponse(_identify_events(request, selected, graph, cache))

    return app


@observe(name="health")
async def _health_check() -> HealthResponse:
    return HealthResponse(status="ok")


async def _identify_events(
    request: IdentifyRequest,
    selected: FrameSelected,
    graph: CompiledStateGraph[PipelineState],
    cache: IdentifyCache,
) -> AsyncIterator[ServerSentEvent]:
    yield ServerSentEvent(data=selected.model_dump_json(), event="frame_selected")
    state = PipelineState(
        video_id=request.video_id,
        frame=request.frames[selected.index],
        title=request.title,
        description=request.description,
        transcript=request.transcript,
    )
    final: list[ProductCandidate] = []
    with trace_attributes("identify", session_id=request.video_id):
        try:
            async for update in graph.astream(
                state,
                config={"callbacks": [new_callback_handler()]},
                stream_mode="updates",
            ):
                for values in update.values():
                    final = values["candidates"]
                    yield _candidates_event(values)
        except RateLimited as error:
            yield _error_event(
                ErrorEvent(
                    code="rate_limited",
                    message=str(error),
                    retry_after_seconds=error.retry_after_seconds,
                )
            )
            return
        except _UPSTREAM_ERRORS as error:
            yield _error_event(ErrorEvent(code="upstream_error", message=str(error)))
            return
    await cache.put(request.video_id, request.t, Candidates(candidates=final))


def _candidates_event(values: dict[str, Any]) -> ServerSentEvent:
    event = CandidatesEvent(tier=values["tier"], candidates=values["candidates"])
    return ServerSentEvent(data=event.model_dump_json(), event="candidates")


def _error_event(error: ErrorEvent) -> ServerSentEvent:
    return ServerSentEvent(data=error.model_dump_json(), event="error")


async def _save_eval_capture(request: IdentifyRequest, frame_index: int) -> None:
    capture = request.model_copy(update={"frames": [request.frames[frame_index]]})
    path = EVAL_CAPTURES_DIR / f"{request.video_id}_{request.t:.1f}.json"
    await asyncio.to_thread(EVAL_CAPTURES_DIR.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(path.write_text, capture.model_dump_json())


app = create_app()

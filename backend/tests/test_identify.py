import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.config import Settings
from app.db.identify_cache import IdentifyCache
from app.llm import invoke
from app.llm.rate_limit import RateLimited
from app.main import create_app, get_identify_cache
from app.schemas import Candidates
from tests.frames import blurred_frame, sharp_frame

CONFIDENT = json.dumps(
    {
        "candidates": [
            {
                "brand": "Sony",
                "model": "WH-1000XM5",
                "category": "headphones",
                "color": "black",
                "confidence": 0.92,
                "evidence": [{"source": "visual", "detail": "SONY on the headband"}],
                "search_queries": ["Sony WH-1000XM5"],
                "visual_notes": "black over-ear headphones",
            }
        ]
    }
)


class MemoryCache(IdentifyCache):
    def __init__(self) -> None:
        super().__init__(None)
        self.entries: dict[tuple[str, int], Candidates] = {}

    async def get(self, video_id: str, t: float) -> Candidates | None:
        return self.entries.get((video_id, int(t // 5)))

    async def put(self, video_id: str, t: float, result: Candidates) -> None:
        self.entries[(video_id, int(t // 5))] = result


def _request(frames: list[str]) -> dict[str, Any]:
    return {
        "video_id": "abc123",
        "t": 42.0,
        "frames": frames,
        "title": "Desk setup tour",
        "description": "",
        "transcript": [],
        "paid_promotion": False,
    }


def _events(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in body.replace("\r\n", "\n").strip().split("\n\n"):
        fields = dict(
            line.split(": ", 1) for line in block.splitlines() if ": " in line
        )
        events.append((fields["event"], json.loads(fields["data"])))
    return events


@pytest.fixture
def fake_model(monkeypatch: pytest.MonkeyPatch) -> Callable[[list[str]], None]:
    def install(responses: list[str]) -> None:
        def fake_get_llm(*_: Any) -> BaseChatModel:
            return FakeListChatModel(responses=responses)

        monkeypatch.setattr(invoke, "get_llm", fake_get_llm)

    return install


@pytest.fixture
def cache() -> MemoryCache:
    return MemoryCache()


@pytest.fixture
def client(
    make_settings: Callable[..., Settings], cache: MemoryCache
) -> Iterator[TestClient]:
    app = create_app(make_settings())
    app.dependency_overrides[get_identify_cache] = lambda: cache
    with TestClient(app) as test_client:
        yield test_client


def test_identify_streams_frame_then_candidates_and_caches_them(
    client: TestClient, cache: MemoryCache, fake_model: Callable[[list[str]], None]
) -> None:
    fake_model([CONFIDENT])
    response = client.post("/identify", json=_request([blurred_frame(), sharp_frame()]))
    assert response.status_code == 200
    events = _events(response.text)
    assert [name for name, _ in events] == ["frame_selected", "candidates"]
    assert events[0][1]["index"] == 1
    assert events[1][1]["tier"] == 1
    assert cache.entries[("abc123", 8)].candidates[0].model == "WH-1000XM5"


def test_identify_streams_rate_limited_and_caches_nothing(
    client: TestClient, cache: MemoryCache, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def rate_limited(*_: Any, **__: Any) -> None:
        raise RateLimited(12.0)

    monkeypatch.setattr("app.graph.nodes.identify.invoke_json", rate_limited)
    response = client.post("/identify", json=_request([sharp_frame()]))
    name, data = _events(response.text)[-1]
    assert name == "error"
    assert data["code"] == "rate_limited"
    assert data["retry_after_seconds"] == 12.0
    assert cache.entries == {}


def test_identify_rejects_an_undecodable_frame(client: TestClient) -> None:
    response = client.post("/identify", json=_request(["not an image"]))
    assert response.status_code == 422


def test_lookup_returns_a_cached_result_and_404_on_a_miss(
    client: TestClient, cache: MemoryCache
) -> None:
    cache.entries[("abc123", 8)] = Candidates.model_validate_json(CONFIDENT)
    hit = client.get("/lookup", params={"video_id": "abc123", "t": 44.9})
    assert hit.status_code == 200
    assert hit.json()["candidates"][0]["brand"] == "Sony"
    miss = client.get("/lookup", params={"video_id": "abc123", "t": 45.0})
    assert miss.status_code == 404


def test_identify_and_lookup_work_when_the_database_is_down(
    make_settings: Callable[..., Settings], fake_model: Callable[[list[str]], None]
) -> None:
    fake_model([CONFIDENT])
    # Port 1 on loopback refuses connections, like a stopped Postgres.
    settings = make_settings(
        database_url="postgresql+asyncpg://postgres:postgres@127.0.0.1:1/screen_to_cart"
    )
    with TestClient(create_app(settings)) as client:
        lookup = client.get("/lookup", params={"video_id": "abc123", "t": 42})
        identify = client.post("/identify", json=_request([sharp_frame()]))
    assert lookup.status_code == 404
    assert [name for name, _ in _events(identify.text)] == [
        "frame_selected",
        "candidates",
    ]

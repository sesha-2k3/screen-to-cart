from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas import FrameSelected
from tests.frames import blurred_frame, sharp_frame


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


def test_identify_streams_the_sharp_frame_index(
    make_settings: Callable[..., Settings],
) -> None:
    with TestClient(create_app(make_settings())) as client:
        response = client.post(
            "/identify", json=_request([blurred_frame(), sharp_frame()])
        )

    assert response.status_code == 200
    lines = response.text.splitlines()
    assert "event: frame_selected" in lines
    data = next(line for line in lines if line.startswith("data: "))
    assert FrameSelected.model_validate_json(data.removeprefix("data: ")).index == 1


def test_identify_rejects_an_undecodable_frame(
    make_settings: Callable[..., Settings],
) -> None:
    with TestClient(create_app(make_settings())) as client:
        response = client.post("/identify", json=_request(["not an image"]))

    assert response.status_code == 422

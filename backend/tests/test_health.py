from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_returns_ok_without_langfuse(
    make_settings: Callable[..., Settings],
) -> None:
    with TestClient(create_app(make_settings())) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_includes_health_response(
    make_settings: Callable[..., Settings],
) -> None:
    with TestClient(create_app(make_settings())) as client:
        schema = client.get("/openapi.json").json()

    assert "HealthResponse" in schema["components"]["schemas"]

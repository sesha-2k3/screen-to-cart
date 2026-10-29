---
inclusion: fileMatch
fileMatchPattern: "backend/**/*.py"
---

# Backend conventions (Python 3.12, FastAPI, uv)

- Type hints on every function; code must pass `uv run mypy app` and `uv run ruff check .`.
- Config comes from `app/config.py` (`pydantic-settings`). No `os.environ[...]` scattered in code.
- All I/O is async: `httpx.AsyncClient` (one shared client per adapter, created at startup), SQLAlchemy async sessions.
- Endpoints:
  - `GET /lookup?video_id=&t=` → cached result or 404, fast, no LLM calls.
  - `POST /identify` → `EventSourceResponse` streaming LangGraph node updates.
  - `GET /health`.
- Errors: return structured errors (Pydantic model) with a machine-readable `code` (`rate_limited`, `no_captions`, `nothing_found`, `upstream_error`) so the side panel can show the right message. For `rate_limited`, include `retry_after_seconds`.
- Retailer adapters implement `async def search(query: str) -> list[Listing]` and must fail independently (one retailer down never fails the request).
- Database changes always go through an Alembic migration. The first migration runs `CREATE EXTENSION IF NOT EXISTS vector;`.
- Logging: structured, never log full images or API keys.
